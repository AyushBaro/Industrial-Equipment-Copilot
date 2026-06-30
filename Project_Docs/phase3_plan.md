# Phase 3 Plan — Time-Series Tool + Query Router + Fusion

**Gate:** review this, then I run autonomously until the Phase 3 test suite is green.
**What this phase is:** the architecturally interesting one. Today the system only
reads documents. Phase 3 lets it **query the live sensor data**, **route** each
question to the right source, and **fuse** telemetry + documents into a single
grounded, cited answer — the thing that actually mirrors Cognite's product.
**Cost:** more API than Phase 2 (a router call + synthesis per query), still small —
estimated **< $0.30** for the whole build including live tests. Router uses
`gpt-4o-mini`, synthesis uses `gpt-4o`.
**Done = `pytest tests/` is green** (offline logic always; live tests run once).

---

## What we're building, in one picture

```
Question
   │
   ▼
ROUTER  (gpt-4o-mini, structured output)
   │  classifies → {doc | timeseries | fusion | out_of_scope}
   │  extracts   → engine #, sensor id(s), intent (trend/status/overview), window
   ▼
DISPATCH (deterministic — no model)
   ├─ doc         → Phase-2 hybrid retrieval ─────────────┐
   ├─ timeseries  → bounded DuckDB query tools ───────────┤
   ├─ fusion      → BOTH (docs + telemetry) ──────────────┤
   └─ out_of_scope→ abstain                                │
                                                           ▼
                              SYNTHESIS (gpt-4o): one grounded answer,
                              citing doc ids AND telemetry queries
                                                           │
                                                           ▼
                  { answer, citations:[doc ids + telemetry handles],
                    route, confidence, abstained }   ← all citations verified
```

The hard, valuable query — *"Engine 47 is showing elevated Ps30 — is that a known
fault, and what does the manual say to do?"* — needs the router to pick **fusion**,
the tool to pull engine 47's Ps30 trend, retrieval to find FC-HPC-001 + the HPC
manual, and synthesis to combine them with citations to both. That path is the
deliverable.

## Deliverables (adds to Phases 1–2)

```
src/rag/
├─ timeseries.py     # bounded, safe query tools over DuckDB + asset hierarchy
├─ router.py         # classify + extract a structured plan (gpt-4o-mini)
├─ synthesize.py     # GENERALIZE: accept docs and/or telemetry; cite both; abstain
└─ pipeline.py       # route → dispatch → synthesize  (answer() upgraded)
Data/eval/
└─ phase3_seed.jsonl # ~12 Q: timeseries + fusion + out-of-scope, with expected route/engine/sources
tests/
└─ test_phase3.py    # offline tool/dispatch tests + gated live router/fusion tests
```

## Key engineering decisions (the judgment calls — flagging for your input)

1. **Bounded query tools, NOT text-to-SQL.** I considered letting the LLM write SQL,
   but in a low-tolerance domain that risks hallucinated columns and unsafe queries,
   and it's hard to cite. Instead I expose a **small, safe set of parameterized
   functions** the router fills in. Every numeric answer traces to a known query.
   Proposed tools (read-only, over the FD001 train table + hierarchy):
   - `sensor_trend(engine, sensor, last_n=50)` → cycle/value series + direction summary
   - `sensor_status(engine, sensor=None, at_cycle=None)` → value vs nominal/alarm; which sensors are in alarm (defaults to the engine's last cycle)
   - `engine_overview(engine)` → total cycles + sensors currently in alarm

2. **Explicit router + deterministic dispatch, NOT a free agentic tool-loop.** A
   classify-then-dispatch design is testable (we can measure routing accuracy) and
   predictable. The router returns a structured *plan*; code runs the right path. (A
   native multi-tool agent loop is the alternative; rejected for determinism here.)

3. **Sensor resolution by the router, validated in code.** The router prompt includes
   the full 21-sensor table (id, symbol like `Ps30`, description, subsystem), so it
   maps "sensor 11" / "Ps30" / "HPC static discharge pressure" → `sensor_id=11`. Code
   then validates ids ∈ 1..21 and engine ∈ valid set. Bad/missing refs → abstain.

4. **Telemetry is first-class, cited provenance.** Each executed query gets a handle
   (e.g. `telemetry:engine47/sensor11/trend`). Synthesis must cite either a doc id or
   a telemetry handle for every claim; we verify doc citations ⊆ retrieved and
   telemetry citations ⊆ executed queries. Same "can't cite what it wasn't given"
   guarantee as Phase 2, extended to data.

5. **Robust abstention (upgraded from Phase 2's basic version).** Abstain when:
   route is out_of_scope; a timeseries/fusion query names no resolvable engine;
   the named engine/sensor doesn't exist; or doc confidence is low with no telemetry.
   Each gets a tested case.

## Components in detail

- **`timeseries.py`** — pure functions over DuckDB; no API, fully offline-testable.
  Return structured results plus a `query_handle` and a short `result_summary` string
  for the prompt. Threshold checks read alarm thresholds/directions straight from
  `asset_hierarchy.csv` (the Phase-1 source of truth) — so telemetry and docs agree.
- **`router.py`** — one `gpt-4o-mini` structured-output call → plan
  `{route, engine, sensors, intent, last_n, rationale}`; `validate_plan()` enforces
  the id/engine ranges and downgrades unresolvable timeseries/fusion plans to abstain.
- **`synthesize.py`** — generalize `synthesize(question, retrieved=None, telemetry=None)`:
  format whichever context is present, instruct citation of both kinds, verify, abstain
  when both are empty. Phase-2 doc-only behavior preserved.
- **`pipeline.py`** — `answer()` now: `plan = route(q)` → dispatch → `synthesize(...)`;
  result carries the `route` and the executed telemetry handles.

## Seed eval set (`Data/eval/phase3_seed.jsonl`) — ~12 questions
Each: `{question, expected_route, expected_engine, expected_sources, type}`. Spans:
- **timeseries**: "What was sensor 4's trend for engine 23 over its last 50 cycles?" → route=timeseries, engine=23
- **timeseries/status**: "Is engine 12's core speed in alarm?" → route=timeseries, engine=12
- **fusion**: "Engine 47 shows elevated Ps30 — is this a known fault and what does the manual say?" → route=fusion, engine=47, sources include FC-HPC-001 + manual-hpc + telemetry
- **doc** (regression): a couple from Phase 2 to confirm doc routing still works
- **out_of_scope / unanswerable**: incl. "trend for engine 999" (no such engine) → abstain
This seeds, but does not replace, the Phase-4 golden set.

## Acceptance tests (`tests/test_phase3.py`)
**Offline (always, no API):**
1. `sensor_trend` returns ≤ last_n rows, correctly ordered, with the right
   direction summary; values match the DB for a known engine.
2. `sensor_status` flags exactly the sensors over/under their hierarchy thresholds
   at a chosen cycle (computed independently in the test).
3. `engine_overview` returns the true cycle count for a known engine.
4. Plan validation: out-of-range engine/sensor or missing engine → plan downgraded
   to abstain.
5. Dispatch logic with a *fixed plan* (router mocked): doc→retrieval path,
   timeseries→tools path, fusion→both; telemetry citation verifier rejects handles
   for queries that weren't executed.

**Live (gated by `RUN_LLM_TESTS=1`, run once during build):**
6. Router accuracy ≥ 0.9 on the seed set's labeled `expected_route`/`expected_engine`.
7. Timeseries end-to-end: a trend question yields an answer citing the telemetry
   handle, no doc fabrication.
8. Fusion end-to-end: the engine-47 question returns an answer citing **both** a doc
   (FC-HPC-001 or manual-hpc) **and** the telemetry handle.
9. Abstention: out-of-scope and unknown-engine (999) both abstain with no citations.

## Build order
1. `timeseries.py` + offline tool tests → 2. `router.py` + plan-validation tests →
3. generalize `synthesize.py` + telemetry-citation tests → 4. upgrade `pipeline.py`
dispatch + dispatch tests → 5. `phase3_seed.jsonl` → 6. run live tests, iterate to
green → 7. macOS notification + commit + update `steps.md`.

## What I will NOT do in Phase 3
- No full golden eval set or scoring metrics (Phases 4–5) — only the seed + acceptance tests.
- No retrieval/router *tuning* beyond passing the seed; systematic tuning is Phase 5.
- No UI or API server (Phase 6).
- No new data beyond FD001; no text-to-SQL.

## Notification
macOS desktop notification + written summary + test output when the suite is green.
