---
id: fault-code-reference
type: fault_code
title: Fault Code Reference Index
subsystem: Engine
cites_sensors: [3, 4, 11, 21]
assertions:
  - {sensor_id: 3, field: alarm_threshold, value: 1607.89}
  - {sensor_id: 11, field: alarm_threshold, value: 48.10}
  - {sensor_id: 4, field: alarm_threshold, value: 1428.11}
  - {sensor_id: 21, field: alarm_threshold, value: 23.00}
---

# Fault Code Reference Index

This index maps fault codes to their triggering subsystem, the primary sensor
signature, and the detailed procedure document. Raise a fault code when the listed
primary parameters are simultaneously in alarm.

| Code | Subsystem | Primary signature | Procedure |
|------|-----------|-------------------|-----------|
| FC-HPC-001 | HPC | T30 ≥ 1607.89 degR and Ps30 ≥ 48.10 psia, with falling P30 / phi | see `fault-FC-HPC-001` |
| FC-LPT-001 | LPT | T50 ≥ 1428.11 degR with W32 ≤ 23.00 lbm/s | see `fault-FC-LPT-001` |
| FC-FAN-001 | Fan | BPR above nominal with no corresponding HPC alarm | manual-fan, §4 |
| FC-HPT-001 | HPT | W31 below nominal coolant bleed | manual-hpt, §4 |

## Usage notes
- **HPC degradation (FC-HPC-001) is the dominant fault mode in this fleet.** When in
  doubt, evaluate the HPC signature first.
- A single parameter in alarm is an *advisory*, not a fault. Raise a coded fault only
  when the full primary signature is present, to suppress sensor-noise false alarms.
- Codes are not mutually exclusive: late-life engines frequently show FC-HPC-001 and
  FC-LPT-001 together as degradation propagates downstream.
