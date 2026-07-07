"""Phase 5 — regression gate.

Offline (free): the scorer's own logic — source normalization, metric math, Cohen's
kappa — so a broken scorer can't silently report green.

Live (RUN_LLM_TESTS=1, spends a few cents): score the current system against the golden
answer key and fail if any metric drops below its regression floor/ceiling, plus per-row
canaries that guard the three Phase-5 fixes so those exact bugs cannot creep back:
  - Fix 1 (synthesizer over-abstention): g003 answers with the T50 threshold, not "I
    don't have enough information".
  - Fix 2 (type-aware fusion retrieval): the flagship g031 cites a manual/fault-code.
  - Fix 3 (router intent + scope): g005 routes doc (not out_of_scope); g031 uses the
    status tool (not trend).

Run the gate: `make eval-gate` (or RUN_LLM_TESTS=1 pytest tests/test_phase5.py).
"""
from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv

from src.eval import score

load_dotenv()
RUN_LLM = os.environ.get("RUN_LLM_TESTS") == "1" and bool(os.environ.get("OPENAI_API_KEY"))
live = pytest.mark.skipif(not RUN_LLM, reason="set RUN_LLM_TESTS=1 (and OPENAI_API_KEY) for live tests")


# ---- Offline: the scorer must not lie -------------------------------------

def test_normalize_source_strips_telemetry_params():
    # trend/status handles carry params the golden labels omit; both must canonicalize
    assert score.normalize_source("telemetry:engine23/sensor4/trend(last_n=50)") \
        == "telemetry:engine23/sensor4/trend"
    assert score.normalize_source("telemetry:engine47/sensor11/status@cycle214") \
        == "telemetry:engine47/sensor11/status"
    assert score.normalize_source("manual-hpc") == "manual-hpc"  # doc ids pass through


def test_deterministic_metrics_on_perfect_predictions():
    rows = score.load_approved()
    preds = [{"id": r["id"], "route": r["route"], "abstained": r.get("answerable") is False,
              "retrieved": [score.normalize_source(s) for s in r["expected_sources"]],
              "answer": "x", "sources_text": []} for r in rows]
    metrics = {m.name: m.value for m in score.score_run(rows, preds, judge=False)[0]}
    assert metrics["routing_accuracy"] == 1.0
    assert metrics["retrieval_recall@k"] == 1.0
    assert metrics["abstention_correct"] == 1.0
    assert metrics["over_abstention"] == 0.0


def test_cohen_kappa_bounds():
    from src.eval.validate_judge import cohen_kappa
    assert cohen_kappa([(True, True), (False, False)]) == 1.0          # perfect
    assert cohen_kappa([(True, False), (False, True)]) == pytest.approx(-1.0)  # opposite
    assert cohen_kappa([]) is None


def test_load_runs_tolerates_legacy_flat_format(tmp_path):
    import json
    p = tmp_path / "preds.json"
    p.write_text(json.dumps([{"id": "g001"}]))          # legacy single-run flat list
    assert score.load_runs(p) == [[{"id": "g001"}]]
    p.write_text(json.dumps([[{"id": "g001"}]]))        # new list-of-runs
    assert score.load_runs(p) == [[{"id": "g001"}]]


# ---- Live: metric floors + per-fix canaries -------------------------------

@pytest.fixture(scope="module")
def live_predictions():
    """One pipeline pass over the golden set, shared by the live gate tests."""
    from src.rag.embed_store import build_index

    build_index()
    rows = score.load_approved()
    preds = score.run_predictions(rows, runs=1)[0]
    return rows, {p["id"]: p for p in preds}


@live
def test_no_metric_regression(live_predictions):
    rows, by_id = live_predictions
    preds = [by_id[r["id"]] for r in rows]
    metrics = {m.name: m.value for m in score.score_run(rows, preds, judge=False)[0]}
    for name, floor in score.REGRESSION_FLOORS.items():
        assert metrics[name] >= floor, f"{name} {metrics[name]:.3f} < floor {floor}"
    for name, ceil in score.REGRESSION_CEILINGS.items():
        assert metrics[name] <= ceil, f"{name} {metrics[name]:.3f} > ceiling {ceil}"


@live
def test_fix1_canary_synthesizer_answers_with_context(live_predictions):
    # g003: T50 threshold sits in retrieved manual-lpt — must answer, not abstain.
    _, by_id = live_predictions
    g003 = by_id["g003"]
    assert not g003["abstained"], "g003 abstained despite the answer being in context"
    assert "1428.11" in g003["answer"], g003["answer"]


@live
def test_fix2_canary_fusion_cites_canonical_doc(live_predictions):
    # g031: the canonical manual/fault-code must be retrieved and cited (not just work orders).
    _, by_id = live_predictions
    cites = by_id["g031"]["citations"]
    canonical = [c for c in cites if c.startswith("manual-") or c.startswith("fault-")]
    assert canonical, f"g031 cited no manual/fault-code: {cites}"


@live
def test_fix3_canary_router_intent_and_scope(live_predictions):
    _, by_id = live_predictions
    # scope: a conceptual in-scope doc question must not be dismissed as out_of_scope
    assert by_id["g005"]["route"] == "doc", by_id["g005"]["route"]
    # intent: the alarm-style fusion question must use the status tool, not trend
    tel = [c for c in by_id["g031"]["citations"] if c.startswith("telemetry:")]
    assert any("/status" in c for c in tel), f"g031 telemetry not status: {tel}"
