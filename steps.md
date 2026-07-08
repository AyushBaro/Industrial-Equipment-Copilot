# Project Steps & Progress — Industrial Equipment RAG Copilot

**Read this anytime to see where you are and what's next.**
Full spec lives in `Project_Docs/PRD.md`. This file is the living checklist.

- **Status:** ✅ Phases 0–5 complete — eval green, all 4 findings fixed & gated (recall@5 0.967 · routing 1.000 · faithfulness 1.000 · over-abstn 0.067); ⬜ Phase 6 next (deploy + README)
- **Started:** 2026-06-30 (Tue)
- **Target finish:** ~Jul 15 (focused) / early Aug (part-time, evenings+weekends)
- **App LLM stack:** **OpenAI only** — chat model + OpenAI embeddings. (Claude Code is just the tool you build *with*; the app calls OpenAI.)

### Legend
✅ done · 🔄 in progress · ⬜ not started · 👤 = your job (can't delegate) · 🤖 = delegate to Claude Code

---

## Important: the OpenAI-only decision

The whole application uses the OpenAI API for every model call:

| Job in the app | Use |
|---|---|
| Answer synthesis (the copilot's replies) | OpenAI chat model — `gpt-4o` or `gpt-4.1` |
| Query routing (doc / timeseries / fusion) | cheaper `gpt-4o-mini` is fine |
| Synthetic doc generation (one-time) | `gpt-4o-mini` |
| LLM-as-judge (faithfulness scoring) | `gpt-4o` (use the stronger model to judge) |
| Embeddings (retrieval) | `text-embedding-3-small` (cheap, good); `-large` if recall is weak |

Keyword retrieval (BM25 via `rank_bm25`) and the vector store (Chroma or LanceDB,
local) are **not** model-dependent — they just store the OpenAI embeddings.
Put all model calls behind **one thin `llm_client.py` module** so the model name is
changed in exactly one place.

`.env` must contain: `OPENAI_API_KEY=...` (already added ✅)

---

## Current state snapshot (2026-06-30)

- ✅ CMAPSS data downloaded → `Data/raw/CMAPSSData/` (FD001–004 train/test/RUL, readme, + `Damage Propagation Modeling.pdf`)
- ✅ `OPENAI_API_KEY` in `.env`
- ✅ PRD written → `Project_Docs/PRD.md`
- ✅ `git init` + first commit (branch `main`, commit `eb4ac0c`)
- ✅ `.gitignore` (excludes `.env` + `Data/raw/`) and `.env.example`
- ✅ `CLAUDE.md` at repo root (project context for Claude Code)
- ✅ Node v24.2.0 / Python 3.13.4 confirmed
- ⬜ Python env + dependencies (Phase 1)

---

## Phase 0 — Setup  ✅ COMPLETE (2026-06-30)

- ✅ 👤 Download CMAPSS into `Data/raw/CMAPSSData/`
- ✅ 👤 Put `OPENAI_API_KEY` in `.env`
- ✅ 👤 Confirm Node 18+ (v24.2.0) and Python 3.11+ (3.13.4)
- ✅ 👤 `git init`, add `.gitignore` (ignores `.env`, `Data/raw/`, `__pycache__/`, `.venv/`), first commit
- ✅ 🤖 Create `CLAUDE.md` (OpenAI-only rule + non-negotiables: forced citation, abstention, keep eval green)
- ✅ 👤 Read `Data/raw/CMAPSSData/readme.txt`

**Checkpoint:** ✅ repo committed (`main`/`eb4ac0c`), `.env` gitignored, `CLAUDE.md` exists.

---

## Phase 1 — Data foundation  ✅ COMPLETE (2026-06-30)

- ✅ 🤖 Python project + `.venv` + pinned `requirements.txt` (OpenAI-only stack)
- ✅ 🤖 DuckDB loader for **FD001** — train (100 engines, 20631 rows), test, and true RUL tables
- ✅ 🤖 Flat-sensor detection (SNR / drift-based) → canonical constant set `{1,5,6,10,16,18,19}`
- ✅ 🤖 **Asset hierarchy** (`build/asset_hierarchy.csv`) — 21 sensors → subsystem, data-derived nominal range + alarm threshold/direction. Single source of truth.
- ✅ 🤖 **19 Claude-authored maintenance docs** in `data/corpus/` (7 manuals, 3 fault-code, 9 work orders), every cited value asserted against the hierarchy
- ✅ 🤖 8-test acceptance suite `tests/test_phase1.py` — **all green** (incl. the corpus↔hierarchy consistency lint)
- ✅ 👤 (optional) Spot-check: `make data` then eyeball `build/asset_hierarchy.csv`; skim 2–3 docs in `data/corpus/`

**Checkpoint:** ✅ `make test` → 8/8 pass. Time-series queries work; corpus is consistent with the data.
**Artifacts:** `src/` (config, llm_client stub, data/, docs_gen/), `data/corpus/`, `tests/`, `Makefile`.

---

## Phase 2 — Baseline RAG (documents only)  ✅ COMPLETE (2026-06-30)

- ✅ 🤖 Chunk docs (73 section chunks); embed with `text-embedding-3-small`; persist in Chroma (`build/chroma/`)
- ✅ 🤖 Hybrid retrieval: dense (embeddings) + BM25 keyword, fused with RRF
- ✅ 🤖 Synthesis with `gpt-4o`, **forced + code-verified citations**; basic abstention
- ✅ 🤖 8-question seed eval set (`Data/eval/phase2_seed.jsonl`) — seeds Phase 4
- ✅ 🤖 Tests: 5 offline (chunk/BM25/RRF/verifier/abstain) + 3 live (dense/end-to-end/abstain), all green
- ✅ 👤 Sanity run: **6/6 doc-lookup citation recall**, 2/2 out-of-scope correctly abstained

**Checkpoint:** ✅ `make ask Q="..."` answers doc questions with verified citations.
**Artifacts:** `src/rag/` (chunk, embed_store, retrieve, synthesize, pipeline), `src/llm_client.py` (live), seed eval set.
**Cost:** first API spend, well under $0.25 total.
*(Note: time-series + router + robust abstention are Phase 3.)*

---

## Phase 3 — Structured tool + router  ✅ COMPLETE (2026-06-30)

- ✅ 🤖 Bounded time-series tools (`sensor_trend`, `sensor_status`, `engine_overview`) over DuckDB + hierarchy (no free-form SQL)
- ✅ 🤖 Router (`gpt-4o-mini`, structured output): classify → doc/timeseries/fusion/out_of_scope + extract engine/sensors/intent
- ✅ 🤖 Fusion synthesis: docs + telemetry in one answer; **telemetry citations verified** like doc citations
- ✅ 🤖 Robust abstention: out-of-scope, no/invalid engine, unknown sensor
- ✅ 🤖 Tests: 9 offline (tools/validation/dispatch) + 4 live (router acc, timeseries, fusion, abstain) — all green
- ✅ 👤 Demo: timeseries + flagship fusion query both work end-to-end

**Checkpoint:** ✅ fusion query pulls from **both** sensor data and docs, citing both.
**Artifacts:** `src/rag/` + `timeseries.py`, `router.py`, generalized `synthesize.py`, routed `pipeline.py`, `phase3_seed.jsonl`.

### ⚠️ Findings to fix in Phase 5 (honest failure cases — good README material)
**Documented with evidence in `Project_Docs/case_study_retrieval_and_routing.md`** (README-ready).
1. **Fusion retrieval ranks work orders over the canonical procedure.** The engine-47
   Ps30 question cited `wo-1002-engine47` instead of `manual-hpc`/`FC-HPC-001` (which
   didn't make the top 5), so the answer wrongly said "the manual does not provide
   specific actions." Fix: boost manual/fault-code types for fusion; raise k.
2. **Router picks `trend` where `status` is better.** "Elevated Ps30 / known fault?"
   used a trend tool and under-stated the alarm (Ps30 = 48.28 vs 48.10 threshold = IN
   ALARM). Fix: bias fusion/alarm-style questions to a status check.

---

## Phase 4 — Golden eval set  ✅ COMPLETE (2026-07-06)

> **✅ Done:** all 55 candidates reviewed via the browser app — **50 approved, 5 rejected**.
> `make eval-validate ARGS=--require-approved` → *valid and all approved*. Route balance
> of the full file: 15 doc / 15 timeseries / 15 fusion / 10 out-of-scope (Phase 5 scoring
> should use the **50 approved** rows and exclude the 5 rejected). The known-hard fusion
> case (`g031`, engine-47 Ps30) was kept on purpose so the eval has teeth.

<details><summary>Original plan (for reference)</summary>


**What this is:** a hand-verified answer key of 50–60 questions with the *correct*
source(s) and key facts labeled. Everything in Phase 5 (every score, every before/after
delta) is measured against this. If the answer key is wrong or lazy, every number the
project reports is meaningless — that's why only *you* can sign off on the labels.

**Why it can't be fully automated:** the system under test and I (Claude) share
authorship of the corpus. If I also wrote the answer key unchecked, we'd be grading the
system against itself — circular. Your independent verification is what makes it a
legitimate ground truth. So: I draft, **you decide**.

### The division of labor (this is how it goes fast)

| Step | Who | Time | What happens |
|------|-----|------|--------------|
| 1. Define format + validator | 🤖 | — | JSONL schema + a `make eval-validate` that checks every row is well-formed and every cited source id actually exists |
| 2. Generate 60 **candidate** rows with **pre-filled proposed labels** | 🤖 | — | Balanced across routes; proposed source(s) + key-fact answer + difficulty, each marked `status: unreviewed`. For **timeseries**, the answer is **computed from the data** (objective), not guessed |
| 3. Include known-hard cases | 🤖 | — | Deliberately add questions the current system gets WRONG (e.g. the Phase-3 fusion/routing findings) so the eval has teeth |
| 4. **Review & decide** | 👤 | **~45–60 min** | Go row by row: approve, edit, or reject each proposed label. A review helper prints the question + my proposed label + (optionally) what the live system returns, so you're *verifying*, not authoring |
| 5. Add ~5–10 of your own | 👤 | ~15 min | Your own edge cases / phrasings I wouldn't think of — this is where your judgment adds coverage |
| 6. Validate + commit | 🤖 | — | Run the validator, flip all rows to `status: approved`, commit |

> **Current state:** ✅ Steps 1–3 done — `Data/eval/golden.jsonl` has **55 validated
> candidates** (15 doc / 15 timeseries / 15 fusion / 10 out-of-scope), all
> `status: unreviewed`. Timeseries answers are data-computed; the known-hard fusion
> case (`g031`, engine-47 Ps30) is flagged. **Your turn — open the browser review app:**
>
> ```
> make eval-web        # opens http://127.0.0.1:8000
> ```
> Click **✓ Approve** / **✕ Reject** (or keys: ⏎ approve, r reject, s skip, **v verify**,
> e edit). **Verify** shows the real source doc + live sensor data inline so you can
> confirm a label in seconds. Autosaves to `golden.jsonl` after every action — stop and
> resume anytime. (Terminal alternative: `make eval-triage`.) When done:
> `make eval-validate ARGS=--require-approved`.

**Net: ~1 hour of your focused time**, versus a day of writing labels from scratch —
because you're reviewing pre-filled, source-grounded proposals, and the objective
(timeseries) answers are auto-computed.

### The label format (one JSON object per line)
```
{"id": "g001", "question": "...", "route": "doc|timeseries|fusion|out_of_scope",
 "expected_sources": ["manual-hpc", "telemetry:engine47/sensor11/status"],
 "answer_key_facts": ["borescope every 30 cycles", "10 cycles once in alarm"],
 "answerable": true, "difficulty": "easy|medium|hard", "status": "approved", "notes": ""}
```
- `expected_sources`: the doc id(s) and/or telemetry query the correct answer must rest
  on. **This is the most important label** — Phase 5 scores retrieval against it.
- `answer_key_facts`: the specific facts a faithful answer must contain (used by the
  faithfulness judge). Grounded in the source docs/data, **not** copied from the RAG output.
- `answerable: false` for out-of-scope → the correct behavior is abstention.

### Your review guardrails (so the hour is well spent — don't rubber-stamp)
- For each row ask: *is this the source I'd actually pull? Are the key facts right and
  complete?* Open the cited doc if unsure — they're all in `Data/corpus/`.
- Keep the hard cases even though the system fails them — that's the point.
- Aim for balance: ~15 doc, ~15 timeseries, ~15 fusion, ~10 out-of-scope.

**Checkpoint:** `Data/eval/golden.jsonl` — 50–60 rows, all `status: approved`,
validator green, committed.

</details>

**Actual result:** ✅ 50 approved + 5 rejected, validator green. Not yet committed.

---

## Phase 5 — Automated scoring + iterate  ✅ COMPLETE (Jul 6–7)

> **Outcome:** every headline metric clears target (recall@5 **0.967**, routing **1.000**,
> faithfulness **1.000**, over-abstn **0.067** ↓ from 0.250). Judge validated (0.867 raw),
> all four human-review findings fixed with measured before/after, gate locks it in.

- ✅ 🤖 Scoring code: retrieval precision/recall@k, routing accuracy, abstention rate (`src/eval/score.py`, `make eval-score`)
- ✅ 🤖 Faithfulness scorer = LLM-as-judge (`gpt-4o`) — v1 (fact-only; needs source-aware upgrade, see note)
- ✅ 👤 Run the first full eval → **baseline recorded** (2026-07-06, table below)
- ✅ 🤖 Judge-validation helper built (`src/eval/validate_judge.py`, `make eval-judge`) — blind labeling in the browser, reports raw agreement + Cohen's κ
- ✅ 👤 Hand-labeled 15 rows → **raw agreement 0.867, κ 0.44** (passes ≥0.85 bar; low κ is a definition gap — abstention reads "faithful" to the judge but "failure" to a user). Surfaced findings 3–4 (see case study).
- ✅ 🤖 **Fix 1 — synthesizer over-abstention** (prompt rebalanced): fact_recall **0.473 → 0.598**, over-abstention **0.250 → 0.175**, faithfulness **held 0.975** (no new hallucination), out-of-scope abstention held 1.000. Deterministic fixes: g003/g004/g006 now answer 3/3.
- ✅ 🤖 **N-run averaging** in the harness (`make eval-score ARGS="--runs 3"`) — each metric is a mean with a min–max Range so noise is explicit (gpt isn't deterministic at temp 0).
- ✅ 🤖 **Fix 2 — type-aware fusion retrieval** (Phase-3 finding #1): add a manuals/fault-codes dense list as a 3rd RRF input for fusion. recall@5 **0.813 → 0.867**, faithfulness **0.950 → 1.000**, over-abstn **0.192 → 0.158**; g031 now cites the manual+fault code, g033/g039 stopped abstaining. No routing/OOS regression. (Both 3-run means; see case study.)
- ✅ 🤖 **Fix 3 — router intent + scope** (findings #2 & #4): prefer `status` for alarm-style Qs (g031 now reports the alarm), treat conceptual in-scope Qs as `doc` (g005/g014), + code-net for invalid sensors; bonus g022 cycle-count fix. routing **0.940 → 1.000**, recall@5 **0.867 → 0.967**, over-abstn **0.158 → 0.067**. No OOS regression. **All four review findings resolved.**
- ✅ 🤖 **Regression gate** (`tests/test_phase5.py`, `make eval-gate`): 4 offline scorer-logic tests (in `make test`) + live metric floors/ceilings (routing ≥0.90, recall ≥0.85, OOS-abstain ≥0.90, over-abstn ≤0.20) + per-fix canaries (g003 answers, g031 cites a manual & uses status, g005 routes doc). All 8 green. Locks in the Fix-1/2/3 numbers.
- ⬜ 👤 Pick 1–2 real failures to write up as a mini case study (findings 1–4 drafted in `Project_Docs/case_study_retrieval_and_routing.md`)

**Checkpoint:** a numbers table exists + at least **one documented before/after improvement**. ✅ (Fix 1 above.)

---

## Phase 6 — Deploy + README  (Jul 8 – Jul 9)

- ✅ 🤖 **FastAPI backend** (`src/api.py`, `make serve` → :8100, docs at `/docs`): `POST /ask` → grounded answer + citations + contexts + route + latency_ms; `/health`, `/`. Warms the index at startup; per-query latency logging. 4 offline + 1 live test (`tests/test_phase6.py`).
- ✅ 🤖 **Streamlit UI** (`src/ui.py`, `make ui` → :8501): question box + example prompts + k slider; renders route/confidence/latency, the grounded answer, citations, and a provenance expander (retrieved chunks + telemetry handles). Abstentions shown honestly. Verified end-to-end against the live API (doc/fusion/out-of-scope all render correctly).
- ✅ 🤖 **Cost logging per query** — `llm_client` tallies OpenAI token `usage` + USD cost in a request-scoped `track_usage()` meter (contextvars, threadpool-safe). Pricing table lives beside the model names. `answer()` attaches a `usage` dict (tokens, cost_usd, per-model breakdown); the API returns it + logs `cost_usd`/`tokens` per query; the UI shows a **Cost** metric + breakdown. Verified live: fusion query = $0.0048, 4 calls (router + 2 embed + synth). 4 offline unit checks pass.
- 🔄 👤 Write README intro (Cognite-style problem statement) + the failure case study in your own voice — **draft in place** at the top of `README.md` (marked as a placeholder to rewrite in your voice)
- ✅ 🤖 **Assemble README** (`README.md`): leads with the eval-results table (0.804→0.967 recall, 0.250→0.067 over-abstn) + an ASCII architecture diagram front and center, then data sources, query types, eval-harness + judge-validation methodology, the 4-finding failure case study, quickstart, make targets, model stack, layout, and a synthetic-data transparency note. All referenced targets/paths verified to resolve.

**Checkpoint:** ✅ demo runs end-to-end (API + UI verified live); README leads with results. Remaining: 👤 rewrite the intro paragraph in your own voice.

---

## Benchmarks — me  asure baseline (Phase 5 first run), then beat it

| Metric | Baseline (07-06) | Current — after Fixes 1–3 (07-07, 3-run) | Final target |
|---|---|---|---|
| Retrieval recall@5 | 0.804 | **0.967** | ≥ 0.80 ✅ |
| Routing accuracy | 0.940 | **1.000** | ≥ 0.90 ✅ |
| Faithfulness (grounding) | 0.975 | **1.000** | ≥ 0.85 ✅ |
| Fact recall (completeness) | 0.473 | **0.690** | — |
| Correct abstention rate | 1.000 (10/10) | **1.000** | ≥ 0.90 ✅ |
| Over-abstention (in-scope refused) | 0.250 (10/40) | **0.067** | → drive to 0 |
| LLM-judge ↔ your hand labels | 0.867 raw / κ 0.44 | (unchanged) | ≥ 0.85 ✅ (raw) |

> **Judge v2 (source-aware).** The faithfulness judge scores grounding against the
> *retrieved source text* (what the model actually saw), separately from fact coverage
> against the answer key. Faithfulness is high (**0.975** — the forced-citation design
> works; only g028 hallucinated a false "T30 in alarm"). The real gaps are **completeness**
> (fact_recall 0.47) and **over-abstention** (0.25) — and they're largely the *same
> problem*: 6 of the 8 worst fact_recall rows are answerable doc questions the system
> wrongly refused, so each covers 0 facts. Fixing over-abstention lifts both.
> **Still to do:** 👤 hand-label ~15 rows to confirm judge agreement ≥ 0.85.
>
> _(A v1 judge that saw only the answer key — not the sources — was tried first and
> mis-scored faithfulness at 0.60 by calling grounded-but-unlisted values "fabricated";
> replaced by v2. Good reminder of failure mode #3: never trust the judge unvalidated.)_

**The strongest portfolio artifact is the delta**, e.g. "recall@5 0.62 → 0.84 after
switching to hybrid retrieval." Record the date + the change that caused each jump.

---

## 👉 RIGHT NOW, DO THIS NEXT

Phase 5 is done — eval harness, validated judge, all 4 findings fixed with measured
before/after, and a regression gate locking it in. **On to Phase 6 (deploy + README).**

1. 🤖 FastAPI backend exposing the copilot (`answer()` → JSON with citations + route).
2. 🤖 Streamlit/Gradio UI; cost/latency logging per query.
3. 👤 Write the README intro (Cognite-style problem statement) in your voice; 🤖 assemble
   README leading with the **eval results table + the 4-finding case study** (the arc from
   0.804→0.967 recall and 0.250→0.067 over-abstention is the headline artifact).

> Before deploying, optionally run `make eval-gate` once more to confirm green on a clean
> checkout. The Phase-5 numbers table + `case_study_retrieval_and_routing.md` are the
> strongest things to put front-and-center in the README.

> The 3 ways people fail this: (1) rushing the hand-labeled eval set, (2) building the
> router before the doc-only baseline works, (3) trusting the LLM judge without
> validating it. Don't. (All three avoided ✅)
