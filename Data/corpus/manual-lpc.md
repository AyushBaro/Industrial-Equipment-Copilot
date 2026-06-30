---
id: manual-lpc
type: manual
title: Low-Pressure Compressor (LPC) Operation & Maintenance Manual
subsystem: LPC
cites_sensors: [2]
assertions:
  - {sensor_id: 2, field: nominal_min, value: 641.54}
  - {sensor_id: 2, field: nominal_max, value: 643.28}
  - {sensor_id: 2, field: alarm_threshold, value: 644.15}
---

# Low-Pressure Compressor (LPC) — Operation & Maintenance Manual

## 1. Overview
The low-pressure compressor (booster) raises airflow pressure between the fan and the
HPC. Its health is tracked primarily through the LPC outlet total temperature, which
rises as booster efficiency degrades.

## 2. Monitored parameters
| Sensor | Symbol | Quantity | Nominal range | Alarm |
|--------|--------|----------|---------------|-------|
| 2 | T24 | LPC outlet total temperature (degR) | 641.54 – 643.28 | ≥ 644.15 (high) |

## 3. Inspection interval
Combined gas-path inspection every **40 operational cycles**; the LPC is typically
inspected alongside the HPC because the two share the core gas path.

## 4. Alarm response
- **T24 ≥ 644.15 degR:** rising LPC discharge temperature. On its own this is usually
  mild; if it accompanies an HPC alarm (see FC-HPC-001) treat it as confirmation of
  core gas-path degradation rather than an isolated LPC fault.
