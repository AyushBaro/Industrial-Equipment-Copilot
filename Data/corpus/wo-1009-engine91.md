---
id: wo-1009-engine91
type: work_order
title: "WO-1009 — Engine 91 combined LPT thermal + coolant event"
subsystem: LPT
engine: 91
date: 2026-06-08
fault_code: FC-LPT-001
cites_sensors: [4, 21]
assertions:
  - {sensor_id: 4, field: alarm_threshold, value: 1428.11}
  - {sensor_id: 21, field: alarm_threshold, value: 23.00}
---

# WO-1009 — Engine 91 Combined LPT Thermal + Coolant Event

**Engine:** 91 **Date:** 2026-06-08 **Raised by:** prognostics review
**Fault code:** FC-LPT-001

## Observation
Engine 91 presented the full FC-LPT-001 signature: LPT outlet temperature (T50) at
1431.2 degR, above the **1428.11 degR** threshold, with LPT coolant bleed (W32) at
22.9 lbm/s, below the **23.00 lbm/s** low threshold. HPC parameters were also
elevated, indicating degradation had propagated downstream from the core gas path.

## Action taken
Raised FC-LPT-001 alongside the existing HPC advisory. Given co-occurrence of HPC and
LPT signatures, prioritized end-of-life planning and tightened RUL tracking.

## Status
Open — late-life engine with combined HPC + LPT degradation; removal planning initiated.
