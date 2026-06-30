---
id: wo-1001-engine24
type: work_order
title: "WO-1001 — Engine 24 HPC over-temperature advisory"
subsystem: HPC
engine: 24
date: 2026-03-04
fault_code: FC-HPC-001
cites_sensors: [3, 11]
assertions:
  - {sensor_id: 3, field: alarm_threshold, value: 1607.89}
  - {sensor_id: 11, field: alarm_threshold, value: 48.10}
---

# WO-1001 — Engine 24 HPC Over-Temperature Advisory

**Engine:** 24 **Date:** 2026-03-04 **Raised by:** line monitoring
**Fault code:** FC-HPC-001 (HPC degradation)

## Observation
Trend review flagged Engine 24's HPC discharge temperature (T30) climbing across the
last 12 cycles, reaching 1609.4 degR — above the **1607.89 degR** alarm threshold.
Static discharge pressure (Ps30) reached 48.2 psia, also above its **48.10 psia**
threshold. Total discharge pressure (P30) and the fuel-flow ratio (phi) were trending
down, consistent with the FC-HPC-001 signature.

## Action taken
Reduced HPC borescope interval to every 10 cycles per FC-HPC-001. Compressor wash
scheduled. Began RUL tracking. Borescope showed early-stage blade fouling consistent
with efficiency loss.

## Status
Open — re-baseline T30/Ps30 after wash; escalate to module removal if still in alarm.
