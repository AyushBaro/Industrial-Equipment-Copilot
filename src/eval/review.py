"""Review helper for the golden eval set.

Prints each candidate with its PROPOSED label so you can verify quickly, then edit
Data/eval/golden.jsonl in your editor (set "status": "approved", or fix any field).

    python -m src.eval.review              # read-only: show all candidates + proposed labels
    python -m src.eval.review --unreviewed # only rows still needing review
    python -m src.eval.review --live        # ALSO run the current system and compare (spends API)

--live shows what the system answers today so you can see agreement/disagreement — but
your label must reflect the CORRECT answer, not whatever the system says.
"""
from __future__ import annotations

import sys

from src.eval.validate_golden import load_rows

C = {"doc": "📄", "timeseries": "📈", "fusion": "🔀", "out_of_scope": "🚫"}


def _print_row(r):
    print(f"\n{'─'*78}")
    print(f"{r['id']}  {C.get(r['route'],'')} {r['route']}  [{r['difficulty']}]  status={r['status']}")
    print(f"Q: {r['question']}")
    print(f"  proposed sources : {r['expected_sources']}")
    print(f"  proposed facts   : {r['answer_key_facts']}")
    if r["expected_engine"] is not None:
        print(f"  expected engine  : {r['expected_engine']}")
    if r["notes"]:
        print(f"  notes            : {r['notes']}")


def _print_live(r):
    from src.rag.pipeline import answer

    res = answer(r["question"])
    route_ok = "✓" if res["route"] == r["route"] else "✗"
    exp = set(r["expected_sources"])
    got = set(res["citations"])
    # prefix-match telemetry handles (executed handle carries last_n/cycle suffixes)
    def covered(e):
        return any(g == e or g.startswith(e) or e.startswith(g.split("(")[0]) for g in got)
    src_hits = sum(1 for e in exp if covered(e))
    print(f"  ── system now: route={res['route']} [{route_ok}]  abstained={res['abstained']}")
    print(f"     answer   : {res['answer'][:200]}")
    print(f"     cites    : {res['citations']}")
    if r["route"] != "out_of_scope":
        print(f"     source match: {src_hits}/{len(exp)} expected sources cited")


def main():
    rows = load_rows()
    only_unreviewed = "--unreviewed" in sys.argv
    do_live = "--live" in sys.argv
    if only_unreviewed:
        rows = [r for r in rows if r["status"] == "unreviewed"]

    counts = {}
    for r in load_rows():
        counts[r["status"]] = counts.get(r["status"], 0) + 1

    print(f"Golden set: {sum(counts.values())} rows | status: {counts}")
    print("Edit Data/eval/golden.jsonl to approve/fix. Run `make eval-validate` when done.")

    for r in rows:
        _print_row(r)
        if do_live:
            try:
                _print_live(r)
            except Exception as e:  # noqa: BLE001
                print(f"  (live error: {e})")

    print(f"\n{'─'*78}\nReviewed {len(rows)} rows. Next: set status='approved' on the good ones,")
    print("edit any that are wrong, then `make eval-validate ARGS=--require-approved`.")


if __name__ == "__main__":
    main()
