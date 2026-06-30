---
id: manual-lpt
type: manual
title: Low-Pressure Turbine (LPT) Operation & Maintenance Manual
subsystem: LPT
cites_sensors: [4, 21]
assertions:
  - {sensor_id: 4, field: nominal_min, value: 1390.08}
  - {sensor_id: 4, field: nominal_max, value: 1415.43}
  - {sensor_id: 4, field: alarm_threshold, value: 1428.11}
  - {sensor_id: 21, field: nominal_min, value: 23.18}
  - {sensor_id: 21, field: nominal_max, value: 23.53}
  - {sensor_id: 21, field: alarm_threshold, value: 23.00}
---

# Low-Pressure Turbine (LPT) — Operation & Maintenance Manual

## 1. Overview
The low-pressure turbine drives the fan and LPC. LPT degradation appears as a
**rising LPT outlet temperature** (T50) — the stage extracts work less efficiently, so
exhaust gas runs hotter — often accompanied by a **falling LPT coolant bleed** (W32).

## 2. Monitored parameters
| Sensor | Symbol | Quantity | Nominal range | Alarm |
|--------|--------|----------|---------------|-------|
| 4  | T50 | LPT outlet total temperature (degR) | 1390.08 – 1415.43 | ≥ 1428.11 (high) |
| 21 | W32 | LPT coolant bleed (lbm/s)           | 23.18 – 23.53     | ≤ 23.00 (low)    |

## 3. Inspection interval
LPT gas-path and exhaust inspection every **35 operational cycles**.

## 4. Alarm response
- **T50 ≥ 1428.11 degR:** LPT over-temperature. Inspect for blade distress and
  exhaust-path blockage. Persistent high T50 is a leading indicator of end-of-life in
  engines whose primary degradation has propagated downstream.
- **W32 ≤ 23.00 lbm/s:** falling LPT coolant bleed; inspect the cooling circuit and
  cross-check W31 (sensor 20) for a shared supply fault. See fault code FC-LPT-001.
