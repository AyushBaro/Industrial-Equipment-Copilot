"""Parse and validate the maintenance corpus.

Each corpus doc is markdown with a YAML front-matter block:

    ---
    id: manual-hpc
    type: manual            # one of: manual | fault_code | work_order
    title: ...
    subsystem: HPC
    cites_sensors: [3, 7, 11, 12]
    assertions:             # optional: values the doc states that MUST match the hierarchy
      - {sensor_id: 3, field: nominal_max, value: 1597.38}
    ---
    <markdown body>

`assertions` are how we keep the corpus honest: every hierarchy-derived number a doc
states is declared here and checked against build/asset_hierarchy.csv. Observed
sensor *readings* in work orders are free prose (they are observations, not hierarchy
values) and are not asserted.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from src import config
from src.data.asset_hierarchy import load_hierarchy

VALID_TYPES = {"manual", "fault_code", "work_order"}
ASSERTABLE_FIELDS = {"nominal_min", "nominal_max", "alarm_threshold"}
TOLERANCE = 0.01


@dataclass
class Doc:
    path: Path
    meta: dict
    body: str
    errors: list[str] = field(default_factory=list)


def _split_front_matter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        raise ValueError("missing YAML front-matter (must start with '---')")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError("malformed front-matter delimiters")
    meta = yaml.safe_load(parts[1]) or {}
    return meta, parts[2].strip()


def load_corpus(corpus_dir=None) -> list[Doc]:
    corpus_dir = Path(corpus_dir or config.CORPUS_DIR)
    docs: list[Doc] = []
    for path in sorted(corpus_dir.glob("*.md")):
        meta, body = _split_front_matter(path.read_text())
        docs.append(Doc(path=path, meta=meta, body=body))
    return docs


def validate(corpus_dir=None) -> list[Doc]:
    docs = load_corpus(corpus_dir)
    hier = load_hierarchy().set_index("sensor_id")
    seen_ids: set[str] = set()

    for doc in docs:
        m = doc.meta
        for key in ("id", "type", "title", "subsystem", "cites_sensors"):
            if key not in m:
                doc.errors.append(f"missing front-matter key: {key}")
        if m.get("type") not in VALID_TYPES:
            doc.errors.append(f"invalid type: {m.get('type')!r}")
        if m.get("id") in seen_ids:
            doc.errors.append(f"duplicate id: {m.get('id')}")
        seen_ids.add(m.get("id"))
        if not doc.body or len(doc.body) < 80:
            doc.errors.append("body too short / empty")

        for a in m.get("assertions", []) or []:
            sid, fld, val = a.get("sensor_id"), a.get("field"), a.get("value")
            if fld not in ASSERTABLE_FIELDS:
                doc.errors.append(f"assertion field not assertable: {fld}")
                continue
            if sid not in hier.index:
                doc.errors.append(f"assertion sensor_id not in hierarchy: {sid}")
                continue
            actual = hier.loc[sid, fld]
            if actual != actual:  # NaN — sensor has no such threshold
                doc.errors.append(
                    f"sensor {sid} has no {fld} (non-informative); cannot assert {val}"
                )
                continue
            if abs(float(actual) - float(val)) > TOLERANCE:
                doc.errors.append(
                    f"sensor {sid}.{fld}={val} disagrees with hierarchy {actual}"
                )
    return docs


def errors_summary(docs: list[Doc]) -> dict:
    return {d.path.name: d.errors for d in docs if d.errors}


if __name__ == "__main__":
    docs = validate()
    bad = errors_summary(docs)
    print(f"Corpus: {len(docs)} docs.")
    if bad:
        for name, errs in bad.items():
            print(f"  ✗ {name}: {errs}")
    else:
        print("  ✓ all docs valid and consistent with the asset hierarchy.")
