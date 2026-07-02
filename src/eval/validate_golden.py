"""Validate the golden eval file: structure + that every cited source actually exists.

Run:  python -m src.eval.validate_golden          (structure + source existence)
      python -m src.eval.validate_golden --require-approved   (also: all rows approved)
"""
from __future__ import annotations

import json
import re
import sys

from src import config
from src.rag.chunk import build_chunks
from src.rag.timeseries import N_ENGINES, sensor_exists

VALID_ROUTES = {"doc", "timeseries", "fusion", "out_of_scope"}
VALID_DIFF = {"easy", "medium", "hard"}
VALID_STATUS = {"unreviewed", "approved", "rejected"}
REQUIRED = {"id", "question", "route", "expected_engine", "expected_sources",
            "answer_key_facts", "answerable", "difficulty", "status", "notes"}
_TELE = re.compile(r"^telemetry:engine(\d+)/(sensor(\d+)|all|overview)(/\w+)?$")


def load_rows(path=None):
    path = path or config.GOLDEN_EVAL
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def validate(path=None, require_approved: bool = False) -> list[str]:
    rows = load_rows(path)
    doc_ids = {c.doc_id for c in build_chunks()}
    errors, ids = [], set()

    for i, r in enumerate(rows):
        tag = r.get("id", f"row{i}")
        missing = REQUIRED - r.keys()
        if missing:
            errors.append(f"{tag}: missing keys {missing}")
            continue
        if r["id"] in ids:
            errors.append(f"{tag}: duplicate id")
        ids.add(r["id"])
        if r["route"] not in VALID_ROUTES:
            errors.append(f"{tag}: bad route {r['route']!r}")
        if r["difficulty"] not in VALID_DIFF:
            errors.append(f"{tag}: bad difficulty {r['difficulty']!r}")
        if r["status"] not in VALID_STATUS:
            errors.append(f"{tag}: bad status {r['status']!r}")

        # out-of-scope consistency
        if r["route"] == "out_of_scope":
            if r["answerable"] or r["expected_sources"]:
                errors.append(f"{tag}: out_of_scope must be answerable=false, no sources")
        else:
            if not r["expected_sources"]:
                errors.append(f"{tag}: {r['route']} needs at least one expected source")

        # every source exists
        for s in r["expected_sources"]:
            if s.startswith("telemetry:"):
                m = _TELE.match(s)
                if not m:
                    errors.append(f"{tag}: malformed telemetry handle {s!r}")
                    continue
                eng = int(m.group(1))
                if not 1 <= eng <= N_ENGINES:
                    errors.append(f"{tag}: engine {eng} out of range in {s!r}")
                if m.group(3) and not sensor_exists(int(m.group(3))):
                    errors.append(f"{tag}: sensor {m.group(3)} out of range in {s!r}")
            elif s not in doc_ids:
                errors.append(f"{tag}: unknown doc id {s!r}")

        if not r["answer_key_facts"]:
            errors.append(f"{tag}: answer_key_facts is empty")

        if require_approved and r["status"] != "approved":
            errors.append(f"{tag}: status is {r['status']!r} (need 'approved')")

    return errors


def main():
    require = "--require-approved" in sys.argv
    rows = load_rows()
    errors = validate(require_approved=require)
    by_route = {}
    for r in rows:
        by_route[r["route"]] = by_route.get(r["route"], 0) + 1
    print(f"{len(rows)} rows | by route: {by_route}")
    if errors:
        print(f"\n✗ {len(errors)} problems:")
        for e in errors:
            print("  -", e)
        raise SystemExit(1)
    print("✓ valid" + (" and all approved" if require else ""))


if __name__ == "__main__":
    main()
