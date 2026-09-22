"""Knowledge Base and Semantic Document Retrieval Engine for PortalPulse.

Indexes secure_action.md and platform operational runbooks into searchable
knowledge chunks with TF-IDF vectorization and cosine similarity retrieval.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from backend.m5_assistant.schema import DocumentChunk

SECURE_ACTION_PATH = Path(__file__).resolve().parents[2] / "secure_action.md"


class SREKnowledgeBase:
    """Semantic RAG Knowledge Base grounded in secure_action.md and SRE runbooks."""

    def __init__(self, doc_path: Optional[Path] = None) -> None:
        self.doc_path = doc_path or SECURE_ACTION_PATH
        self.chunks: List[DocumentChunk] = []
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.tfidf_matrix: Optional[np.ndarray] = None
        self.topics: List[str] = []

        self._build_index()

    def _build_index(self) -> None:
        """Parse secure_action.md into discrete topic chunks and build TF-IDF index."""
        if not self.doc_path.exists():
            self._init_default_chunks()
        else:
            raw_text = self.doc_path.read_text(encoding="utf-8")
            self._parse_markdown_sections(raw_text)

        if not self.chunks:
            self._init_default_chunks()

        # Build TF-IDF vectorizer
        corpus = [f"{c.title} {c.section} {' '.join(c.tags)} {c.content}" for c in self.chunks]
        self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        self.tfidf_matrix = self.vectorizer.fit_transform(corpus)
        self.topics = sorted(list({c.section for c in self.chunks}))

    def _parse_markdown_sections(self, text: str) -> None:
        """Split markdown document by headers (## Section)."""
        sections = re.split(r"\n##\s+", text)

        for i, sec in enumerate(sections):
            lines = sec.strip().split("\n")
            if not lines:
                continue

            header = lines[0].strip("# ").strip()
            body = "\n".join(lines[1:]).strip()

            if not body or len(body) < 40:
                continue

            # Extract tags based on keywords
            tags = []
            lower_body = body.lower()
            if "token bucket" in lower_body or "rate limit" in lower_body:
                tags.extend(["rate-limiting", "token-bucket", "ingress"])
            if "circuit breaker" in lower_body or "fallback" in lower_body:
                tags.extend(["circuit-breaker", "resilience", "fault-tolerance"])
            if "autoscaling" in lower_body or "horizontal" in lower_body or "warm pool" in lower_body:
                tags.extend(["autoscaling", "hpa", "capacity"])
            if "queue" in lower_body or "buffer" in lower_body or "kafka" in lower_body:
                tags.extend(["queueing", "backpressure", "buffering"])
            if "database" in lower_body or "connection pool" in lower_body or "replica" in lower_body:
                tags.extend(["database", "connection-pool", "sql"])
            if "ddos" in lower_body or "flash crowd" in lower_body or "anycast" in lower_body:
                tags.extend(["ddos", "anycast", "flash-crowd"])
            if "keep-alive" in lower_body or "http/2" in lower_body or "quic" in lower_body:
                tags.extend(["networking", "quic", "http2"])

            chunk_id = f"sec_{i:02d}_{header.lower().replace(' ', '_')[:24]}"
            self.chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    title=header,
                    section=header,
                    content=body,
                    tags=list(set(tags)),
                    relevance_score=1.0,
                )
            )

    def _init_default_chunks(self) -> None:
        """Fallback knowledge chunks if markdown file is unavailable."""
        defaults = [
            (
                "Token Bucket Rate Limiting",
                "Rate Limiting and Throttling",
                "The token bucket algorithm accumulates tokens at a sustained refill rate up to capacity. "
                "Each incoming request consumes a token. Allows bursts up to bucket size then sustains refill rate. "
                "Ideal for burst-tolerant API ingress protection under flash crowd conditions.",
                ["rate-limiting", "token-bucket", "ingress"],
            ),
            (
                "Circuit Breakers and Graceful Degradation",
                "Backpressure and Graceful Degradation",
                "Circuit breakers monitor dependent service success rates. When errors exceed threshold, "
                "the circuit trips open and immediately serves fallback responses to prevent cascading thread exhaustion. "
                "Includes half-open state to periodically probe service recovery.",
                ["circuit-breaker", "resilience", "fault-tolerance"],
            ),
            (
                "Predictive and Horizontal Autoscaling",
                "Autoscaling Strategies",
                "Horizontal scaling adds worker replicas to distribute request load for stateless services. "
                "Warm pools maintain pre-initialized standby instances to eliminate cold-start latency. "
                "Predictive scaling provisions capacity minutes ahead of forecasted traffic surges.",
                ["autoscaling", "hpa", "capacity"],
            ),
            (
                "Database Connection Pool and Read Divergence",
                "Resilience Patterns",
                "Under database lock contention or pool exhaustion, increasing connection ceiling and recycling "
                "idle connections provides immediate relief. Read queries should be redirected to secondary replicas.",
                ["database", "connection-pool", "sql"],
            ),
            (
                "Virtual Waiting Room and Queue Buffering",
                "Queueing, Buffering, and Caching",
                "When arrival rates exceed 10,000 RPS, edge FIFO waiting rooms throttle user admission. "
                "Message queues buffer asynchronous tasks, shielding downstream worker backends from sudden bursts.",
                ["queueing", "backpressure", "buffering"],
            ),
        ]

        for i, (title, sec, content, tags) in enumerate(defaults):
            self.chunks.append(
                DocumentChunk(
                    chunk_id=f"default_{i:02d}",
                    title=title,
                    section=sec,
                    content=content,
                    tags=tags,
                    relevance_score=1.0,
                )
            )

    def search(self, query: str, top_k: int = 3) -> List[DocumentChunk]:
        """Search knowledge base using TF-IDF cosine similarity.

        Args:
            query: Operator natural language question.
            top_k: Number of highest-ranked chunks to return.

        Returns:
            List of DocumentChunk sorted by descending relevance score.
        """
        if not self.chunks or self.vectorizer is None or self.tfidf_matrix is None:
            return []

        clean_query = query.strip()
        if not clean_query:
            return self.chunks[:top_k]

        query_vec = self.vectorizer.transform([clean_query])
        scores = cosine_similarity(query_vec, self.tfidf_matrix)[0]

        # Rank indices
        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for idx in top_indices:
            score = float(scores[idx])
            chunk = self.chunks[idx]
            results.append(
                DocumentChunk(
                    chunk_id=chunk.chunk_id,
                    title=chunk.title,
                    section=chunk.section,
                    content=chunk.content,
                    tags=chunk.tags,
                    relevance_score=round(score, 4),
                )
            )

        return results


# Global singleton instance
KNOWLEDGE_BASE = SREKnowledgeBase()
