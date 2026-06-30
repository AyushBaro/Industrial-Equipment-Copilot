---
id: manual-hpt
type: manual
title: High-Pressure Turbine (HPT) Operation & Maintenance Manual
subsystem: HPT
cites_sensors: [20]
assertions:
  - {sensor_id: 20, field: nominal_min, value: 38.64}
  - {sensor_id: 20, field: nominal_max, value: 39.22}
  - {sensor_id: 20, field: alarm_threshold, value: 38.35}
---

# High-Pressure Turbine (HPT) — Operation & Maintenance Manual

## 1. Overview
The high-pressure turbine extracts work from the combustor exhaust to drive the HPC.
Its health is tracked through the HPT coolant bleed flow (W31), which **falls** as
seal wear and clearance changes alter the cooling circuit.

## 2. Monitored parameters
| Sensor | Symbol | Quantity | Nominal range | Alarm |
|--------|--------|----------|---------------|-------|
| 20 | W31 | HPT coolant bleed (lbm/s) | 38.64 – 39.22 | ≤ 38.35 (low) |

## 3. Inspection interval
HPT clearance and seal inspection every **30 operational cycles**, aligned with the
HPC schedule since the two are mechanically coupled on the high-pressure shaft.

## 4. Alarm response
- **W31 ≤ 38.35 lbm/s:** declining HPT coolant bleed. Inspect coolant passages and
  high-pressure shaft seals. A simultaneous decline in LPT coolant bleed (W32, sensor
  21) points to a shared cooling-supply problem rather than an isolated HPT fault.
