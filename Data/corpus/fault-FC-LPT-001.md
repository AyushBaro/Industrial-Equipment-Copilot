---
id: fault-FC-LPT-001
type: fault_code
title: "FC-LPT-001 — Low-Pressure Turbine Thermal Degradation"
subsystem: LPT
cites_sensors: [4, 21]
assertions:
  - {sensor_id: 4, field: alarm_threshold, value: 1428.11}
  - {sensor_id: 21, field: alarm_threshold, value: 23.00}
---

# FC-LPT-001 — Low-Pressure Turbine Thermal Degradation

## Description
Loss of LPT efficiency, typically appearing later in life and often downstream of HPC
degradation. The turbine extracts work less effectively, so exhaust gas temperature
rises; coolant bleed flow falls as the cooling circuit is affected.

## Primary signature
| Sensor | Symbol | Direction | Alarm condition |
|--------|--------|-----------|-----------------|
| 4  | T50 | rising  | ≥ 1428.11 degR |
| 21 | W32 | falling | ≤ 23.00 lbm/s  |

## Procedure
1. Confirm sustained T50 rise over at least 5 cycles, with W32 trending down.
2. Inspect LPT blades and exhaust path for distress and blockage.
3. Inspect the LPT coolant circuit; if W31 (HPT coolant, sensor 20) is also low,
   treat as a shared cooling-supply fault rather than an isolated LPT problem.
4. When FC-LPT-001 co-occurs with FC-HPC-001, prioritize end-of-life planning — the
   combination is a strong late-life indicator.
