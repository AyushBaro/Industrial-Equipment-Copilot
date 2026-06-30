---
id: fault-FC-HPC-001
type: fault_code
title: "FC-HPC-001 — High-Pressure Compressor Degradation"
subsystem: HPC
cites_sensors: [3, 7, 11, 12, 9, 17]
assertions:
  - {sensor_id: 3, field: alarm_threshold, value: 1607.89}
  - {sensor_id: 11, field: alarm_threshold, value: 48.10}
  - {sensor_id: 7, field: alarm_threshold, value: 551.16}
  - {sensor_id: 12, field: alarm_threshold, value: 519.69}
  - {sensor_id: 9, field: alarm_threshold, value: 9092.00}
  - {sensor_id: 17, field: alarm_threshold, value: 397.50}
---

# FC-HPC-001 — High-Pressure Compressor Degradation

## Description
Progressive loss of HPC efficiency. This is the primary run-to-failure mode in the
fleet. As compressor stages foul and tip clearances open up, the HPC must run hotter
and at higher static pressure to hold its operating point, while recoverable total
pressure and the fuel-flow ratio fall.

## Primary signature (all should be present to raise the code)
| Sensor | Symbol | Direction | Alarm condition |
|--------|--------|-----------|-----------------|
| 3  | T30  | rising  | ≥ 1607.89 degR |
| 11 | Ps30 | rising  | ≥ 48.10 psia   |
| 7  | P30  | falling | ≤ 551.16 psia  |
| 12 | phi  | falling | ≤ 519.69 pps/psi |

## Secondary / confirming indicators
- Core speed Nc rising toward **9092.00 rpm** as the core compensates for lost efficiency.
- Bleed enthalpy htBleed rising toward **397.50** as overall core temperatures climb.

## Procedure
1. Confirm the primary signature on at least the last 5 operational cycles (suppress
   single-cycle noise spikes).
2. Reduce HPC borescope inspection interval to every 10 cycles.
3. Perform a compressor wash; re-baseline T30 and Ps30 after the wash.
4. If T30 and Ps30 remain in alarm after wash, schedule HPC module removal at the next
   maintenance opportunity and begin RUL tracking for end-of-life planning.
5. Check whether T50 (LPT) has also entered alarm — co-occurrence indicates
   degradation has propagated and shortens the remaining-useful-life estimate.
