# Project Steps & Progress — Industrial Equipment RAG Copilot

**Read this anytime to see where you are and what's next.**
Full spec lives in `Project_Docs/PRD.md`. This file is the living checklist.

- **Status:** ✅ Phases 0–3 complete (offline 22/22 green; live 7/7 passed) — next: Phase 4
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

## Phase 4 — Golden eval set  (Jul 8 – Jul 9)  👤 YOUR WORK, UNSKIPPABLE

- ⬜ 🤖 Define the eval data format (question, correct answer, correct source ids, category, answerable?)
- ⬜ 👤 Hand-label **40–60 Q/A pairs** across all 3 query types
- ⬜ 👤 Add **5–10 out-of-scope / unanswerable** questions (to test abstention)
- ⬜ 👤 Label the correct source(s) for each (which doc chunk and/or which sensor query)

> This is tedious and it's the entire differentiator. Claude can suggest *candidate*
> questions, but **you verify every label.** Block the time; don't rush it.

**Checkpoint:** 40–60 verified labeled pairs + abstention cases committed.

---

## Phase 5 — Automated scoring + iterate  (Jul 10, 13)

- ⬜ 🤖 Scoring code: retrieval precision/recall@k, routing accuracy, abstention rate
- ⬜ 🤖 Faithfulness scorer = LLM-as-judge (`gpt-4o`)
- ⬜ 👤 Hand-label faithfulness on ~15 examples; compare to the judge → report agreement rate (≥0.85 = trustworthy)
- ⬜ 🤖 Wire eval into a **pytest regression test** that runs on every change
- ⬜ 👤 Run the first full eval → record the **baseline** numbers (don't fix anything yet)
- ⬜ 🤖 Iterate retrieval on what eval reveals (chunking, hybrid weights, k)
- ⬜ 👤 Pick 1–2 real failures to write up as a mini case study

**Checkpoint:** a numbers table exists + at least **one documented before/after improvement**.

---

## Phase 6 — Deploy + README  (Jul 14 – Jul 15)

- ⬜ 🤖 FastAPI backend exposing the copilot
- ⬜ 🤖 Streamlit/Gradio UI
- ⬜ 🤖 Cost/latency logging per query (track OpenAI token usage)
- ⬜ 👤 Write README intro (Cognite-style problem statement) + the failure case study in your own voice
- ⬜ 🤖 Assemble README: eval table + architecture diagram **front and center**, then setup/run + synthetic-data transparency note

**Checkpoint:** demo runs end-to-end; README leads with results.

---

## Benchmarks — measure baseline (Phase 5 first run), then beat it

| Metric | Baseline (just record) | Final target |
|---|---|---|
| Retrieval recall@5 | ___ | ≥ 0.80 |
| Routing accuracy | ___ | ≥ 0.90 |
| Faithfulness | ___ | ≥ 0.85 |
| Correct abstention rate | ___ | ≥ 0.90 |
| LLM-judge ↔ your hand labels | — | ≥ 0.85 |

**The strongest portfolio artifact is the delta**, e.g. "recall@5 0.62 → 0.84 after
switching to hybrid retrieval." Record the date + the change that caused each jump.

---

## 👉 RIGHT NOW, DO THIS NEXT

Phases 0–3 are done. The system now routes + fuses. Next is **Phase 4 — Golden eval set** (your work):

1. 👤 (optional) Try fusion: `make ask Q="Engine 47 is showing elevated Ps30 — is this a known fault and what does the manual say?"`
2. 👤 **Phase 4 is mostly yours and unskippable** — hand-label 40–60 Q/A pairs across doc/timeseries/fusion + abstention cases. Claude can scaffold the format and suggest candidates, but you verify every label.
3. 🤖 Ask Claude Code: *"Plan Phase 4: define the golden eval format and generate candidate questions across all 3 routes for me to label."*

> The two Phase-3 findings above are deliberately left for Phase 5 — once the golden
> set + scoring exist, fixing them gives you a measurable before/after (your best artifact).

> The 3 ways people fail this: (1) rushing the hand-labeled eval set, (2) building the
> router before the doc-only baseline works, (3) trusting the LLM judge without
> validating it. Don't.
