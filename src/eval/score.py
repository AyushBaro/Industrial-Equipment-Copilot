"""Phase 5 — automated scoring of the copilot against the golden answer key.

Runs every APPROVED golden row through the live pipeline, then measures four things,
each against a different label in the row:

  routing accuracy   <- row.route         : did the router pick the same bucket?
  retrieval recall/  <- row.expected_sources : did retrieval surface the source(s)
    precision @k                             the correct answer must rest on?
  abstention         <- row.answerable=false : did the system refuse out-of-scope Qs
                                               (and NOT over-refuse in-scope ones)?
  faithfulness       <- row.answer_key_facts : LLM-judge — is the answer grounded
    + fact-recall                            (no fabrication) and does it cover the
                                             required facts?

The live pipeline is expensive, so predictions are cached to
Data/eval/reports/predictions-<tag>.json — recompute metrics freely without re-billing.
Only status=="approved" rows are scored; rejected rows stay in the file as a record.

    make eval-score                 # run pipeline + judge, write a timestamped report
    make eval-score ARGS=--no-judge # skip the LLM faithfulness judge (deterministic only)
    make eval-score ARGS=--reuse    # recompute metrics from the cached predictions
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from src import config
from src.llm_client import MODEL_JUDGE
from src.llm_client import client as llm

REPORTS_DIR = config.EVAL_DIR / "reports"

# ----------------------------------------------------------------------------- data


def load_approved() -> list[dict]:
    rows = [json.loads(l) for l in config.GOLDEN_EVAL.read_text().splitlines() if l.strip()]
    return [r for r in rows if r.get("status") == "approved"]


def normalize_source(src: str) -> str:
    """Canonicalize a source id so a predicted source matches the golden label.

    Telemetry handles carry query params the golden labels omit, e.g.
    'telemetry:engine23/sensor4/trend(last_n=50)' and '.../status@cycle120' must both
    match the labeled '.../trend' / '.../status'. Doc ids pass through unchanged.
    """
    if not src.startswith("telemetry:"):
        return src
    return re.split(r"[(@]", src, maxsplit=1)[0]


def retrieved_sources(result: dict) -> set[str]:
    """Sources retrieval actually surfaced for this question (from result contexts)."""
    out: set[str] = set()
    for ctx in result.get("contexts") or []:
        if "doc_id" in ctx:
            out.add(ctx["doc_id"])
        elif "telemetry" in ctx:
            out.add(normalize_source(ctx["telemetry"]))
    return out


# ------------------------------------------------------------------- run / cache


def run_predictions(rows: list[dict]) -> list[dict]:
    """Call the live pipeline once per row. Returns prediction dicts aligned to rows."""
    from src.rag.pipeline import answer  # local import: builds retriever lazily

    preds = []
    for i, r in enumerate(rows, 1):
        print(f"  [{i:>2}/{len(rows)}] {r['id']} ({r['route']}) …", flush=True)
        try:
            res = answer(r["question"])
            preds.append({
                "id": r["id"],
                "route": res.get("route"),
                "answer": res.get("answer", ""),
                "citations": res.get("citations", []),
                "retrieved": sorted(retrieved_sources(res)),
                "abstained": bool(res.get("abstained")),
                "sources_text": res.get("sources_text", []),
            })
        except Exception as exc:  # noqa: BLE001 — one bad row shouldn't sink the run
            print(f"       ! error: {exc}")
            preds.append({"id": r["id"], "error": str(exc)})
    return preds


# --------------------------------------------------------------- deterministic metrics


@dataclass
class Metric:
    name: str
    value: float | None
    n: int
    detail: dict = field(default_factory=dict)


def score_routing(rows, preds) -> Metric:
    by_route: dict[str, list[int]] = {}
    correct = 0
    for r, p in zip(rows, preds):
        ok = p.get("route") == r["route"]
        correct += ok
        by_route.setdefault(r["route"], []).append(ok)
    per_route = {rt: round(sum(v) / len(v), 3) for rt, v in sorted(by_route.items())}
    return Metric("routing_accuracy", round(correct / len(rows), 3), len(rows),
                  {"per_route": per_route})


def score_retrieval(rows, preds) -> Metric:
    """Recall@k and precision@k over rows that have expected sources (skip out-of-scope)."""
    recalls, precisions, per_route = [], [], {}
    for r, p in zip(rows, preds):
        expected = {normalize_source(s) for s in r.get("expected_sources", [])}
        if not expected:
            continue  # out-of-scope: nothing to retrieve, measured by abstention instead
        got = set(p.get("retrieved", []))
        hit = expected & got
        recall = len(hit) / len(expected)
        precision = len(hit) / len(got) if got else 0.0
        recalls.append(recall)
        precisions.append(precision)
        per_route.setdefault(r["route"], []).append(recall)
    if not recalls:
        return Metric("retrieval_recall@k", None, 0)
    return Metric("retrieval_recall@k", round(sum(recalls) / len(recalls), 3), len(recalls),
                  {"precision@k": round(sum(precisions) / len(precisions), 3),
                   "k": config.RETRIEVAL_K,
                   "recall_per_route": {rt: round(sum(v) / len(v), 3)
                                        for rt, v in sorted(per_route.items())}})


def score_abstention(rows, preds) -> tuple[Metric, Metric]:
    """Two rates: correct abstention on out-of-scope, and over-abstention on in-scope."""
    oos_ok, oos_n, over, in_n = 0, 0, 0, 0
    for r, p in zip(rows, preds):
        if r.get("answerable") is False:
            oos_n += 1
            oos_ok += bool(p.get("abstained"))
        else:
            in_n += 1
            over += bool(p.get("abstained"))  # abstained when it should have answered
    correct = Metric("abstention_correct", round(oos_ok / oos_n, 3) if oos_n else None, oos_n)
    overrate = Metric("over_abstention", round(over / in_n, 3) if in_n else None, in_n)
    return correct, overrate


# ------------------------------------------------------------------ LLM-as-judge

JUDGE_SYSTEM = """You are a strict evaluator for an industrial-equipment maintenance \
assistant in a near-zero-hallucination domain. You are given a QUESTION, the SOURCES the \
assistant was allowed to use (retrieved doc excerpts and/or telemetry results), the \
REQUIRED FACTS a complete answer should convey (a reference answer key), and the \
assistant's ANSWER.

Judge two things INDEPENDENTLY — do not conflate them:
1. faithfulness (grounding): is EVERY claim in the ANSWER supported by the SOURCES, \
with NO outside knowledge and NO fabricated or contradicted numbers, thresholds, or \
actions? Judge grounding ONLY against the SOURCES — a number that is in the SOURCES but \
absent from the REQUIRED FACTS is still faithful. An abstention ("I don't have enough \
information") makes no claims and is therefore faithful.
2. fact coverage: for each REQUIRED FACT, is it present (in meaning, not necessarily \
wording) in the ANSWER? This measures completeness, not grounding.

Return ONLY JSON:
{"faithful": bool, "facts_supported": [bool, ...same length/order as required facts...], \
"reason": "one short sentence"}"""


def judge_faithfulness(question: str, required_facts: list[str], answer: str,
                       sources_text: list[str] | None = None) -> dict:
    sources = "\n\n".join(sources_text or []) or "(no sources were retrieved)"
    user = (f"QUESTION: {question}\n\nSOURCES:\n{sources}\n\nREQUIRED FACTS:\n"
            + "\n".join(f"- {f}" for f in required_facts)
            + f"\n\nANSWER:\n{answer}")
    raw = llm.chat([{"role": "system", "content": JUDGE_SYSTEM},
                    {"role": "user", "content": user}],
                   model=MODEL_JUDGE, temperature=0.0, json_mode=True)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"faithful": False, "facts_supported": [], "reason": "judge returned non-JSON"}
    return data


def score_faithfulness(rows, preds) -> tuple[Metric, Metric, list[dict]]:
    """Judge every answerable row. Returns (faithfulness, fact_recall, per-row verdicts)."""
    verdicts, faithful_flags, fact_recalls = [], [], []
    answerable = [(r, p) for r, p in zip(rows, preds)
                  if r.get("answerable") is not False and "error" not in p]
    for i, (r, p) in enumerate(answerable, 1):
        facts = r.get("answer_key_facts", [])
        print(f"  judge [{i:>2}/{len(answerable)}] {r['id']} …", flush=True)
        v = judge_faithfulness(r["question"], facts, p.get("answer", ""),
                               p.get("sources_text"))
        supported = v.get("facts_supported") or []
        recall = (sum(1 for x in supported if x) / len(facts)) if facts else None
        faithful_flags.append(bool(v.get("faithful")))
        if recall is not None:
            fact_recalls.append(recall)
        verdicts.append({"id": r["id"], "faithful": bool(v.get("faithful")),
                         "fact_recall": None if recall is None else round(recall, 3),
                         "reason": v.get("reason", "")})
    faith = Metric("faithfulness", round(sum(faithful_flags) / len(faithful_flags), 3)
                   if faithful_flags else None, len(faithful_flags))
    frecall = Metric("fact_recall", round(sum(fact_recalls) / len(fact_recalls), 3)
                     if fact_recalls else None, len(fact_recalls))
    return faith, frecall, verdicts


# ---------------------------------------------------------------------- reporting


def build_report(rows, metrics: list[Metric], verdicts) -> dict:
    return {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n_rows": len(rows),
        "metrics": {m.name: {"value": m.value, "n": m.n, **m.detail} for m in metrics},
        "faithfulness_verdicts": verdicts,
    }


TARGETS = {"retrieval_recall@k": 0.80, "routing_accuracy": 0.90,
           "faithfulness": 0.85, "abstention_correct": 0.90}


def render_table(report: dict) -> str:
    m = report["metrics"]
    lines = ["| Metric | Value | n | Target |", "|---|---|---|---|"]
    order = ["retrieval_recall@k", "routing_accuracy", "faithfulness", "fact_recall",
             "abstention_correct", "over_abstention"]
    for key in order:
        if key not in m:
            continue
        v = m[key]["value"]
        vs = "—" if v is None else f"{v:.3f}"
        tgt = TARGETS.get(key)
        tgts = "" if tgt is None else f"≥ {tgt:.2f}"
        lines.append(f"| {key} | {vs} | {m[key]['n']} | {tgts} |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Score the copilot against the golden set.")
    ap.add_argument("--no-judge", action="store_true", help="skip the LLM faithfulness judge")
    ap.add_argument("--reuse", action="store_true",
                    help="recompute metrics from the latest cached predictions (no API calls)")
    ap.add_argument("--tag", default="baseline", help="report filename tag")
    args = ap.parse_args()

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    rows = load_approved()
    print(f"Scoring {len(rows)} approved golden rows.")

    pred_path = REPORTS_DIR / f"predictions-{args.tag}.json"
    if args.reuse and pred_path.exists():
        print(f"Reusing cached predictions: {pred_path}")
        preds = json.loads(pred_path.read_text())
    else:
        print("Running live pipeline …")
        preds = run_predictions(rows)
        pred_path.write_text(json.dumps(preds, indent=1))
        print(f"Cached predictions → {pred_path}")

    metrics = [score_routing(rows, preds), score_retrieval(rows, preds)]
    ab_ok, ab_over = score_abstention(rows, preds)

    verdicts = []
    if args.no_judge:
        metrics += [ab_ok, ab_over]
    else:
        print("Judging faithfulness …")
        faith, frecall, verdicts = score_faithfulness(rows, preds)
        metrics += [faith, frecall, ab_ok, ab_over]

    report = build_report(rows, metrics, verdicts)
    table = render_table(report)

    json_path = REPORTS_DIR / f"report-{args.tag}.json"
    md_path = REPORTS_DIR / f"report-{args.tag}.md"
    json_path.write_text(json.dumps(report, indent=1))
    md_path.write_text(f"# Eval report ({args.tag})\n\n_{report['generated']}_ · "
                       f"{report['n_rows']} approved rows\n\n{table}\n")

    print("\n" + table)
    print(f"\nReport → {md_path}")


if __name__ == "__main__":
    main()
