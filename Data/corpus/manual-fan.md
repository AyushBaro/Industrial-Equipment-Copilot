---
id: manual-fan
type: manual
title: Fan Module Operation & Maintenance Manual
subsystem: Fan
cites_sensors: [1, 5, 6, 8, 13, 15, 18, 19]
assertions:
  - {sensor_id: 8, field: nominal_min, value: 2387.94}
  - {sensor_id: 8, field: nominal_max, value: 2388.18}
  - {sensor_id: 8, field: alarm_threshold, value: 2388.30}
  - {sensor_id: 13, field: nominal_max, value: 2388.17}
  - {sensor_id: 13, field: alarm_threshold, value: 2388.28}
  - {sensor_id: 15, field: nominal_min, value: 8.36}
  - {sensor_id: 15, field: nominal_max, value: 8.48}
  - {sensor_id: 15, field: alarm_threshold, value: 8.54}
---

# Fan Module — Operation & Maintenance Manual

## 1. Overview
The fan provides bypass thrust and feeds the core. Under the single sea-level
operating condition of this fleet (FD001), several fan-related channels are held
effectively constant by the control system and carry **no degradation signal**:
fan inlet temperature (T2, sensor 1), fan inlet pressure (P2, sensor 5), bypass-duct
pressure (P15, sensor 6), demanded fan speed (Nf_dmd, sensor 18) and demanded
corrected fan speed (PCNfR_dmd, sensor 19). These are recorded for completeness but
are **excluded from trend monitoring**.

## 2. Monitored parameters (informative)
| Sensor | Symbol | Quantity | Nominal range | Alarm |
|--------|--------|----------|---------------|-------|
| 8  | Nf  | Physical fan speed (rpm)   | 2387.94 – 2388.18 | ≥ 2388.30 (high) |
| 13 | NRf | Corrected fan speed (rpm)  | 2387.94 – 2388.17 | ≥ 2388.28 (high) |
| 15 | BPR | Bypass ratio (–)           | 8.36 – 8.48       | ≥ 8.54 (high)    |

## 3. Inspection interval
Fan blade and containment inspection every **50 operational cycles**. Because the fan
is not the primary fault mode in this fleet, routine intervals are longer than for the
HPC.

## 4. Alarm response
- **BPR ≥ 8.54:** rising bypass ratio indicates the core is passing less of the
  total flow — often a secondary symptom of core/HPC degradation rather than a fan
  fault. Correlate with HPC parameters before attributing to the fan.
- **Nf ≥ 2388.30 rpm / NRf ≥ 2388.28 rpm:** physical and corrected fan speed creeping
  above nominal. Confirm against demanded fan speed; a gap suggests control-loop drift.
