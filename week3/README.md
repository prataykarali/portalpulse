# Week 3: Anomaly Detection & Root Cause Analysis (M3 & M4)

## Strategic Objective
Week 3 focuses on the **Detective Layer** of PortalPulse:
1. **Module 3 (M3: Unsupervised Anomaly Detection)**:
   - *"Is something abnormal happening right now?"*
   - Powered by `sklearn.ensemble.IsolationForest` trained strictly on nominal, SLA-preserving telemetry.
   - Computes continuous anomaly scores $[0.0 \to 1.0]$ and discrete anomaly alert triggers.
2. **Module 4 (M4: Root Cause Analysis & Topological Graph Traversal)**:
   - *"What probably caused the anomaly?"*
   - Supervised **XGBoost RCA Classifier** attributing failure to 8 core failure categories (`NORMAL`, `TRAFFIC_SPIKE`, `API_CPU`, `DATABASE`, `NETWORK`, `MEMORY`, `QUEUE_OVERLOAD`, `DEPENDENCY_FAILURE`).
   - **NetworkX Topological Causal Graph** propagating anomalies across physical architectural tiers ($\text{Users} \to \text{CDN} \to \text{API Gateway} \to \text{Backend Pods} \to \text{Database/Redis}$) to isolate the root tier.

## Deliverables & Modules
- `backend/m3_anomaly_rca/schema.py`: Pydantic contracts for anomaly and RCA diagnostics.
- `backend/m3_anomaly_rca/anomaly_detector.py`: Production Isolation Forest inference engine.
- `backend/m3_anomaly_rca/rca_classifier.py`: Production XGBoost multi-class RCA engine.
- `backend/m3_anomaly_rca/dependency_graph.py`: NetworkX causal DAG traversal engine.
- `backend/m3_anomaly_rca/train_rca.py`: Model training & synthetic incident evaluation pipeline.
- `backend/m3_anomaly_rca/routes.py`: FastAPI endpoints for live anomaly & RCA querying.
- `tests/test_m3_m4_anomaly_rca.py`: Comprehensive test suite verifying accuracy and latency.
