"""Central paths and constants for the Industrial Equipment RAG Copilot."""
from __future__ import annotations

from pathlib import Path

# --- Roots -------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = ROOT / "Data" / "raw" / "CMAPSSData"
CORPUS_DIR = ROOT / "Data" / "corpus"
BUILD_DIR = ROOT / "build"

# --- Generated artifacts -----------------------------------------------------
DUCKDB_PATH = BUILD_DIR / "cmapss.duckdb"
ASSET_HIERARCHY_CSV = BUILD_DIR / "asset_hierarchy.csv"
FLAT_SENSORS_JSON = BUILD_DIR / "flat_sensors.json"

# --- CMAPSS (Phase 1 uses FD001 only) ---------------------------------------
DATASET = "FD001"
TRAIN_FILE = DATA_RAW / f"train_{DATASET}.txt"
TEST_FILE = DATA_RAW / f"test_{DATASET}.txt"
RUL_FILE = DATA_RAW / f"RUL_{DATASET}.txt"

N_SENSORS = 21
N_OP_SETTINGS = 3

# Column order in the raw space-delimited files (26 columns, no header).
COLUMNS = (
    ["unit_number", "time_in_cycles"]
    + [f"op_setting_{i}" for i in range(1, N_OP_SETTINGS + 1)]
    + [f"sensor_{i}" for i in range(1, N_SENSORS + 1)]
)
SENSOR_COLUMNS = [f"sensor_{i}" for i in range(1, N_SENSORS + 1)]

# DuckDB table names
TABLE_TRAIN = "sensor_readings"
TABLE_TEST = "sensor_readings_test"
TABLE_RUL = "rul_test"


def ensure_build_dir() -> None:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
