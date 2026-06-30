---
id: wo-1004-engine12
type: work_order
title: "WO-1004 — Engine 12 core overspeed advisory"
subsystem: Core
engine: 12
date: 2026-04-15
fault_code: FC-HPC-001
cites_sensors: [9, 14]
assertions:
  - {sensor_id: 9, field: alarm_threshold, value: 9092.00}
  - {sensor_id: 14, field: alarm_threshold, value: 8169.77}
---

# WO-1004 — Engine 12 Core Overspeed Advisory

**Engine:** 12 **Date:** 2026-04-15 **Raised by:** trend review
**Fault code:** FC-HPC-001 (suspected, pending HPC confirmation)

## Observation
Engine 12's physical core speed (Nc) reached 9093.5 rpm, just above the **9092.00 rpm**
alarm threshold, with corrected core speed (NRc) at 8171.0 rpm, above its **8169.77
rpm** threshold. Rising core speed is a system-level symptom: the core is compensating
for gas-path efficiency loss.

## Action taken
Localized the cause by reviewing HPC parameters — T30 and Ps30 found trending upward,
consistent with early HPC degradation. Raised FC-HPC-001 as the underlying cause and
reduced HPC inspection interval.

## Status
Open — core speed is the symptom; HPC is the root cause. Tracking under FC-HPC-001.
