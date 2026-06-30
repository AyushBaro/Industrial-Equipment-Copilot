"""Phase 3 acceptance tests.

Offline (no API): time-series tools, plan validation, dispatch branch logic, telemetry
citation verification, and out-of-scope abstention (no model call). Live (gated by
RUN_LLM_TESTS=1): router accuracy, timeseries + fusion end-to-end, abstention.
"""
from __future__ import annotations

import json
import os

import pytest
from dotenv import load_dotenv

from src import config
from src.data import load_cmapss
from src.data.asset_hierarchy import load_hierarchy
from src.rag import pipeline, timeseries as ts
from src.rag.router import validate_plan
from src.rag.synthesize import verify_citations

load_dotenv()
RUN_LLM = os.environ.get("RUN_LLM_TESTS") == "1" and bool(os.environ.get("OPENAI_API_KEY"))
live = pytest.mark.skipif(not RUN_LLM, reason="set RUN_LLM_TESTS=1 (and OPENAI_API_KEY) for live tests")


def _seed():
    return [json.loads(l) for l in config.PHASE3_SEED.read_text().splitlines() if l.strip()]


# ---- Offline: time-series tools -------------------------------------------

def test_sensor_trend_shape_and_order():
    r = ts.sensor_trend(23, 4, last_n=50)
    assert r["ok"] and len(r["series"]) <= 50
    cycles = [p["cycle"] for p in r["series"]]
    assert cycles == sorted(cycles)  # chronological
    assert r["direction"] in {"rising", "falling", "flat"}
    assert "telemetry:engine23/sensor4" in r["query_handle"]


def test_sensor_status_threshold_logic():
    # engine 47 at its last cycle: Ps30 (11) is a known HPC-degradation alarm.
    hot = ts.sensor_status(47, 11)
    s = hot["statuses"][0]
    assert s["in_alarm"] is True
    assert s["value"] >= s["alarm_threshold"]            # 'high' direction
    # early life: same sensor should be nominal
    cold = ts.sensor_status(47, 11, at_cycle=1)
    assert cold["statuses"][0]["in_alarm"] is False


def test_sensor_status_matches_hierarchy_independently():
    # Recompute in-alarm independently from the raw row + hierarchy, compare to the tool.
    hier = load_hierarchy().set_index("sensor_id")
    con = load_cmapss.connect()
    cyc = con.execute(f"SELECT MAX(time_in_cycles) FROM {config.TABLE_TRAIN} WHERE unit_number=47").fetchone()[0]
    row = con.execute(f"SELECT * FROM {config.TABLE_TRAIN} WHERE unit_number=47 AND time_in_cycles=?", [cyc]).df()
    con.close()
    out = {s["sensor"]: s["in_alarm"] for s in ts.sensor_status(47)["statuses"]}
    for sid, in_alarm in out.items():
        thr, direction = hier.loc[sid, "alarm_threshold"], hier.loc[sid, "alarm_direction"]
        val = float(row[f"sensor_{sid}"].iloc[0])
        expected = (direction == "high" and val >= thr) or (direction == "low" and val <= thr)
        assert in_alarm == bool(expected), f"sensor {sid}"


def test_engine_overview_cycle_count():
    con = load_cmapss.connect()
    expected = con.execute(f"SELECT MAX(time_in_cycles) FROM {config.TABLE_TRAIN} WHERE unit_number=1").fetchone()[0]
    con.close()
    assert ts.engine_overview(1)["n_cycles"] == expected


def test_tools_reject_bad_refs():
    assert ts.sensor_trend(999, 4)["ok"] is False
    assert ts.sensor_status(47, 99)["ok"] is False
    assert ts.engine_overview(0)["ok"] is False


# ---- Offline: routing plan validation & dispatch --------------------------

def test_plan_validation_downgrades_unsafe():
    # data query with no engine -> abstain
    p = validate_plan({"route": "timeseries", "engine": None, "sensors": [4], "intent": "trend"})
    assert p["route"] == "out_of_scope" and p["abstain_reason"]
    # out-of-range engine -> rejected (None) -> abstain for a data route
    p2 = validate_plan({"route": "fusion", "engine": 999, "sensors": [11], "intent": "status"})
    assert p2["engine"] is None and p2["route"] == "out_of_scope"
    # invalid sensors filtered out
    p3 = validate_plan({"route": "timeseries", "engine": 23, "sensors": [4, 99], "intent": "trend"})
    assert p3["sensors"] == [4] and p3["route"] == "timeseries"


def test_dispatch_branches_select_right_tools():
    trend = pipeline.run_timeseries({"engine": 23, "sensors": [4], "intent": "trend", "last_n": 50})
    assert len(trend) == 1 and "trend" in trend[0]["query_handle"]
    status = pipeline.run_timeseries({"engine": 47, "sensors": [], "intent": "status", "last_n": None})
    assert len(status) == 1 and "/all/status" in status[0]["query_handle"]
    overview = pipeline.run_timeseries({"engine": 76, "sensors": [], "intent": "overview", "last_n": None})
    assert "overview" in overview[0]["query_handle"]


def test_telemetry_citation_verification():
    assert verify_citations(["TS1", "TS9", "manual-hpc"], {"TS1", "manual-hpc"}) == ["TS1", "manual-hpc"]
    assert verify_citations(["TS2"], {"TS1"}) == []


def test_out_of_scope_abstains_without_api(monkeypatch):
    monkeypatch.setattr(pipeline, "route_question",
                        lambda q: {"route": "out_of_scope", "engine": None, "sensors": [],
                                   "intent": None, "last_n": None, "abstain_reason": "x"})
    res = pipeline.answer("anything")  # must not call any model/embedding
    assert res["abstained"] is True and res["citations"] == [] and res["route"] == "out_of_scope"


# ---- Live (gated) ----------------------------------------------------------

@pytest.fixture(scope="module")
def built_index():
    from src.rag.embed_store import build_index
    build_index()
    yield


@live
def test_router_accuracy_on_seed():
    from src.rag.router import route
    seed = _seed()
    route_hits, engine_hits, engine_total = 0, 0, 0
    for s in seed:
        p = route(s["question"])
        route_hits += int(p["route"] == s["expected_route"])
        if s["expected_engine"] is not None:
            engine_total += 1
            engine_hits += int(p["engine"] == s["expected_engine"])
    assert route_hits / len(seed) >= 0.9, f"routing {route_hits}/{len(seed)}"
    assert engine_hits / engine_total >= 0.9, f"engine extraction {engine_hits}/{engine_total}"


@live
def test_timeseries_end_to_end():
    res = pipeline.answer("What was sensor 4's trend for engine 23 over its last 50 cycles?")
    assert res["route"] == "timeseries" and not res["abstained"]
    assert any(c.startswith("telemetry:") for c in res["citations"])


@live
def test_fusion_end_to_end(built_index):
    res = pipeline.answer(
        "Engine 47 is showing elevated Ps30 readings — is this a known fault pattern, "
        "and what does the manual say to do about it?")
    assert res["route"] == "fusion" and not res["abstained"]
    # Fusion invariant: the answer cites at least one document AND the telemetry.
    # (Citations are verified ⊆ retrieved, so any non-telemetry citation is a real doc.)
    doc_cited = any(not c.startswith("telemetry:") for c in res["citations"])
    tel_cited = any(c.startswith("telemetry:") for c in res["citations"])
    assert doc_cited and tel_cited, res["citations"]


@live
def test_abstention_live():
    assert pipeline.answer("Show me the trend for engine 999.")["abstained"] is True
    assert pipeline.answer("What is the tire pressure of a Boeing 747?")["abstained"] is True
