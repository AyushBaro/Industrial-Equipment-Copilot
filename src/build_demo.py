
"""Generate the cached demo dataset for the public Streamlit demo (make demo-data).

Runs a curated subset of the golden questions through the real pipeline once and
snapshots the full response (answer, citations, provenance, confidence, cost, latency)
to Data/demo/demo_qa.json. The hosted demo reads that file, so it never needs an API
key and costs nothing to serve — the answers are genuine pipeline output, frozen.

Re-run whenever the pipeline changes materially:  make demo-data
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from src import config
from src.rag.pipeline import answer

# Curated to show the full range: simple lookup → deep procedure → conceptual reasoning;
# trend / alarm / overview telemetry; three fusion answers; and three DISTINCT abstention
# reasons (invalid engine, invalid sensor, off-domain).
DEMO_IDS = [
    "g001", "g011", "g014",   # doc: easy interval · hard procedure · conceptual reasoning
    "g017", "g019", "g021",   # timeseries: trend · alarm status · overview
    "g031", "g043", "g033",   # fusion: flagship (engine 47 Ps30) · T30 procedure · LPT
    "g048", "g055", "g051",   # out-of-scope: invalid engine · invalid sensor · off-domain
]

ROUTE_BLURB = {
    "doc": "Answered from the maintenance corpus.",
    "timeseries": "Answered from live sensor data.",
    "fusion": "Answered from documents and sensor telemetry together.",
    "out_of_scope": "Outside the copilot's knowledge — correctly abstained.",
}


def main() -> None:
    golden = {json.loads(l)["id"]: json.loads(l)
              for l in config.GOLDEN_EVAL.read_text().splitlines() if l.strip()}

    out = []
    for qid in DEMO_IDS:
        g = golden[qid]
        question = g["question"]
        t0 = time.perf_counter()
        r = answer(question)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        usage = r.get("usage", {})
        plan = r.get("plan", {}) or {}
        out.append({
            "id": qid,
            "question": question,
            "route": r.get("route", "out_of_scope"),
            "route_blurb": ROUTE_BLURB.get(r.get("route", ""), ""),
            "difficulty": g.get("difficulty", ""),
            "answer": r.get("answer", ""),
            "citations": r.get("citations", []),
            "contexts": r.get("contexts", []),
            "confidence": r.get("confidence", "low"),
            "abstained": bool(r.get("abstained")),
            "latency_ms": latency_ms,
            "cost_usd": usage.get("cost_usd", 0.0),
            "total_tokens": usage.get("total_tokens", 0),
            "n_calls": usage.get("n_calls", 0),
            # what the router decided (route internals shown in the demo)
            "plan": {k: plan.get(k) for k in ("route", "engine", "sensors", "intent", "rationale")},
            # the exact grounding text the model saw (trimmed) — lets the demo show
            # *what* each answer rests on, not just the source ids.
            "sources_text": [s[:700] for s in r.get("sources_text", [])],
        })
        tag = "ABSTAINED" if out[-1]["abstained"] else f'{len(out[-1]["citations"])} cites'
        print(f'{qid} [{out[-1]["route"]:12}] {tag} · ${out[-1]["cost_usd"]:.5f} · {latency_ms}ms')

    demo_dir = Path(config.ROOT) / "Data" / "demo"
    demo_dir.mkdir(parents=True, exist_ok=True)
    (demo_dir / "demo_qa.json").write_text(json.dumps(out, indent=2))
    total = sum(r["cost_usd"] for r in out)
    print(f"\nWrote {len(out)} demo Q/A → {demo_dir/'demo_qa.json'}  (cost ${total:.4f})")

    # Before/after showcase for the flagship fusion case (g031). "Before" is the cached
    # pre-fix baseline (free — read from the eval report); "after" is this run's g031.
    baseline = json.loads((config.EVAL_DIR / "reports" / "predictions-baseline.json").read_text())
    base_runs = baseline if isinstance(baseline[0], list) else [baseline]
    b31 = next(x for x in base_runs[0] if x.get("id") == "g031")
    a31 = next(x for x in out if x["id"] == "g031")
    showcase = {
        "id": "g031",
        "question": a31["question"],
        "before": {"answer": b31["answer"], "citations": b31["citations"]},
        "after": {"answer": a31["answer"], "citations": a31["citations"]},
        "fix_note": (
            "Baseline retrieved an engine-named work order and a sensor *trend*, so it "
            "missed the manual/fault-code and under-reported the alarm. Two fixes — "
            "type-aware fusion retrieval and status-preferring routing — make it cite the "
            "canonical procedure and read the live alarm correctly."
        ),
    }
    (demo_dir / "showcase.json").write_text(json.dumps(showcase, indent=2))
    print(f"Wrote before/after showcase → {demo_dir/'showcase.json'}")


if __name__ == "__main__":
    main()
