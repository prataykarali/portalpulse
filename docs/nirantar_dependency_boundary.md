# Architecture Note: Nirantar Isolation & Dependency Boundary

**Document Version:** 1.0.0  
**Effective Date:** 2026-09-21  
**Status:** HISTORICAL BASELINE; deployment boundary remains active

**Update, 2026-10-29:** The user supplied the Nirantar source repository and requested native UI integration. A separate checkout now contains a native notice component; those source edits supersede the read-only source constraint below. The public here.now site has not been republished, and PortalPulse's existing Nirantar connector still targets a local in-process bridge. No claim of live control over the public Nirantar service follows from this document.

---

## 1. Hard Isolation Constraints & Immutable Boundaries

To ensure strict separation of concerns, zero regression risks, and architectural decoupling between the **PortalPulse Autonomous Resilience Control Plane** and the **Nirantar National Railway ERP** target platform, the following invariant boundaries are established:

### Non-Modification & Non-Deployment Invariants
1. **Local Nirantar Workspace:**
   - Path: `/home/pratay-karali/Desktop/NIRANTAR`
   - **Historical constraint:** Originally read-only. The user subsequently authorized a native notification component in a separate Nirantar checkout.
2. **Remote Deployed Endpoint:**
   - Target URL: `https://ubuntu-cedar-sqkf.here.now/`
   - **Current state:** No remote deployment has been changed. A new frontend publication requires a successful build and a reachable event backend.
3. **No Frontend Source Code Import:**
   - Nirantar's frontend source tree (React, Vite, TypeScript, Tailwind components) must never be imported, copied, or bundled into PortalPulse.
4. **Zero Mutation of Core Logic & Assets:**
   - Nirantar UI components, static assets, internal railway business models, Tatkal algorithms, and database routes must remain untouched.

---

## 2. Dependency Architecture & Communication Hierarchy

All communication between PortalPulse and Nirantar is strictly mediated through the existing decoupled adapter and bridge contracts:

```
┌────────────────────────────────────────────────────────┐
│               PORTALPULSE CONTROL PLANE                │
│  M1: Telemetry Ingestion (VUs, RPS, Latency, Queue)    │
│  M2: Forecast  │  M3: Anomaly  │  M9: Queue Knee Point │
│  M4: XGBoost + Causal DAG Root Cause Analysis          │
│  M5: PyTorch Policy Network (Prescriptive SRE)         │
│  M6: Deterministic Safety Guardrails & Masking         │
│  M7: Closed-Loop Actuator & Verification Delta         │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                  ADAPTER / BRIDGE LAYER                │
│  • backend/connectors/nirantar.py (NirantarConnector)  │
│  • backend/connectors/nirantar_bridge.py               │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│           NIRANTAR CONNECTOR / STATE INTERFACE         │
│  • Concurrency Tracker: NIRANTAR_SESSION_TRACKER       │
│  • State Dictionary:    NIRANTAR_INFRA_STATE           │
│  • Portal Contract:     BasePortalConnector Protocol   │
│  • Actuator Endpoints:  /portalpulse/actions           │
└────────────────────────────────────────────────────────┘
```

### Protocol Boundaries
- **Telemetry Ingestion:** Read-only access via [`NirantarConnector.get_telemetry()`](file:///home/pratay-karali/Desktop/portalpulse/backend/connectors/nirantar.py) consuming empirical measurements from [`NIRANTAR_SESSION_TRACKER`](file:///home/pratay-karali/Desktop/portalpulse/backend/connectors/nirantar_bridge.py).
- **Capability Discovery:** Static declaration via [`NirantarConnector.get_capabilities()`](file:///home/pratay-karali/Desktop/portalpulse/backend/connectors/nirantar.py) (e.g. horizontal scaling, waiting room, replica diversion, rate limiting).
- **Topology Declaration:** Structural graph nodes via [`NirantarConnector.get_dependencies()`](file:///home/pratay-karali/Desktop/portalpulse/backend/connectors/nirantar.py) for dynamic causal DAG evaluation.
- **Actuation & Mitigation:** Controlled mutation strictly mediated by [`NirantarConnector.execute_action()`](file:///home/pratay-karali/Desktop/portalpulse/backend/connectors/nirantar.py) calling the internal bridge action handler (`/portalpulse/actions`) without direct database or container manipulation.

---

## 3. Baseline Verification Record

Prior to any modifications or additions for the continuous traffic loop, the full existing test suite was executed to establish the verifiable baseline:

- **Command Executed:** `.venv/bin/pytest`
- **Execution Timestamp:** 2026-09-21T21:17:13+05:30
- **Duration:** 22.76 seconds
- **Test Results:**
  - **Passed:** `204 passed`
  - **Failed:** `0`
  - **Warnings:** `1 warning` (`StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead.`)
- **Status:** **BASELINE CONFIRMED AND RECORDED** (matches expected `204 passed, 1 warning`).

---

## 4. Deployment Status
- **Current State:** No deployment operations executed. System remains in safe local baseline state.
