"""Phase 1 acceptance tests — the definition-of-done gate.

Green suite == Phase 1 complete: FD001 loaded correctly, flat sensors detected,
asset hierarchy sound, and the maintenance corpus consistent with that hierarchy.
"""
from __future__ import annotations

import json

from src import config
from src.docs_gen.validate_corpus import errors_summary, validate

# Canonical FD001 result: sensors held constant by the controller carry no signal.
EXPECTED_FLAT = [1, 5, 6, 10, 16, 18, 19]


# 1 — Train table loads with the right shape and no nulls.
def test_train_table_shape(con):
    n_engines = con.execute(
        f"SELECT COUNT(DISTINCT unit_number) FROM {config.TABLE_TRAIN}"
    ).fetchone()[0]
    n_rows = con.execute(f"SELECT COUNT(*) FROM {config.TABLE_TRAIN}").fetchone()[0]
    n_cols = len(con.execute(f"SELECT * FROM {config.TABLE_TRAIN} LIMIT 0").description)
    assert n_engines == 100
    assert n_cols == 26
    assert n_rows > 20000

    # no nulls anywhere
    total_nulls = con.execute(
        "SELECT SUM(nulls) FROM ("
        + " UNION ALL ".join(
            f"SELECT COUNT(*) - COUNT({c}) AS nulls FROM {config.TABLE_TRAIN}"
            for c in config.COLUMNS
        )
        + ")"
    ).fetchone()[0]
    assert total_nulls == 0


# 2 — Test + RUL tables cover all 100 test engines.
def test_test_and_rul_tables(con):
    n_test = con.execute(
        f"SELECT COUNT(DISTINCT unit_number) FROM {config.TABLE_TEST}"
    ).fetchone()[0]
    n_rul = con.execute(f"SELECT COUNT(*) FROM {config.TABLE_RUL}").fetchone()[0]
    assert n_test == 100
    assert n_rul == 100
    # every test engine has a RUL row
    missing = con.execute(
        f"SELECT COUNT(*) FROM (SELECT DISTINCT unit_number FROM {config.TABLE_TEST}) t "
        f"LEFT JOIN {config.TABLE_RUL} r USING (unit_number) WHERE r.rul IS NULL"
    ).fetchone()[0]
    assert missing == 0


# 3 — Column names match the canonical schema exactly.
def test_schema_columns(con):
    cols = [d[0] for d in con.execute(
        f"SELECT * FROM {config.TABLE_TRAIN} LIMIT 0"
    ).description]
    assert cols == config.COLUMNS


# 4 — A representative time-series query works.
def test_timeseries_query(con):
    rows = con.execute(
        f"""
        SELECT time_in_cycles, sensor_4
        FROM {config.TABLE_TRAIN}
        WHERE unit_number = 1
        ORDER BY time_in_cycles DESC
        LIMIT 50
        """
    ).fetchall()
    assert 0 < len(rows) <= 50
    cycles = [r[0] for r in rows]
    assert cycles == sorted(cycles, reverse=True)  # ordered


# 5 — Flat-sensor detection is correct and deterministic.
def test_flat_sensor_detection():
    res = json.loads(config.FLAT_SENSORS_JSON.read_text())
    assert res["flat_sensor_ids"] == EXPECTED_FLAT
    assert len(res["flat_sensor_ids"]) >= 1
    # deterministic: recomputing yields the same set
    from src.data.detect_flat_sensors import compute_flat_sensors

    assert compute_flat_sensors()["flat_sensor_ids"] == EXPECTED_FLAT


# 6 — Asset hierarchy is complete and well-formed.
def test_asset_hierarchy(hierarchy):
    assert len(hierarchy) == 21
    assert set(hierarchy["sensor_id"]) == set(range(1, 22))
    assert hierarchy["subsystem"].notna().all()
    # nominal_min <= nominal_max everywhere
    assert (hierarchy["nominal_min"] <= hierarchy["nominal_max"]).all()
    # informative sensors have an alarm threshold + direction; flat ones don't
    info = hierarchy[hierarchy["is_informative"]]
    flat = hierarchy[~hierarchy["is_informative"]]
    assert info["alarm_threshold"].notna().all()
    assert info["alarm_direction"].isin(["high", "low"]).all()
    assert flat["alarm_direction"].eq("none").all()
    assert sorted(flat["sensor_id"]) == EXPECTED_FLAT


# 7 — KEY TEST: every value the corpus asserts matches the hierarchy.
def test_corpus_consistency():
    docs = validate()
    bad = errors_summary(docs)
    assert bad == {}, f"corpus inconsistencies: {bad}"


# 8 — Corpus is the expected size with valid, typed front-matter.
def test_corpus_structure():
    docs = validate()
    assert 15 <= len(docs) <= 20
    types = {"manual", "fault_code", "work_order"}
    for d in docs:
        assert d.meta.get("type") in types
        assert d.meta.get("id")
        assert d.meta.get("title")
        assert isinstance(d.meta.get("cites_sensors"), list)
    # we expect a spread across all three document types
    present = {d.meta["type"] for d in docs}
    assert present == types
