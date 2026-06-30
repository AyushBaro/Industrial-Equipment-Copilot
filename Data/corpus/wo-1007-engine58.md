---
id: wo-1007-engine58
type: work_order
title: "WO-1007 — Engine 58 rising bleed enthalpy"
subsystem: Engine
engine: 58
date: 2026-05-13
fault_code: FC-HPC-001
cites_sensors: [17, 3]
assertions:
  - {sensor_id: 17, field: alarm_threshold, value: 397.50}
  - {sensor_id: 3, field: alarm_threshold, value: 1607.89}
---

# WO-1007 — Engine 58 Rising Bleed Enthalpy

**Engine:** 58 **Date:** 2026-05-13 **Raised by:** prognostics review
**Fault code:** FC-HPC-001

## Observation
Engine 58's bleed enthalpy (htBleed) reached 398.1, above the **397.50** alarm
threshold, accompanied by HPC discharge temperature (T30) at 1608.7 degR, over its
**1607.89 degR** threshold. Rising bleed enthalpy plus rising T30 is a strong late-life
HPC-degradation indicator.

## Action taken
Raised FC-HPC-001. Compressor wash performed; began close RUL tracking given the
combined late-life signature. Recommended end-of-life planning review.

## Status
Open — late-life engine; T30 and htBleed both in alarm. Prioritized for removal planning.
