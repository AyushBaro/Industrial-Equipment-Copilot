---
id: manual-core-engine
type: manual
title: Core Shaft & Engine-Level Monitoring Manual
subsystem: Core
cites_sensors: [9, 14, 10, 17]
assertions:
  - {sensor_id: 9, field: nominal_min, value: 9038.00}
  - {sensor_id: 9, field: nominal_max, value: 9074.00}
  - {sensor_id: 9, field: alarm_threshold, value: 9092.00}
  - {sensor_id: 14, field: nominal_min, value: 8120.73}
  - {sensor_id: 14, field: nominal_max, value: 8153.42}
  - {sensor_id: 14, field: alarm_threshold, value: 8169.77}
  - {sensor_id: 17, field: nominal_min, value: 390.00}
  - {sensor_id: 17, field: nominal_max, value: 395.00}
  - {sensor_id: 17, field: alarm_threshold, value: 397.50}
---

# Core Shaft & Engine-Level Monitoring Manual

## 1. Overview
This manual covers shaft speeds and engine-level indicators that span subsystems. Core
speed rises as the engine compensates for gas-path efficiency loss; bleed enthalpy
rises with overall thermal degradation. Engine pressure ratio (epr, sensor 10) is held
constant at **1.30** under FD001 conditions and is non-informative for trending.

## 2. Monitored parameters
| Sensor | Symbol | Quantity | Nominal range | Alarm |
|--------|--------|----------|---------------|-------|
| 9  | Nc      | Physical core speed (rpm)   | 9038.00 – 9074.00 | ≥ 9092.00 (high) |
| 14 | NRc     | Corrected core speed (rpm)  | 8120.73 – 8153.42 | ≥ 8169.77 (high) |
| 17 | htBleed | Bleed enthalpy (index)      | 390.00 – 395.00   | ≥ 397.50 (high)  |
| 10 | epr     | Engine pressure ratio (–)   | constant ≈ 1.30   | non-informative  |

## 3. Inspection interval
Engine-level trend review every **20 operational cycles**; core speeds and bleed
enthalpy are the broadest health indicators and are reviewed most frequently.

## 4. Alarm response
- **Nc ≥ 9092.00 rpm / NRc ≥ 8169.77 rpm:** rising core speed indicates the core is
  working harder to hold thrust — a system-level symptom of gas-path degradation.
  Localize using HPC parameters (FC-HPC-001).
- **htBleed ≥ 397.50:** rising bleed enthalpy reflects increasing core temperatures
  overall; a strong end-of-life indicator when combined with rising T30 and T50.
