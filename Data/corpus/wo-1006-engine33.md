---
id: wo-1006-engine33
type: work_order
title: "WO-1006 — Engine 33 bypass-ratio drift"
subsystem: Fan
engine: 33
date: 2026-05-01
fault_code: FC-FAN-001
cites_sensors: [15]
assertions:
  - {sensor_id: 15, field: alarm_threshold, value: 8.54}
  - {sensor_id: 15, field: nominal_max, value: 8.48}
---

# WO-1006 — Engine 33 Bypass-Ratio Drift

**Engine:** 33 **Date:** 2026-05-01 **Raised by:** trend review
**Fault code:** FC-FAN-001 (advisory)

## Observation
Engine 33's bypass ratio (BPR) drifted to 8.55, just over the **8.54** alarm threshold
and above the **8.48** nominal maximum. Per the fan manual, rising BPR with no
corresponding HPC alarm is usually a secondary effect rather than a fan fault.

## Action taken
Reviewed HPC parameters — all nominal, so this was logged as an isolated fan advisory,
not FC-HPC-001. No hardware action; flagged for re-review in 25 cycles.

## Status
Open (advisory) — monitor; escalate only if HPC parameters subsequently enter alarm.
