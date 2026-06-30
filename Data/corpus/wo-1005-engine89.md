---
id: wo-1005-engine89
type: work_order
title: "WO-1005 — Engine 89 routine inspection (nominal)"
subsystem: HPC
engine: 89
date: 2026-04-22
fault_code: null
cites_sensors: [3, 7]
assertions:
  - {sensor_id: 3, field: nominal_min, value: 1576.37}
  - {sensor_id: 3, field: nominal_max, value: 1597.38}
  - {sensor_id: 7, field: nominal_min, value: 552.51}
  - {sensor_id: 7, field: nominal_max, value: 555.21}
---

# WO-1005 — Engine 89 Routine Inspection (Nominal)

**Engine:** 89 **Date:** 2026-04-22 **Raised by:** scheduled maintenance
**Fault code:** none

## Observation
Scheduled 30-cycle HPC inspection. All HPC parameters within nominal range: T30 at
1588 degR (nominal **1576.37 – 1597.38**), P30 at 553.8 psia (nominal **552.51 –
555.21**). No advisories. Borescope clean.

## Action taken
Routine inspection completed, no corrective action required. Next inspection scheduled
in 30 cycles per the HPC manual.

## Status
Closed — engine healthy, baseline confirmed.
