
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
        })
        tag = "ABSTAINED" if out[-1]["abstained"] else f'{len(out[-1]["citations"])} cites'
        print(f'{qid} [{out[-1]["route"]:12}] {tag} · ${out[-1]["cost_usd"]:.5f} · {latency_ms}ms')

    dest = Path(config.ROOT) / "Data" / "demo" / "demo_qa.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2))
    total = sum(r["cost_usd"] for r in out)
    print(f"\nWrote {len(out)} demo Q/A → {dest}  (total generation cost ${total:.4f})")


if __name__ == "__main__":
    main()
