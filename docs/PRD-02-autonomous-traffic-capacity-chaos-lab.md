# PortalPulse PRD-02: Autonomous Traffic, Capacity & Chaos Laboratory

## Objective
Create a real load-testing environment in which PortalPulse can stress Nirantar and IEMCRP using Locust and observe what actually happens.
The administrator must be able to simulate realistic traffic rather than simply moving a "users" slider.

---

## 1. Locust Integration
- Locust becomes the official traffic engine.
- PortalPulse must be able to launch/control test scenarios.
- Each test must record:
  - target portal
  - scenario
  - VUs
  - spawn rate
  - duration
  - RPS
  - latency
  - errors
  - endpoint distribution
  - peak concurrency

---

## 2. Real User Personas
Create:

### Student
- login
- dashboard
- exam
- questions
- autosave
- submit
- logout

### Panicked Student
- login
- refresh
- refresh
- dashboard
- retry
- exam
- submit

### Result-Rush Student
- login
- results
- marksheet
- results
- results

### Faculty
- login
- roster
- grade
- save
- cache invalidation

### Abnormal Client
- rapid repeated requests

Each persona gets configurable probability.

---

## 3. Randomized Behavior
Do not use:
- *every user sleeps exactly 5 seconds*

Use randomized:
- think time
- session duration
- endpoint selection
- retries
- refreshes
- submission timing

Support configurable traffic distributions.

---

## 4. Traffic Modes
Implement:
- `CONSTANT`
- `RAMP_UP`
- `RAMP_DOWN`
- `SPIKE`
- `WAVE`
- `STAMPEDE`
- `RESULT_RUSH`
- `CUSTOM`

---

## 5. Exam Day Simulator
Create:
```text
ADMIN
  ↓
SIMULATION LAB
  ↓
EXAM DAY
```

Controls:
- Expected Students
- Peak Concurrent Users
- Login Burst
- Autosave Frequency
- Question Access Rate
- Submission Burst
- Result Rush
- Duration

Example:
- `08:45` NORMAL
- `08:55` LOGIN RAMP
- `09:00` EXAM STAMPEDE
- `09:30` STEADY STATE
- `10:55` SUBMISSION RUSH
- `11:00` SUBMISSION SPIKE
- `13:00` RESULT RUSH

These events must generate actual Locust traffic.

---

## 6. Capacity Discovery
PortalPulse must discover capacity experimentally.

Start low:
- 50
- 100
- 250
- 500
- 1000
- 2000
- 4000
- ...

Record:
- RPS
- P50
- P95
- P99
- CPU
- RAM
- DB
- errors

Detect:
- Sustainable Capacity
- Degradation Knee
- Hard Saturation
- Operating Ceiling

Store these per portal.

---

## 7. Capacity Headroom
Create a flagship metric:
```text
PORTAL CAPACITY

Current:
6,420 users

Sustainable:
8,400 users

Headroom:
1,980

Utilization:
76.4%
```

Use actual capacity profiles.
Do not calculate capacity from an arbitrary frontend constant.

---

## 8. Capacity States
- **0–70%**: `SAFE`
- **70–85%**: `PREPARE`
- **85–100%**: `CRITICAL`
- **>100%**: `OVER CAPACITY`

Thresholds should be configurable.

---

## 9. Chaos Scenarios
Implement:
- `TRAFFIC SPIKE`
- `DB LATENCY`
- `DB CONNECTION EXHAUSTION`
- `CACHE MISS STORM`
- `WORKER FAILURE`
- `CPU PRESSURE`
- `MEMORY PRESSURE`
- `NETWORK LATENCY`
- `5XX BURST`
- `DEPENDENCY FAILURE`

Whenever possible, affect the real local environment.
If a scenario cannot safely be made real:
- `SIMULATED FAULT` must be clearly displayed.

---

## 10. Scenario Builder
Admin chooses:
- Portal
- Users
- Spawn Rate
- Duration
- Traffic Persona Mix
- Think Time
- Endpoint Mix
- Fault Type
- Fault Intensity

Then:
- `[ START ]`
- `[ STOP ]`
- `[ RESET ]`

---

## 11. Before/After Verification
Every mitigation must produce:
```text
BEFORE
P95: 910ms
5xx: 6.2%
CPU: 94%

ACTION
ENABLE_CACHE

AFTER
P95: 410ms
5xx: 0.8%
CPU: 68%
```

Then calculate:
- Latency improvement
- Error reduction
- Capacity improvement
- Recovery time

If metrics don't improve:
- `ACTION INEFFECTIVE`

Never declare success from the action response alone.

---

## 12. Autonomous Test Mode
Add:
```text
AUTONOMOUS CAPACITY DISCOVERY
```

PortalPulse automatically:
1. starts load
2. increases load
3. monitors SLA
4. detects knee
5. reduces load
6. probes around the knee
7. calculates sustainable capacity
8. saves the profile
9. updates capacity dashboard

---

## 13. Acceptance Test
A valid demonstration must show:
```text
Locust
  ↓
REAL PORTAL
  ↓
REAL TELEMETRY
  ↓
CAPACITY CHANGE
  ↓
PORTALPULSE DETECTION
```

The UI must visibly change because the underlying portal changed.
