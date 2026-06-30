---
id: wo-1002-engine47
type: work_order
title: "WO-1002 — Engine 47 HPC pressure-loss investigation"
subsystem: HPC
engine: 47
date: 2026-03-18
fault_code: FC-HPC-001
cites_sensors: [7, 12]
assertions:
  - {sensor_id: 7, field: alarm_threshold, value: 551.16}
  - {sensor_id: 12, field: alarm_threshold, value: 519.69}
---

# WO-1002 — Engine 47 HPC Pressure-Loss Investigation

**Engine:** 47 **Date:** 2026-03-18 **Raised by:** prognostics review
**Fault code:** FC-HPC-001 (HPC degradation)

## Observation
Engine 47 showed HPC total discharge pressure (P30) falling to 550.8 psia, below the
**551.16 psia** low alarm threshold, with the fuel-flow ratio (phi) at 519.4 pps/psi,
under its **519.69** low threshold. T30 was elevated but not yet in alarm. This is the
"pressure-loss-first" presentation of HPC degradation.

## Action taken
Confirmed signature over 6 consecutive cycles to rule out sensor noise. Performed
compressor wash; P30 recovered partially to 552.0 psia. Continued monitoring.

## Status
Open — watching for T30 to enter alarm, which would confirm advancing degradation.
