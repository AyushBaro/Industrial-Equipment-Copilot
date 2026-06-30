---
id: wo-1008-engine05
type: work_order
title: "WO-1008 — Engine 5 HPT coolant-bleed decline"
subsystem: HPT
engine: 5
date: 2026-05-26
fault_code: FC-HPT-001
cites_sensors: [20]
assertions:
  - {sensor_id: 20, field: alarm_threshold, value: 38.35}
  - {sensor_id: 20, field: nominal_min, value: 38.64}
---

# WO-1008 — Engine 5 HPT Coolant-Bleed Decline

**Engine:** 5 **Date:** 2026-05-26 **Raised by:** line monitoring
**Fault code:** FC-HPT-001

## Observation
Engine 5's HPT coolant bleed (W31) declined to 38.30 lbm/s, below the **38.35 lbm/s**
low alarm threshold and under the **38.64** nominal minimum. LPT coolant bleed (W32)
remained nominal, so this was treated as an HPT-local cooling issue, not a shared
supply fault.

## Action taken
Inspected HPT coolant passages and high-pressure shaft seals; found seal wear
consistent with reduced bleed flow. Scheduled seal service at next opportunity.

## Status
Open — HPT seal service pending; monitor W31 and watch W32 for any shared-supply signature.
