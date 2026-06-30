---
id: manual-hpc
type: manual
title: High-Pressure Compressor (HPC) Operation & Maintenance Manual
subsystem: HPC
cites_sensors: [3, 7, 11, 12]
assertions:
  - {sensor_id: 3, field: nominal_min, value: 1576.37}
  - {sensor_id: 3, field: nominal_max, value: 1597.38}
  - {sensor_id: 3, field: alarm_threshold, value: 1607.89}
  - {sensor_id: 7, field: nominal_min, value: 552.51}
  - {sensor_id: 7, field: nominal_max, value: 555.21}
  - {sensor_id: 7, field: alarm_threshold, value: 551.16}
  - {sensor_id: 11, field: nominal_max, value: 47.73}
  - {sensor_id: 11, field: alarm_threshold, value: 48.10}
  - {sensor_id: 12, field: nominal_min, value: 520.80}
  - {sensor_id: 12, field: alarm_threshold, value: 519.69}
---

# High-Pressure Compressor (HPC) — Operation & Maintenance Manual

## 1. Overview
The high-pressure compressor raises core airflow pressure before the combustor. HPC
degradation is the dominant failure mode in this fleet (FD001), so the HPC sensor
suite is the primary indicator of remaining useful life. Efficiency loss in the HPC
shows up as **rising discharge temperature**, **rising static discharge pressure**,
and a **falling total discharge pressure and fuel-flow ratio** as the stage works
harder to hold the operating point.

## 2. Monitored parameters
| Sensor | Symbol | Quantity | Nominal range | Alarm |
|--------|--------|----------|---------------|-------|
| 3  | T30  | HPC outlet total temperature (degR) | 1576.37 – 1597.38 | ≥ 1607.89 (high) |
| 7  | P30  | HPC outlet total pressure (psia)    | 552.51 – 555.21   | ≤ 551.16 (low)  |
| 11 | Ps30 | HPC outlet static pressure (psia)   | 46.98 – 47.73     | ≥ 48.10 (high)  |
| 12 | phi  | Fuel-flow / Ps30 ratio (pps/psi)    | 520.80 – 523.01   | ≤ 519.69 (low)  |

## 3. Inspection interval
Borescope inspection of the HPC stages is recommended every **30 operational cycles**
under nominal conditions, reduced to every **10 cycles** once any HPC parameter
crosses its alarm threshold.

## 4. Alarm response
- **T30 ≥ 1607.89 degR:** HPC discharge over-temperature. Inspect for blade fouling,
  tip-clearance loss, and seal wear. Correlate with Ps30 and phi.
- **Ps30 ≥ 48.10 psia** with **P30 ≤ 551.16 psia:** classic HPC efficiency loss
  signature — the stage is generating more static rise but less recoverable total
  pressure. Schedule wash and clearance check.
- **phi ≤ 519.69 pps/psi:** fuel-flow-to-pressure ratio falling; cross-check fuel
  metering and confirm against T30 trend before acting.

When two or more HPC parameters are simultaneously in alarm, raise fault code
**FC-HPC-001** (HPC degradation) and follow that procedure.
