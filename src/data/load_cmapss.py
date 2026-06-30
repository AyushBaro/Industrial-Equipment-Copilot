"""Load CMAPSS FD001 (train, test, RUL) into DuckDB.

Run as a module:  python -m src.data.load_cmapss
"""
from __future__ import annotations

import duckdb
import pandas as pd

from src import config


def _read_readings(path) -> pd.DataFrame:
    """Parse a space-delimited CMAPSS readings file into the canonical 26 columns.

    The files use variable whitespace and often have trailing spaces that produce
    phantom empty columns, so we split on any whitespace and keep the first 26 fields.
    """
    df = pd.read_csv(path, sep=r"\s+", header=None, engine="python")
    # Drop any all-NaN trailing columns produced by trailing whitespace.
    df = df.dropna(axis=1, how="all")
    if df.shape[1] != len(config.COLUMNS):
        raise ValueError(
            f"{path.name}: expected {len(config.COLUMNS)} columns, got {df.shape[1]}"
        )
    df.columns = config.COLUMNS
    df["unit_number"] = df["unit_number"].astype(int)
    df["time_in_cycles"] = df["time_in_cycles"].astype(int)
    return df


def _read_rul(path) -> pd.DataFrame:
    """RUL file: one true remaining-useful-life value per test engine, in order."""
    rul = pd.read_csv(path, sep=r"\s+", header=None, engine="python").dropna(axis=1, how="all")
    rul = rul.iloc[:, 0].astype(int).reset_index(drop=True)
    return pd.DataFrame({"unit_number": rul.index + 1, "rul": rul.values})


def build_database(db_path=None) -> str:
    """(Re)build the DuckDB database from the raw FD001 files. Returns the path."""
    config.ensure_build_dir()
    db_path = str(db_path or config.DUCKDB_PATH)

    train = _read_readings(config.TRAIN_FILE)
    test = _read_readings(config.TEST_FILE)
    rul = _read_rul(config.RUL_FILE)

    con = duckdb.connect(db_path)
    try:
        for table, frame in (
            (config.TABLE_TRAIN, train),
            (config.TABLE_TEST, test),
            (config.TABLE_RUL, rul),
        ):
            con.register("frame", frame)
            con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM frame")
            con.unregister("frame")
    finally:
        con.close()
    return db_path


def connect(db_path=None, read_only: bool = True):
    return duckdb.connect(str(db_path or config.DUCKDB_PATH), read_only=read_only)


if __name__ == "__main__":
    path = build_database()
    con = connect(path)
    n_engines = con.execute(
        f"SELECT COUNT(DISTINCT unit_number) FROM {config.TABLE_TRAIN}"
    ).fetchone()[0]
    n_rows = con.execute(f"SELECT COUNT(*) FROM {config.TABLE_TRAIN}").fetchone()[0]
    con.close()
    print(f"Built {path}: {n_engines} train engines, {n_rows} rows.")
