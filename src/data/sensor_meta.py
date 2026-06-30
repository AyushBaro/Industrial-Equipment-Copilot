"""Canonical CMAPSS 21-sensor mapping.

Source: Saxena, Goebel, Simon & Eklund, "Damage Propagation Modeling for Aircraft
Engine Run-to-Failure Simulation" (PHM08) — the paper bundled at
Data/raw/CMAPSSData/Damage Propagation Modeling.pdf.

This is the single definition of what each sensor *is* and which engine subsystem it
belongs to. The asset hierarchy and the maintenance corpus both build on it.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Sensor:
    sensor_id: int          # 1..21, matches column sensor_{id}
    symbol: str             # engineering symbol, e.g. "T30"
    description: str
    unit: str
    subsystem: str          # asset-hierarchy node it rolls up to


# Subsystems present in the turbofan asset hierarchy (FD001 fault mode: HPC degradation)
SUBSYSTEMS = ["Fan", "LPC", "HPC", "Combustor", "HPT", "LPT", "Core", "Engine"]

SENSORS: list[Sensor] = [
    Sensor(1,  "T2",        "Total temperature at fan inlet",        "degR",    "Fan"),
    Sensor(2,  "T24",       "Total temperature at LPC outlet",       "degR",    "LPC"),
    Sensor(3,  "T30",       "Total temperature at HPC outlet",       "degR",    "HPC"),
    Sensor(4,  "T50",       "Total temperature at LPT outlet",       "degR",    "LPT"),
    Sensor(5,  "P2",        "Pressure at fan inlet",                 "psia",    "Fan"),
    Sensor(6,  "P15",       "Total pressure in bypass duct",         "psia",    "Fan"),
    Sensor(7,  "P30",       "Total pressure at HPC outlet",          "psia",    "HPC"),
    Sensor(8,  "Nf",        "Physical fan speed",                    "rpm",     "Fan"),
    Sensor(9,  "Nc",        "Physical core speed",                   "rpm",     "Core"),
    Sensor(10, "epr",       "Engine pressure ratio (P50/P2)",        "ratio",   "Engine"),
    Sensor(11, "Ps30",      "Static pressure at HPC outlet",         "psia",    "HPC"),
    Sensor(12, "phi",       "Ratio of fuel flow to Ps30",            "pps/psi", "HPC"),
    Sensor(13, "NRf",       "Corrected fan speed",                   "rpm",     "Fan"),
    Sensor(14, "NRc",       "Corrected core speed",                  "rpm",     "Core"),
    Sensor(15, "BPR",       "Bypass ratio",                          "ratio",   "Fan"),
    Sensor(16, "farB",      "Burner fuel-air ratio",                 "ratio",   "Combustor"),
    Sensor(17, "htBleed",   "Bleed enthalpy",                        "index",   "Engine"),
    Sensor(18, "Nf_dmd",    "Demanded fan speed",                    "rpm",     "Fan"),
    Sensor(19, "PCNfR_dmd", "Demanded corrected fan speed",          "rpm",     "Fan"),
    Sensor(20, "W31",       "HPT coolant bleed",                     "lbm/s",   "HPT"),
    Sensor(21, "W32",       "LPT coolant bleed",                     "lbm/s",   "LPT"),
]

SENSOR_BY_ID: dict[int, Sensor] = {s.sensor_id: s for s in SENSORS}


def sensor_column(sensor_id: int) -> str:
    return f"sensor_{sensor_id}"
