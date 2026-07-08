# Industrial Equipment RAG Copilot

A retrieval-augmented copilot that answers maintenance and troubleshooting questions by
**fusing three heterogeneous industrial data sources** — real sensor telemetry, a
structured asset hierarchy, and unstructured maintenance documents — into single,
**grounded, cited** answers. It is built for a domain with **near-zero tolerance for
hallucination**: every claim traces to a specific source, and when the evidence is thin
the system **abstains** ("I don't have enough information") rather than guessing.

This is deliberately modeled on [Cognite's](https://www.cognite.com/) product problem:
industrial data (sensors, work orders, manuals, asset models) stays fragmented and hard
to query as a fused whole, and the valuable questions — *"is this sensor anomaly a known
fault, and what's the procedure?"* — require combining live telemetry with documentation,
cross-referenced through an asset model. The differentiator here is not the RAG plumbing;
it is **trustworthiness you can measure**: forced citation, explicit abstention, and an
evaluation harness wired into a regression test so every change produces a before/after
number.

> _(Author's note: this opening paragraph is a draft — rewrite it in your own voice for
> the final portfolio version.)_

---

## Results first

Every headline metric clears its target. Numbers are **means over 3 eval runs**
(`gpt` is not deterministic even at temperature 0), scored against a **50-question
hand-labeled golden set** (14 doc / 15 timeseries / 11 fusion / 10 out-of-scope).

| Metric | Baseline (07-06) | Current (after Fixes 1–3) | Target |
|---|---|---|---|
| Retrieval recall@5 | 0.804 | **0.967** | ≥ 0.80 ✅ |
| Routing accuracy | 0.940 | **1.000** | ≥ 0.90 ✅ |
| Faithfulness (grounding) | 0.975 | **1.000** | ≥ 0.85 ✅ |
| Fact recall (completeness) | 0.473 | **0.690** | — |
| Correct abstention (out-of-scope) | 1.000 | **1.000** | ≥ 0.90 ✅ |
| Over-abstention (in-scope refused) | 0.250 | **0.067** | → 0 |
| LLM-judge ↔ human labels (raw agreement) | 0.867 | — | ≥ 0.85 ✅ |

**The headline artifact is the delta, not the demo.** Recall@5 rose **0.804 → 0.967** and
over-abstention fell **73% (0.250 → 0.067)** across three measured retrieval/routing fixes
— while faithfulness never dropped below 0.95. Better answers, not looser ones. Each jump
is a documented before/after tied to a specific change (see the [case
study](#failure-case-study)).

Reproduce the numbers on a clean checkout:

```bash
make eval-gate      # scores the live system vs. the golden set; fails on any regression
```

---

## Architecture

```
User query
   │
   ▼
Query router  (gpt-4o-mini, structured output)
   │   classify → { doc · timeseries · fusion · out_of_scope }
   │   + extract engine / sensors / intent
   │
   ├──► Hybrid document retrieval ─────────► Maintenance corpus (Chroma)
   │      dense (text-embedding-3-small)      19 docs → 73 section chunks
   │      + BM25 keyword, fused with RRF       (manuals · fault codes · work orders)
   │      [fusion: + type-restricted manual/fault-code list as a 3rd RRF input]
   │
   ├──► Bounded telemetry tools ────────────► CMAPSS FD001 in DuckDB + asset hierarchy
   │      sensor_trend · sensor_status         (no free-form SQL — validated tool calls)
   │      · engine_overview
   │
   ▼
Synthesis  (gpt-4o, grounded, citations REQUIRED)
   │   answers ONLY from provided sources; every citation code-verified
   │   against what was actually retrieved; abstains when unsupported
   │
   ▼
Answer + citations (doc ids / telemetry handles) + confidence + cost + latency
```

### Deliberate engineering decisions

- **Hybrid retrieval (dense + BM25, fused with RRF).** Exact fault-code and sensor-ID
  matching (`Ps30`, `FC-HPC-001`) matters as much as semantic similarity; pure vector
  search misses exact tokens, BM25 catches them.
- **A routing / tool layer, not a monolithic prompt.** A cheap classifier picks the path
  and extracts structured arguments, so the expensive synthesis model only ever sees the
  right evidence.
- **Bounded telemetry tools, never free-form SQL.** The model can only call
  `sensor_trend`, `sensor_status`, or `engine_overview` with a validated engine/sensor —
  the reliable guarantees live in code, not in a prompt.
- **Forced, code-verified citation.** The synthesizer must cite every claim; a
  post-processing step drops any citation that wasn't actually in the retrieved context.
  An answer with no surviving citation becomes an abstention.
- **Explicit abstention, and it's tested.** Out-of-scope, no/invalid engine, or unknown
  sensor all resolve to "I don't have enough information" — and the eval set has 10
  out-of-scope rows specifically to keep the decline rate at 1.000.
- **One thin `llm_client.py`.** Every OpenAI call — synthesis, routing, embeddings, judge
  — routes through one module, so model names and pricing live in exactly one place.

---

## The data

Three sources, fused through the asset hierarchy as the single source of truth:

1. **Time-series telemetry — real.** NASA [CMAPSS](https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/)
   turbofan run-to-failure data, **FD001** (1 operating condition, 1 fault mode): 100
   engines, 20,631 cycle rows, 21 sensors. Seven sensors are flat/constant in FD001
   (`{1, 5, 6, 10, 16, 18, 19}`) and are detected and flagged as carrying no information —
   a data-quality step, documented rather than hidden.
2. **Asset hierarchy — synthetic, data-derived.** Each of the 21 sensors mapped to a
   subsystem (Fan / LPC / HPC / Combustor / HPT / LPT) with a data-derived nominal range
   and alarm threshold. This is the join layer that makes fusion queries possible and the
   **single source of truth** every document is checked against.
3. **Maintenance documents — synthetic, grounded.** 19 documents (7 manuals, 3 fault-code
   references, 9 work orders) → 73 section chunks. Every cited sensor value / threshold is
   asserted against the asset hierarchy by a consistency lint, so the corpus can't drift
   from the data.

> **On synthetic data (transparency).** The telemetry is real NASA data; the asset
> hierarchy and documents are generated (via `gpt-4o-mini`) and grounded in the real
> sensor schema and data-derived thresholds. This is a standard, legitimate technique —
> the generation is reproducible from the repo, and a lint enforces corpus↔hierarchy
> consistency. See `src/docs_gen/` and `src/data/asset_hierarchy.py`.

---

## Query types

| Type | Example | Path |
|---|---|---|
| **Document lookup** | *"What's the recommended borescope interval for the HPC?"* | hybrid retrieval over docs |
| **Time-series** | *"What was Ps30's trend for engine 23 over its last 50 cycles?"* | bounded tool over DuckDB |
| **Fusion** (the hard, valuable one) | *"Engine 47 shows elevated Ps30 — is this a known fault, and what does the manual say to do?"* | telemetry **+** docs, synthesized into one cited answer |
| **Out-of-scope** | *"What's the capital of France?"* | abstain |

---

## Evaluation harness

The harness is the point of the project. A **50-question golden set** (`Data/eval/golden.jsonl`),
hand-reviewed row by row, labels each question with its correct route, expected source(s),
and the key facts a faithful answer must contain. Automated scoring measures four
dimensions:

| Dimension | Metric | How |
|---|---|---|
| Retrieval quality | precision / recall@k | retrieved source ids vs. labeled correct sources |
| Faithfulness | grounding of each claim | **source-aware** LLM-as-judge (`gpt-4o`), scoring the answer against the *retrieved text* |
| Routing accuracy | correct path chosen | router output vs. labeled route |
| Abstention | correct-decline rate | does it decline out-of-scope / low-confidence questions |

**The judge is validated, not trusted.** 15 rows were blind hand-labeled and compared to
the judge: **raw agreement 0.867, Cohen's κ 0.44**. The low κ was itself a finding — it's
a *definition gap*, not judge error: an abstention makes no false claim so the judge reads
it "faithful," while a user reads it "failure." Conclusion baked into the harness:
**faithfulness is always reported alongside over-abstention, never as a standalone proxy
for answer quality.** (An earlier v1 judge that saw only the answer key — not the sources
— mis-scored faithfulness at 0.60 by calling grounded-but-unlisted values "fabricated"; it
was replaced by the source-aware v2. A good reminder never to trust an unvalidated judge.)

A **regression gate** (`make eval-gate`) runs the live system against the golden set and
fails the build if any metric regresses below its floor or if a fixed bug creeps back.

---

## Failure case study

The strongest evidence of real engineering is the honest failure analysis. Full writeup:
**[`Project_Docs/case_study_retrieval_and_routing.md`](Project_Docs/case_study_retrieval_and_routing.md)**.

The flagship fusion query — *"Engine 47 shows elevated Ps30 — is this a known fault and
what does the manual say to do?"* — exposed four distinct bugs, each fixed with a measured
before/after:

1. **Retrieval ranked incident work orders over the canonical procedure.** The answer
   wrongly said *"the manual does not provide specific actions"* because `manual-hpc` /
   `FC-HPC-001` never made the top 5 — engine-named work orders out-scored the generic
   procedure in both retrievers. **Fix:** a type-restricted manual/fault-code dense list as
   a third RRF input for fusion queries. recall@5 0.813 → 0.867; faithfulness 0.950 → 1.000.
2. **Router chose `trend` where `status` was right.** It reported Ps30 "rising but below
   threshold" when 48.28 > 48.10 = *in alarm*. **Fix:** bias alarm-style questions to a
   value-vs-threshold `status` check.
3. **Synthesizer abstained with the answer in its context** (e.g. the T50 threshold sitting
   in a retrieved table). The single biggest drag on completeness. **Fix:** rebalance the
   prompt to answer-and-cite when a source contains the fact, even in a table — without
   loosening the anti-hallucination rule. over-abstention 0.250 → 0.175.
4. **Router false-negatived conceptual in-scope questions as out-of-scope.** **Fix:** key
   scope on fleet relevance, not on whether a specific engine is named.

All four resolved; routing → 1.000, over-abstention → 0.067, and the gate locks the numbers
in. Notably, the guarantees held *even while the answers were wrong* — every citation
always traced to a real retrieved source, which is exactly what made the failures
diagnosable rather than silent.

---

## Quickstart

**Requirements:** Python 3.13, an OpenAI API key.

```bash
# 1. Set up the environment
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
cp .env.example .env        # then add your key: OPENAI_API_KEY=sk-...

# 2. Get the data (gitignored) — NASA CMAPSS FD001 into Data/raw/CMAPSSData/
#    See Project_Docs/PRD.md §3.1 for sources.

# 3. Build the data foundation + vector index
make data        # DuckDB load · flat-sensor detection · asset hierarchy
make docs        # validate the corpus against the hierarchy
make embed       # embed the corpus into Chroma (cached unless the corpus changed)

# 4. Ask a question from the CLI
make ask Q="Engine 47 shows elevated Ps30 — is this a known fault and what do we do?"
```

**Run the service + UI:**

```bash
make serve       # FastAPI on http://127.0.0.1:8100  (interactive docs at /docs)
make ui          # Streamlit on http://127.0.0.1:8501  (run in a second terminal)
```

`POST /ask` returns the grounded answer plus its citations, the provenance actually used,
route, confidence, per-query **cost (USD) and token usage**, and latency:

```bash
curl -s localhost:8100/ask -H 'content-type: application/json' \
     -d '{"question":"What is the alarm threshold for sensor T50?"}' | jq
```

---

## Make targets

| Target | What it does |
|---|---|
| `make data` | Load CMAPSS FD001 into DuckDB, detect flat sensors, build the asset hierarchy |
| `make docs` | Validate the maintenance corpus against the asset hierarchy |
| `make embed` | Embed the corpus into Chroma (cached unless the corpus changed) |
| `make ask Q="…"` | Ask the copilot one question from the CLI |
| `make serve` | FastAPI backend on `:8100` (`/ask`, `/health`, `/docs`) |
| `make ui` | Streamlit UI on `:8501` |
| `make test` | Offline test suite (free, no API) |
| `make test-live` | Full suite including live API tests (spends a few cents) |
| `make eval-score` | Score the live system vs. the golden set (`ARGS="--runs 3"` to average) |
| `make eval-judge` | Validate the faithfulness judge against hand labels (agreement + κ) |
| `make eval-gate` | Regression gate — fail on any metric regression |

---

## Model stack (OpenAI only)

Every model call routes through `src/llm_client.py`.

| Job | Model |
|---|---|
| Answer synthesis | `gpt-4o` |
| Query routing | `gpt-4o-mini` |
| Synthetic doc generation (one-time) | `gpt-4o-mini` |
| Faithfulness judge | `gpt-4o` |
| Embeddings | `text-embedding-3-small` |

Per-query token usage and USD cost are tallied in a request-scoped meter and surfaced in
the API response, the server log, and the UI.

---

## Tech stack

Python 3.13 · OpenAI SDK · **DuckDB** (telemetry) · **Chroma** (vectors) · **BM25**
(`rank_bm25`, keyword) · **FastAPI** (API) · **Streamlit** (UI) · **pytest** (tests/eval).

## Project layout

```
src/
  llm_client.py      one thin OpenAI wrapper (models, retries, cost metering)
  config.py          paths + constants
  data/              CMAPSS loader, flat-sensor detection, asset hierarchy
  docs_gen/          synthetic doc generation + corpus↔hierarchy lint
  rag/               chunk · embed_store · retrieve · router · timeseries · synthesize · pipeline
  eval/              golden-set generation, review, scoring, judge validation
  api.py             FastAPI backend
  ui.py              Streamlit UI
tests/               phase 1–6 acceptance + regression suites
Data/eval/           golden.jsonl + scored reports
Project_Docs/        PRD + failure case study
```

## Scope

Single fault mode (FD001), single tenant, no auth or streaming, thin UI — this is a
portfolio demonstration of trustworthy retrieval and rigorous evaluation, not a production
system. See `Project_Docs/PRD.md` for the full spec and `steps.md` for the build log.
