---
id: wo-1003-engine76
type: work_order
title: "WO-1003 — Engine 76 LPT exhaust over-temperature"
subsystem: LPT
engine: 76
date: 2026-04-02
fault_code: FC-LPT-001
cites_sensors: [4]
assertions:
  - {sensor_id: 4, field: alarm_threshold, value: 1428.11}
---

# WO-1003 — Engine 76 LPT Exhaust Over-Temperature

**Engine:** 76 **Date:** 2026-04-02 **Raised by:** line monitoring
**Fault code:** FC-LPT-001 (LPT thermal degradation)

## Observation
Engine 76's LPT outlet temperature (T50) reached 1430.6 degR, above the **1428.11
degR** alarm threshold, sustained over 7 cycles. Coolant bleed (W32) was trending
toward its low threshold. HPC parameters were nominal, so this was treated as a
primary LPT event rather than propagated HPC degradation.

## Action taken
Inspected LPT blades and exhaust path; found minor blade-tip distress, no blockage.
Coolant circuit checked — within limits. Scheduled follow-up inspection in 20 cycles.

## Status
Open — monitor T50; co-occurrence with an HPC alarm would shorten the RUL estimate.
