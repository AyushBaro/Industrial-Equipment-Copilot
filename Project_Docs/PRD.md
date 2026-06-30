# PRD: Industrial Equipment RAG Copilot with Evaluation Harness

**Status:** Draft v1
**Owner:** Ayush Barot
**Last updated:** 2026-06-30
**Target build time:** ~12 focused days (solo)

---

## 0. TL;DR

Build a retrieval-augmented copilot that answers maintenance and troubleshooting
questions about industrial equipment by **fusing three heterogeneous data types** —
time-series sensor telemetry, a structured asset hierarchy, and unstructured
maintenance documents — into single, grounded, cited answers. Ship it with an
**automated evaluation harness** that measures retrieval quality, answer
faithfulness, routing accuracy, and abstention behavior, wired into a regression
test so every change produces a measurable before/after.

This is deliberately modeled on Cognite's actual product problem (heterogeneous
industrial data made queryable via a trustworthy copilot, used for equipment
troubleshooting and root-cause analysis in a domain where hallucinations are
unacceptable), scoped down to something one person can finish and demonstrate.

---

## 1. Problem & Motivation

Industrial systems generate **heterogeneous data** — sensor time series, control
systems, engineering models, asset hierarchies, work orders, and manuals — that
stays fragmented and hard to use without contextualization. The valuable questions
("is this sensor anomaly a known fault, and what's the procedure?") require fusing
*structured telemetry* with *unstructured documentation*, cross-referenced through
an *asset model*.

Most RAG portfolio projects stop at "chunk a PDF, embed it, answer questions." That
demonstrates plumbing, not judgment. The differentiator — and the thing that makes
the Cognite-style pitch credible — is **deterministic, trustworthy responses even
for complex questions, in a domain with near-zero tolerance for hallucination.**

That constraint is the design center of this project, not a footnote:
- Every answer must cite its evidence (which doc chunk, which sensor query).
- The system must **abstain** ("I don't have enough information") rather than guess.
- Quality must be **measured**, not asserted.

---

## 2. Goals & Non-Goals

### Goals
1. Fuse 3 heterogeneous data sources (time series + structured metadata + documents)
   into one queryable system.
2. Route queries intelligently between retrieval paths (doc lookup / time-series
   lookup / fusion).
3. Force citation and support explicit abstention.
4. Ship an automated eval harness with a hand-labeled golden set and regression
   testing.
5. Deploy a usable demo (API + thin UI) with cost/latency logging.
6. Produce a README that leads with eval results and the architecture, including an
   honest failure-case study.

### Non-Goals
- Not a production multi-tenant system. No auth, no scaling, no real-time streaming.
- Not a general chatbot. Scope is industrial equipment troubleshooting only.
- Not a fine-tuning project. Use off-the-shelf embedding + LLM APIs.
- Not a fancy frontend. UI is a means to demo, not the deliverable.

---

## 3. The Data

### 3.1 Primary source — NASA CMAPSS Turbofan Degradation (real time series)

**What it is:** Simulated run-to-failure turbofan engine degradation data from
NASA's Prognostics Center of Excellence (C-MAPSS = Commercial Modular Aero-Propulsion
System Simulation). Each engine runs from healthy operation until failure; sensor
readings drift as the engine degrades. This is your "live equipment telemetry."

**Where to get it (in order of preference):**
1. **NASA Open Data Portal** — search "CMAPSS Jet Engine Simulated Data" at
   <https://data.nasa.gov>. Downloads as a `.zip`.
2. **NASA PCoE Prognostics Data Repository** — the original source:
   <https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/>
3. **Kaggle mirror** (often the fastest, identical files): search
   "NASA CMAPSS" / "Turbofan Engine Degradation Simulation Data Set" on kaggle.com.

> Verify the download before building on it: the archive should contain
> `train_FD001.txt … train_FD004.txt`, matching `test_FD00X.txt`, and
> `RUL_FD00X.txt` files, plus a `readme.txt`. If a mirror is missing the RUL files
> or renames columns, prefer the NASA portal copy.

**File structure:** Four sub-datasets (FD001–FD004) with increasing difficulty:

| Dataset | Operating conditions | Fault modes |
|---------|---------------------|-------------|
| FD001   | 1                   | 1 (HPC degradation) |
| FD002   | 6                   | 1 |
| FD003   | 1                   | 2 (HPC + fan degradation) |
| FD004   | 6                   | 2 |

Start with **FD001** — single operating condition, single fault mode, simplest to
reason about. Add FD003/FD004 later if you want harder fusion queries.

**Schema (space-delimited `.txt`, no header):**

```
col 1:      unit_number        (engine ID, 1..N)
col 2:      time_in_cycles     (operational cycle counter; increments to failure)
col 3:      op_setting_1       (operational setting)
col 4:      op_setting_2       (operational setting)
col 5:      op_setting_3       (operational setting)
col 6..26:  sensor_1 .. sensor_21   (temperatures, pressures, fan/compressor speeds, etc.)
```

- `train_*`: each engine runs to failure (last cycle = failure point).
- `test_*`: each engine is truncated before failure.
- `RUL_*`: the true Remaining Useful Life (cycles left) for each test engine.
- Readings include realistic sensor noise.

**Known quirk:** several of the 21 sensors are flat/constant in FD001 and carry no
information. Identifying and dropping these is a legitimate data-quality step worth
documenting (it shows you actually looked at the data).

**Sensor meaning (for grounding your synthetic docs):** the readme maps sensors to
physical quantities — e.g. fan inlet temperature, LPC/HPC outlet temperatures,
physical/corrected fan & core speeds, bypass ratio, bleed enthalpy, etc. Use the
real names/units from the readme so your synthetic documents are internally
consistent with the data.

### 3.2 Synthetic source — Asset hierarchy (structured metadata)

You generate a small asset/equipment hierarchy mimicking Cognite's data-model layer:

```
Fleet
 └─ Engine (unit_number)
     ├─ Subsystem: Fan
     ├─ Subsystem: LPC (Low-Pressure Compressor)
     ├─ Subsystem: HPC (High-Pressure Compressor)
     ├─ Subsystem: Combustor
     ├─ Subsystem: HPT / LPT (turbines)
     └─ Sensors (sensor_1..21) → each mapped to a subsystem + physical quantity + nominal range
```

Store as a relational table (or a small knowledge graph if you want to show off).
Minimum columns: `sensor_id, subsystem, physical_quantity, unit, nominal_min,
nominal_max, alarm_threshold`. This is the join layer that makes fusion queries
possible ("sensor 11 belongs to the HPC, here's its nominal range").

### 3.3 Synthetic source — Maintenance documents (unstructured text)

Generate **15–25 documents** (depth of querying matters more than corpus size),
grounded in the real CMAPSS sensor names/ranges so they're internally consistent:

- **Equipment manuals**: inspection intervals, operating limits, subsystem
  descriptions, recommended actions per fault code.
- **Maintenance logs / work orders**: dated entries referencing engines, fault
  codes, sensor readings, and actions taken.
- **Fault-code reference**: a table of fault codes → symptoms (which sensors deviate
  and how) → recommended procedure.

**This is legitimate, not cheating** — generating realistic synthetic docs grounded
in real data is a standard technique. Be transparent about it in the README. Keep a
generation script (and the prompts used) in the repo so the corpus is reproducible.

> **Trap to avoid:** keep the synthetic docs *consistent* with the sensor data
> (thresholds, sensor IDs, subsystem assignments must match §3.2). Inconsistency
> will surface as eval failures and is hard to debug later.

---

## 4. Query Types (the part that demonstrates judgment)

The system must handle three classes, and the eval set must cover all three:

1. **Pure document lookup**
   *"What's the recommended inspection interval for the HPC?"*
   → vector/keyword retrieval over docs only.

2. **Pure time-series lookup**
   *"What was sensor 4's trend for engine 23 over its last 50 cycles?"*
   → structured query over CMAPSS only.

3. **Fusion (the hard, valuable ones)**
   *"Engine 47 is showing elevated sensor 11 readings — is this consistent with a
   known fault pattern, and what does the manual say to do about it?"*
   → query telemetry, look up the sensor→subsystem→threshold mapping, retrieve the
   matching fault-code doc, **then synthesize both into one grounded answer.**

Category 3 is the whole point and is structurally identical to what Cognite's
copilot must do, at portfolio scale.

---

## 5. Architecture

```
User Query
   │
   ▼
Query Router  ── classify → { doc-lookup | timeseries-lookup | fusion }
   │
   ├──► Vector retrieval (hybrid: dense embeddings + BM25) ──► Maintenance docs / manuals / fault codes
   │
   ├──► Structured query tool (DuckDB/SQL or pandas) ─────────► CMAPSS sensor data + asset hierarchy
   │
   ▼
Synthesis (LLM, grounded in retrieved evidence, citations REQUIRED)
   │
   ▼
Answer + source attribution + confidence/abstention signal
```

### Deliberate engineering decisions (document the *why* for each)

- **Hybrid retrieval (dense + BM25).** Exact fault-code / sensor-ID matching matters
  as much as semantic similarity. Pure vector search misses "FD003" or "sensor_11"
  as exact tokens; BM25 catches them.
- **A routing / tool-calling layer**, not a monolithic prompt. This is what lets you
  say "I built a system, not a wrapper." Use the LLM's tool/function calling to pick
  the path and to issue structured queries.
- **Forced citation.** Every answer cites which chunk or which sensor query produced
  it. Ungrounded answers are a worse failure than no answer in this domain.
- **Explicit abstention.** When retrieval confidence is low or the question is
  out-of-scope, return "I don't have enough information" — and *test for this*.

### Suggested tech stack (don't over-think it)
- **Language:** Python 3.11+
- **Telemetry store:** DuckDB (zero-setup, fast, SQL over the CMAPSS files). Postgres
  is fine if you prefer.
- **Vector store:** Chroma or LanceDB (local, simple). FAISS if you want raw control.
- **Keyword:** `rank_bm25` or the vector store's built-in hybrid mode.
- **LLM + embeddings:** Anthropic Claude for synthesis/routing (use the latest
  capable model, e.g. Claude Opus / Sonnet 4.x) + an embedding model for retrieval.
  Keep the model behind one thin client module so you can swap it.
- **API:** FastAPI. **UI:** Streamlit or Gradio.
- **Eval:** plain pytest + a small harness module; log runs to CSV/JSON.

---

## 6. Evaluation Harness (the real differentiator)

Build a **golden dataset of 40–60 Q/A pairs** spanning all three query types, each
labeled by hand with: the question, the correct answer, the correct source(s)
(doc chunk IDs and/or the sensor query), and a category tag. Include ~5–10
**out-of-scope / unanswerable** questions to test abstention.

Automated scoring dimensions:

| Dimension | Metric | How |
|-----------|--------|-----|
| **Retrieval quality** | precision/recall@k | compare retrieved sources vs. labeled correct sources |
| **Faithfulness** | % of answer claims traceable to retrieved evidence | LLM-as-judge, **validated against a hand-labeled subset first** so you trust the judge |
| **Routing accuracy** | % correct path chosen | compare router output vs. labeled category |
| **Abstention** | correct-decline rate | does it decline out-of-scope/low-confidence Qs instead of hallucinating |

**Wire this into a regression test that runs on every change.** The before/after
delta when you improve chunking or retrieval is your strongest portfolio artifact —
stronger than the demo itself.

> Validate the LLM judge before trusting it: hand-label faithfulness on ~15
> examples, run the judge on the same 15, and report the agreement rate in the
> README. An unvalidated LLM judge is just another unmeasured claim.

---

## 7. Build Sequence (so it doesn't sprawl)

| Days | Milestone | Definition of done |
|------|-----------|-------------------|
| 1–2  | Data foundation | CMAPSS loaded into DuckDB; synthetic 15–25 doc corpus generated (reproducibly); asset hierarchy table built and consistent with docs |
| 3–4  | Baseline RAG (docs only) | End-to-end: embed → vector store → retrieve → answer with citations. Working before adding complexity. |
| 5–6  | Structured tool + router | Time-series query tool + routing layer. The architecturally interesting part — budget real time. |
| 7–8  | Golden eval set | 40–60 hand-labeled Q/A pairs across all 3 types + abstention cases |
| 9–10 | Automated scoring + iterate | Scoring runs; validate the LLM judge; iterate retrieval on what eval reveals. Document 1–2 embarrassing failures as a mini case study. |
| 11–12| Deploy + README | FastAPI + Streamlit/Gradio; cost/latency logging; README with architecture diagram + eval results front and center |

**Discipline:** get each milestone working end-to-end before adding the next layer.
The eval set (days 7–8) is tedious but it's the part that proves rigor — don't skip
or rush it.

---

## 8. README — what a recruiter/interviewer actually reads

Lead with, in this order:
1. **One-paragraph problem statement** naming the Cognite-style problem explicitly:
   *"Industrial systems generate heterogeneous data — sensors, documents, asset
   hierarchies — that's hard to query as a fused whole. This is a copilot that fuses
   them into grounded, cited answers."* (Makes relevance obvious without you having
   to explain it in an interview.)
2. **Eval results table** (the §6 metrics) — not a feature list.
3. **Architecture diagram** + one paragraph.
4. **Failure case study** — 1–2 real failures the eval surfaced and how you
   diagnosed/fixed them. Reads as honest engineering, not a polished sales demo.
5. Setup/run instructions + a note on the synthetic-data methodology (transparency).

---

## 9. Success Metrics

- All three query types answered correctly on the golden set (target: define a
  realistic bar after your first eval run, e.g. ≥0.8 retrieval recall@5, ≥0.9
  routing accuracy, ≥0.85 faithfulness, ≥0.9 correct abstention).
- A documented, reproducible before/after improvement from at least one retrieval
  iteration.
- Demo runs end-to-end with logged cost/latency per query.

---

## 10. Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Scope creep (FD002/4, fancy UI, multi-tenant) | Lock to FD001 + thin UI for v1; everything else is "future work" |
| Synthetic docs inconsistent with data | Generate from the asset-hierarchy table as source of truth; lint consistency |
| LLM judge unreliable | Validate against hand labels before trusting; report agreement |
| Fusion routing flaky | Start with explicit category classification; only add complexity if eval demands it |
| Dataset mirror differs | Prefer NASA portal copy; verify file manifest before building |

---

## 11. Getting Started with Claude Code

**Install** (requires Node.js 18+):
```bash
npm install -g @anthropic-ai/claude-code
```

**Start in this project directory:**
```bash
cd /Users/ayushbarot/Personal/Proj_1
claude
```
(First run will prompt you to authenticate.)

### Set up `CLAUDE.md` first
Run `/init` inside Claude Code, or create a `CLAUDE.md` at the repo root with project
context Claude should always know. Seed it with:
- The project summary (copy §0 TL;DR + §2 goals from this PRD).
- The data schema (§3) and the hard rule that **synthetic docs must stay consistent
  with the asset hierarchy**.
- The non-negotiables: **forced citation, abstention over guessing, every change
  must keep the eval suite green.**
- Commands: how to load data, run the API, run the eval harness.

### How to work with it (from Anthropic's best-practices guidance)
- **Plan before code.** For each milestone in §7, ask Claude to propose a plan first
  (use plan mode), review it, then let it implement. Planning first beats one giant
  "build everything" prompt.
- **Work in tight loops.** One milestone at a time; verify end-to-end before moving
  on (matches §7's discipline).
- **Give it the eval harness as a feedback loop.** Once §6 exists, tell Claude to run
  the eval after changes and iterate on the numbers — this is where an agentic tool
  shines.
- **Be specific and supply context.** Point Claude at this PRD, the CMAPSS readme, and
  the schema rather than describing them from memory.
- **Commit often** so you can show the before/after deltas the README needs.

### Suggested first prompts
1. *"Read PRD.md. Set up the repo skeleton (folders, deps, DuckDB loader for
   CMAPSS FD001) per milestone 1. Show me a plan before writing code."*
2. *"Generate the asset-hierarchy table (sensor → subsystem → nominal range) as the
   source of truth, then generate 15–25 synthetic maintenance docs grounded in it.
   Keep the generation script in the repo."*
3. *"Build the docs-only baseline RAG (milestone 2) end-to-end with forced
   citations. Don't add the router yet."*

---

## Appendix A — CMAPSS column reference (FD001)

```
unit_number | time_in_cycles | op_setting_1 | op_setting_2 | op_setting_3 |
sensor_1 | sensor_2 | ... | sensor_21
```
Consult the dataset's `readme.txt` for the physical quantity and unit behind each
sensor index; use those exact names in your synthetic docs. Note that some sensors
are constant in FD001 and should be dropped — document which and why.
