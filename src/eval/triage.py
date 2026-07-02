"""Interactive triage for the golden eval set — fast, keyboard-driven, autosaving.

For each unreviewed row you see the question + proposed label. Then:

    [Enter] approve      (the common case — just tap Enter)
    v       view sources (prints the cited doc text AND runs the telemetry query — offline, free)
    e       edit         (opens the row in $EDITOR; on save it's marked approved)
    r       reject       (drops it from the final set)
    s       skip         (leave unreviewed, decide later)
    b       back         (re-do the previous row)
    q       quit & save

Progress is written to Data/eval/golden.jsonl after every decision, so you can stop
and resume anytime. No manual JSON editing required.

    python -m src.eval.triage              # review only unreviewed rows
    python -m src.eval.triage --all        # revisit every row
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile

from src import config
from src.docs_gen.validate_corpus import load_corpus
from src.rag import timeseries as ts

_TELE = re.compile(r"^telemetry:engine(\d+)/(sensor(\d+)|all|overview)(?:/(\w+))?")
_ICON = {"doc": "DOC", "timeseries": "TS", "fusion": "FUSION", "out_of_scope": "OOS"}


def _load():
    return [json.loads(l) for l in config.GOLDEN_EVAL.read_text().splitlines() if l.strip()]


def _save(rows):
    with config.GOLDEN_EVAL.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def _corpus_map():
    return {d.meta["id"]: d for d in load_corpus()}


def _run_handle(handle: str) -> str:
    m = _TELE.match(handle)
    if not m:
        return f"(unparseable handle: {handle})"
    eng, kind, sensor, intent = int(m.group(1)), m.group(2), m.group(3), m.group(4)
    if kind == "overview":
        return ts.engine_overview(eng)["result_summary"]
    if kind == "all":
        return ts.sensor_status(eng)["result_summary"]
    s = int(sensor)
    if intent == "trend":
        return ts.sensor_trend(eng, s)["result_summary"]
    return ts.sensor_status(eng, s)["result_summary"]


def _view_sources(row, corpus):
    print("\n" + "═" * 78)
    for src in row["expected_sources"]:
        if src.startswith("telemetry:"):
            print(f"\n▶ TELEMETRY {src}\n   {_run_handle(src)}")
        elif src in corpus:
            body = corpus[src].body
            snippet = body if len(body) < 1400 else body[:1400] + "\n   …(truncated)"
            print(f"\n▶ DOC {src} — {corpus[src].meta.get('title','')}\n{snippet}")
        else:
            print(f"\n▶ (unknown source: {src})")
    print("═" * 78)


def _edit(row) -> bool:
    editor = os.environ.get("EDITOR") or "nano"
    with tempfile.NamedTemporaryFile("w+", suffix=".json", delete=False) as tf:
        json.dump(row, tf, indent=2)
        path = tf.name
    try:
        subprocess.call([editor, path])
        with open(path) as f:
            new = json.load(f)
        for k in ("id", "question", "route", "expected_sources", "answer_key_facts"):
            if k not in new:
                print(f"  ! edit missing key {k}; discarded.")
                return False
        row.clear()
        row.update(new)
        return True
    except json.JSONDecodeError as e:
        print(f"  ! invalid JSON ({e}); edit discarded.")
        return False
    finally:
        os.unlink(path)


def _show(row, idx, total):
    print("\n" + "─" * 78)
    eng = f" engine={row['expected_engine']}" if row.get("expected_engine") is not None else ""
    print(f"[{idx+1}/{total}]  {_ICON.get(row['route'],'')}  {row['route']}  "
          f"[{row['difficulty']}]  status={row['status']}{eng}")
    print(f"\nQ: {row['question']}\n")
    print(f"  proposed sources : {row['expected_sources']}")
    print(f"  proposed facts   : {row['answer_key_facts']}")
    if row["notes"]:
        print(f"  ⚠ notes          : {row['notes']}")


def main():
    rows = _load()
    corpus = _corpus_map()
    review_all = "--all" in sys.argv
    order = [i for i, r in enumerate(rows) if review_all or r["status"] == "unreviewed"]
    if not order:
        print("Nothing to review — all rows already reviewed. Use --all to revisit.")
        return

    print(f"Triaging {len(order)} rows. [Enter]=approve  v=view  e=edit  r=reject  s=skip  b=back  q=quit")
    pos = 0
    while pos < len(order):
        i = order[pos]
        row = rows[i]
        _show(row, pos, len(order))
        choice = input("  > ").strip().lower()

        if choice in ("", "a"):
            row["status"] = "approved"; _save(rows); pos += 1
        elif choice == "v":
            _view_sources(row, corpus)  # stay on same row
        elif choice == "e":
            if _edit(row):
                row["status"] = "approved"; _save(rows); pos += 1
        elif choice == "r":
            row["status"] = "rejected"; _save(rows); pos += 1
        elif choice == "s":
            pos += 1
        elif choice == "b":
            pos = max(0, pos - 1)
        elif choice == "q":
            break
        else:
            print("  ? keys: [Enter]=approve v=view e=edit r=reject s=skip b=back q=quit")

    _save(rows)
    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print(f"\nSaved. Status counts: {counts}")
    remaining = counts.get("unreviewed", 0)
    if remaining:
        print(f"{remaining} still unreviewed — rerun `make eval-triage` to continue.")
    else:
        print("All reviewed. Finish with: make eval-validate ARGS=--require-approved")


if __name__ == "__main__":
    main()
