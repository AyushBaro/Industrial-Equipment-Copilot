"""Phase 4 tests — the golden eval set stays well-formed and grounded.

These are durable invariants that survive human review (approving/editing rows): the
file validates, it's the right size/balance, and every telemetry source it references
is a runnable query against real data. All offline, no API.
"""
from __future__ import annotations

import re

from src.eval.validate_golden import load_rows, validate
from src.rag import timeseries as ts

_TELE = re.compile(r"^telemetry:engine(\d+)/(sensor(\d+)|all|overview)")


def test_golden_validates():
    assert validate() == []


def test_size_and_balance():
    rows = load_rows()
    assert len(rows) >= 50
    by_route = {}
    for r in rows:
        by_route[r["route"]] = by_route.get(r["route"], 0) + 1
    assert by_route.get("doc", 0) >= 15
    assert by_route.get("timeseries", 0) >= 15
    assert by_route.get("fusion", 0) >= 15
    assert by_route.get("out_of_scope", 0) >= 10


def test_ids_unique():
    ids = [r["id"] for r in load_rows()]
    assert len(ids) == len(set(ids))


def test_telemetry_sources_are_runnable():
    """Every telemetry source referenced must map to a tool call that returns ok=True."""
    for r in load_rows():
        for s in r["expected_sources"]:
            if not s.startswith("telemetry:"):
                continue
            m = _TELE.match(s)
            assert m, f"{r['id']}: unparseable handle {s}"
            engine = int(m.group(1))
            if m.group(2) == "overview":
                assert ts.engine_overview(engine)["ok"], f"{r['id']}: overview not runnable"
            elif m.group(2) == "all":
                assert ts.sensor_status(engine)["ok"], f"{r['id']}: all-status not runnable"
            else:
                sensor = int(m.group(3))
                assert ts.sensor_status(engine, sensor)["ok"], f"{r['id']}: sensor status not runnable"
