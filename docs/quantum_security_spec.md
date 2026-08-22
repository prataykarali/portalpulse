# Role-Based Cryptographic Access Token (RBAC-PAT) Specification

## 1. Cryptographic Rationale & Access Control
PortalPulse enforces zero-trust role-scoped authentication using **Role-Based Cryptographic Access Tokens**:
- **High-Entropy Token Space**: Cryptographically random tokens generated with 256-bit entropy.
- **Timing Side-Channel Defense**: Token verification uses strict constant-time comparison via `hmac.compare_digest` to prevent statistical execution-time leakage and timing side-channel vulnerabilities.
- **Scope Isolation**: Prevents privilege escalation between Student, Faculty, and Admin personas.

## 2. Active Token Allocations
- `ADM-SEC-7F9A2B81C3D4`: Master Admin Global Control Tower Token
- `FAC-SEC-5E6C1D94A8B2`: Faculty Academic Submission Token
- `STU-SEC-3B8A7F1C9E20`: Student Scoped Result Viewer Token
*(Legacy tokens `ADM-QKEY-...`, `FAC-QKEY-...`, `STU-QKEY-...` are aliased for backward compatibility).*
