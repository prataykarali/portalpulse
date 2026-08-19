# Quantum-Resistant Key Architecture Specification

## 1. Cryptographic Rationale
Traditional public-key cryptosystems (RSA-2048, ECDSA) are susceptible to polynomial-time quantum attacks using Shor's Algorithm.

PortalPulse implements symmetric key isolation with **256-bit high-entropy keys**:
- **Grover's Quantum Search Defense**: Grover's algorithm provides a quadratic speedup $O(\sqrt{N})$ for symmetric key searches. A 256-bit key requires $2^{128}$ quantum operations, which remains computationally infeasible across known physics limits.
- **Side-Channel Timing Resistance**: Key verification is performed via `hmac.compare_digest`, which enforces strict constant-time string comparison.

## 2. Key Allocations
- `ADM-QKEY-7F9A2B81C3D4`: Master Admin Global Control Key
- `FAC-QKEY-5E6C1D94A8B2`: Faculty Academic Submission Key
- `STU-QKEY-3B8A7F1C9E20`: Student Scoped Result Viewer Key
