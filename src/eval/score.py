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


def _predict_once(answer, rows: list[dict]) -> list[dict]:
    """One pass of the live pipeline over every row (aligned to rows)."""
    preds = []
    for i, r in enumerate(rows, 1):
        print(f"    [{i:>2}/{len(rows)}] {r['id']} ({r['route']}) …", flush=True)
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
            print(f"         ! error: {exc}")
            preds.append({"id": r["id"], "error": str(exc)})
    return preds


def run_predictions(rows: list[dict], runs: int = 1) -> list[list[dict]]:
    """Run the pipeline `runs` times over every row (gpt is not deterministic even at
    temperature 0, so a single pass is noisy on borderline rows). Returns a list of runs,
    each a list of per-row prediction dicts aligned to rows."""
    from src.rag.pipeline import answer  # local import: builds retriever lazily

    all_runs = []
    for run_i in range(1, runs + 1):
        print(f"  pipeline run {run_i}/{runs} …", flush=True)
        all_runs.append(_predict_once(answer, rows))
    return all_runs


def load_runs(pred_path) -> list[list[dict]]:
    """Load cached predictions, tolerating the old single-run flat-list format."""
    data = json.loads(pred_path.read_text())
    if data and isinstance(data[0], dict):  # legacy: a flat list of preds = one run
        return [data]
    return data


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


# --------------------------------------------------------------- per-run + aggregate


def score_run(rows, preds, judge: bool) -> tuple[list[Metric], list[dict]]:
    """Compute the full metric set for a single run's predictions."""
    metrics = [score_routing(rows, preds), score_retrieval(rows, preds)]
    verdicts = []
    if judge:
        faith, frecall, verdicts = score_faithfulness(rows, preds)
        metrics += [faith, frecall]
    ab_ok, ab_over = score_abstention(rows, preds)
    metrics += [ab_ok, ab_over]
    return metrics, verdicts


def aggregate(per_run: list[list[Metric]]) -> dict:
    """Average each metric across runs; keep the spread (min,max) so noise is visible.
    Detail (per-route breakdowns etc.) is taken from the first run as illustrative."""
    names = [m.name for m in per_run[0]]
    out = {}
    for name in names:
        vals = [next(m.value for m in run if m.name == name) for run in per_run]
        vals = [v for v in vals if v is not None]
        first = next(m for m in per_run[0] if m.name == name)
        mean = None if not vals else round(sum(vals) / len(vals), 3)
        out[name] = {"value": mean, "n": first.n, "runs": len(per_run),
                     "spread": [round(min(vals), 3), round(max(vals), 3)] if vals else None,
                     **first.detail}
    return out


# ---------------------------------------------------------------------- reporting


def build_report(rows, metrics: dict, verdicts, runs: int) -> dict:
    return {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n_rows": len(rows),
        "runs": runs,
        "metrics": metrics,
        "faithfulness_verdicts": verdicts,
    }


TARGETS = {"retrieval_recall@k": 0.80, "routing_accuracy": 0.90,
           "faithfulness": 0.85, "abstention_correct": 0.90}


def render_table(report: dict) -> str:
    m = report["metrics"]
    multi = report.get("runs", 1) > 1
    head = "| Metric | Value | Range | n | Target |" if multi else "| Metric | Value | n | Target |"
    lines = [head, "|---|---|---|---|---|" if multi else "|---|---|---|---|"]
    order = ["retrieval_recall@k", "routing_accuracy", "faithfulness", "fact_recall",
             "abstention_correct", "over_abstention"]
    for key in order:
        if key not in m:
            continue
        v = m[key]["value"]
        vs = "—" if v is None else f"{v:.3f}"
        tgt = TARGETS.get(key)
        tgts = "" if tgt is None else f"≥ {tgt:.2f}"
        if multi:
            sp = m[key].get("spread")
            rng = "—" if not sp else f"{sp[0]:.3f}–{sp[1]:.3f}"
            lines.append(f"| {key} | {vs} | {rng} | {m[key]['n']} | {tgts} |")
        else:
            lines.append(f"| {key} | {vs} | {m[key]['n']} | {tgts} |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Score the copilot against the golden set.")
    ap.add_argument("--no-judge", action="store_true", help="skip the LLM faithfulness judge")
    ap.add_argument("--reuse", action="store_true",
                    help="recompute metrics from the latest cached predictions (no API calls)")
    ap.add_argument("--runs", type=int, default=1,
                    help="pipeline passes per row; >1 averages out gpt nondeterminism")
    ap.add_argument("--tag", default="baseline", help="report filename tag")
    args = ap.parse_args()

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    rows = load_approved()
    print(f"Scoring {len(rows)} approved golden rows over {args.runs} run(s).")

    pred_path = REPORTS_DIR / f"predictions-{args.tag}.json"
    if args.reuse and pred_path.exists():
        print(f"Reusing cached predictions: {pred_path}")
        all_runs = load_runs(pred_path)
    else:
        print("Running live pipeline …")
        all_runs = run_predictions(rows, runs=args.runs)
        pred_path.write_text(json.dumps(all_runs, indent=1))
        print(f"Cached predictions → {pred_path}")

    judge = not args.no_judge
    per_run, verdicts = [], []
    for i, preds in enumerate(all_runs):
        if judge:
            print(f"Judging faithfulness (run {i + 1}/{len(all_runs)}) …")
        metrics, run_verdicts = score_run(rows, preds, judge)
        per_run.append(metrics)
        if i == 0:
            verdicts = run_verdicts  # keep run-0 verdicts for the disagreement table

    report = build_report(rows, aggregate(per_run), verdicts, len(all_runs))
    table = render_table(report)

    json_path = REPORTS_DIR / f"report-{args.tag}.json"
    md_path = REPORTS_DIR / f"report-{args.tag}.md"
    json_path.write_text(json.dumps(report, indent=1))
    md_path.write_text(f"# Eval report ({args.tag})\n\n_{report['generated']}_ · "
                       f"{report['n_rows']} approved rows · {report['runs']} run(s)"
                       f"{' (Value = mean, Range = min–max across runs)' if report['runs'] > 1 else ''}"
                       f"\n\n{table}\n")

    print("\n" + table)
    print(f"\nReport → {md_path}")


if __name__ == "__main__":
    main()
