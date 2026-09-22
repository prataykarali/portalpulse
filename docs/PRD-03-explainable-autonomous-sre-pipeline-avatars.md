# PortalPulse PRD-03: Explainable Autonomous SRE Pipeline & Portal Avatars

## Objective
Turn PortalPulse's existing intelligence modules into a visible, traceable decision pipeline.
The UI must prove that the local models actually execute.

---

## 1. Model Pipeline
Create:
```text
M1 MONITORING
      ↓
M2 PREDICTION
      ↓
M3 ANOMALY
      ↓
M4 RCA
      ↓
M5 ACTION INTELLIGENCE
      ↓
M6 SAFETY
      ↓
M7 ACTUATOR
      ↓
VERIFICATION
```
The existing architecture already contains these intelligence layers, including prediction, anomaly detection, RCA, action intelligence, deterministic safety and closed-loop actuation.

---

## 2. Actual Model Execution
For every model display:
```text
STATUS
INPUT
OUTPUT
CONFIDENCE
INFERENCE TIME
MODEL VERSION
```
Example:
```text
M2 Prediction

● COMPLETE

Prediction:
Saturation in 73 seconds

Confidence:
92%

Inference:
4.2ms
```
Never display documentation metrics as if they were current inference results.

---

## 3. Model Consensus
Display:
```text
PREDICTION
Saturation imminent
92%

ANOMALY
Abnormal traffic
91%

RCA
DB saturation
89%

ACTION
Enable cache
94%
```
Then M6 evaluates.

---

## 4. Model Disagreement
If:
```text
Prediction: 91%
RCA: 61%
Action: 55%
```
M6 should not blindly execute.
Show:
```text
⚠ HUMAN APPROVAL REQUIRED
```

---

## 5. Deterministic Safety Layer
M6 checks:
- confidence
- cooldown
- rate limit
- blast radius
- portal capability
- allowlist
- current state
- rollback availability

Then:
```text
APPROVED
REJECTED
HITL REQUIRED
```

---

## 6. Real Actuation
Do not merely modify telemetry variables.
Where safe:
- `SCALE WORKERS`
- `ENABLE CACHE`
- `ENABLE RATE LIMIT`
- `ENABLE WAITING ROOM`
- `RESTART WORKER`

must change the actual local portal environment.

If simulated:
- `SIMULATED ACTION` must be shown.

The existing audit specifically identifies the current in-memory actuator behavior as a limitation.

---

## 7. Action Explanation
Every action needs:
```text
WHAT
WHY
CONFIDENCE
EXPECTED BENEFIT
BLAST RADIUS
SAFETY CHECKS
```
Example:
```text
ENABLE WAITING ROOM

WHY:
PCI = 94%
P95 above SLA
saturation predicted in 61 sec
traffic accelerating

Confidence:
93%

Blast radius:
LOW

Capability:
SUPPORTED

Cooldown:
CLEAR

Decision:
APPROVED
```

---

## 8. Live Decision Timeline
Create:
```text
10:04:12  Telemetry received
10:04:13  M2 prediction
10:04:14  M3 anomaly
10:04:15  M4 RCA
10:04:16  M5 recommendation
10:04:17  M6 approved
10:04:18  M7 executed
10:04:24  Recovery detected
```
This must be backed by real event logs.

---

## 9. Portal Anatomy
Create a dedicated section:
### HOW THIS PORTAL WORKS
It should visualize the actual architecture.
Example:
```text
USER → FRONTEND → API → BACKEND → CACHE → DATABASE
```
For each portal, load its own architecture.
Do not display Nirantar architecture for IEMCRP.

---

## 10. Nirantar Avatar System
Retain the existing PortalPulse visual/avatar system.
Create role-based explanations:
- **Monitoring Avatar**: Explains telemetry.
- **Prediction Avatar**: Explains forecast.
- **Anomaly Avatar**: Explains abnormal behavior.
- **RCA Avatar**: Explains bottleneck.
- **Action Avatar**: Explains intervention.
- **Safety Avatar**: Explains governance.
- **Verification Avatar**: Explains recovery.

These avatars should reference current system state.
Example:
> *"I detected a rapid increase in result requests. P95 has increased by 31% over the last 20 seconds."*
Not generic text.

---

## 11. IEMCRP Avatar System
Create **3 additional portal-specific avatars** for the IEMCRP-style portal.
First inspect IEMCRP's actual workflow and architecture.
Then create three domain-specific roles. They must not simply be recolored copies of Nirantar avatars.
Use roles based on IEMCRP's real workflow:
1. **IEMCRP User/Access Avatar**: Explains how a user enters and navigates the portal (enrollment, auth, exam lobby).
2. **IEMCRP Processing Avatar**: Explains the portal's core transaction/request-processing flow (marksheet calculation, submission commits).
3. **IEMCRP Operations Avatar**: Explains backend processing, dependencies and operational health (monolithic DB lock contention, worker exhaustion).

---

## 12. Avatar Behavior
Avatars must not become static decorations.
During a live test they should respond to events.
Example:
- Traffic spike: *"We're receiving 2.4× normal traffic."*
- RCA: *"The current bottleneck appears to be database connections."*
- Action: *"I recommend enabling the available cache layer before scaling."*
- Recovery: *"Latency has returned below the SLA. The mitigation appears effective."*

---

## 13. Admin Control Tower
Add:
```text
ADMIN
  ↓
SIMULATION LAB
```
with:
- Exam Day
- Result Rush
- Traffic Spike
- Database Failure
- Redis Failure
- Worker Failure
- Bot Spike
- Combined Disaster
- Custom Scenario

Each must show:
- Target Portal
- Traffic
- Fault
- Expected Risk
- Recommended Controls
- `START`, `STOP`, `RESET`

---

## 14. "BREAK THE PORTAL" Demo
Create a controlled demonstration mode:
- Admin chooses: Target, Scenario, Users, Spawn Rate, Fault
- Then: `[ BREAK TEST ]`
- PortalPulse should observe the actual degradation and run its pipeline.

---

## 15. User Impact
Do not only display infrastructure metrics.
Display:
- Users affected
- Successful requests
- Failed requests
- Login success %
- Submission success %
- Result success %
- Average waiting time
- 429 responses
- 5xx responses

Connect technical failure to user impact.

---

## 16. Recovery Score
After every incident calculate:
```text
RECOVERY SCORE
- Detection time
- Prediction lead time
- RCA accuracy/confidence
- Action latency
- Recovery time
- User impact
```
Then show `RECOVERY VERIFIED` only when actual telemetry confirms recovery.

---

## 17. No Fake "AI"
The system must never claim "AI fixed the portal" unless:
1. the model actually ran
2. the action actually ran
3. the portal actually changed
4. telemetry confirms improvement

Otherwise label it: `SIMULATION` or `RECOMMENDATION ONLY`.

---

## 18. Final Acceptance Demonstration
The following must work:
```text
OPEN NIRANTAR
      ↓
START EXAM DAY
      ↓
LOCUST GENERATES TRAFFIC
      ↓
NIRANTAR ACTUALLY RECEIVES REQUESTS
      ↓
PORTALPULSE RECEIVES TELEMETRY
      ↓
M2 PREDICTS
      ↓
M3 DETECTS
      ↓
M4 EXPLAINS
      ↓
M5 RECOMMENDS
      ↓
M6 APPROVES
      ↓
M7 ACTS
      ↓
NIRANTAR CHANGES
      ↓
TELEMETRY CHANGES
      ↓
RECOVERY VERIFIED
```
Then repeat with:
```text
IEMCRP
```
and demonstrate that the metrics, architecture, traffic patterns and available actions are different.

---

## 19. Final Rule
Do not optimize for the appearance of intelligence.
Optimize for:
```text
REAL INPUT → REAL DECISION → REAL ACTION → REAL OUTCOME
```
Every visible claim must have a traceable backend source.
