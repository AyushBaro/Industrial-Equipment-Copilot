---
id: manual-combustor
type: manual
title: Combustor Operation & Maintenance Manual
subsystem: Combustor
cites_sensors: [16]
assertions: []
---

# Combustor — Operation & Maintenance Manual

## 1. Overview
The combustor burns metered fuel with HPC discharge air to drive the turbines. In this
fleet (FD001), the burner fuel-air ratio (farB, sensor 16) is held essentially
constant at **0.03** by the fuel control and shows no measurable degradation trend. It
is therefore monitored for fault annunciation only, not for trend-based prognostics.

## 2. Monitored parameters
| Sensor | Symbol | Quantity | Behaviour |
|--------|--------|----------|-----------|
| 16 | farB | Burner fuel-air ratio (–) | Constant ≈ 0.03; non-informative for trending |

## 3. Inspection interval
Borescope inspection of combustor liner and fuel nozzles every **45 operational
cycles**, or on any step change in farB outside controller tolerance.

## 4. Alarm response
Because farB is regulated to a fixed setpoint, treat **any sustained departure from
0.03** as a fuel-metering or sensor fault rather than gradual wear. Combustor distress
in this fleet is more reliably inferred from downstream turbine temperatures (T50,
sensor 4) than from farB itself.
