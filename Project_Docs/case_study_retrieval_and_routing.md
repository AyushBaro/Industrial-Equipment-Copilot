# Case Study: Two Failure Modes in a Fusion Query (and How the Eval Harness Will Fix Them)

> **README material.** This documents two real, reproducible weaknesses found the
> first time the fusion path ran end-to-end (Phase 3, 2026-06-30), *before* any eval
> harness or tuning. They are kept deliberately so Phase 5 can show a measurable
> before/after. Honest failure analysis is the point — a system you can't see failing
> is a system you can't trust.

## The query

> *"Engine 47 is showing elevated Ps30 readings — is this consistent with a known
> fault pattern, and what does the manual say to do about it?"*

This is the flagship **fusion** question: it needs (a) the live sensor reading for
engine 47, (b) the known-fault pattern, and (c) the recommended procedure from the
manual — combined into one cited answer.

## What the system answered (baseline, pre-Phase-5)

> "Engine 47 is showing a known fault pattern of HPC degradation, indicated by the
> 'pressure-loss-first' presentation with Ps30 readings rising but still below the
> threshold. **The manual does not provide specific actions for this pattern**, but the
> work order suggests monitoring and potentially escalating if conditions persist."
>
> **Citations:** `wo-1002-engine47`, `telemetry:engine47/sensor11/trend(last_n=50)`

The routing and fusion machinery worked — it correctly classified the query as fusion,
pulled telemetry, retrieved a document, and cited both, with every citation verified
against what was actually retrieved. But the *answer quality* is wrong in two ways.

---

## Finding 1 — Retrieval ranks incident records over canonical procedure

**Symptom.** The answer claims "the manual does not provide specific actions." That is
false: `manual-hpc` and `fault-FC-HPC-001` both contain the exact procedure (reduce
borescope interval to 10 cycles, compressor wash, re-baseline, schedule removal if
still in alarm). They were simply never retrieved.

**Evidence — top-5 retrieved chunks for the query:**

| Rank | Fused score | Document | Section |
|------|-------------|----------|---------|
| 1 | 0.03178 | `wo-1002-engine47` | Observation |
| 2 | 0.03055 | `wo-1002-engine47` | overview |
| 3 | 0.01639 | `wo-1001-engine24` | Observation |
| 4 | 0.01613 | `wo-1001-engine24` | Status |
| 5 | 0.01613 | `manual-combustor` | Overview |

The canonical sources (`manual-hpc`, `fault-FC-HPC-001`) **did not appear in the top
5 at all** — an irrelevant combustor manual outranked them.

**Root cause.** Both dense and sparse retrieval reward surface overlap with the query
string. The work orders contain the literal tokens "engine 47" and "Ps30," so they
dominate. The canonical procedure docs describe the *pattern* generically ("HPC
degradation," "Ps30 rising") and never mention engine 47, so they score lower —
exactly backwards from what a maintenance engineer wants.

**Why it matters.** In a low-tolerance domain, retrieving a past incident instead of
the authoritative procedure produces a confidently wrong "the manual says nothing"
answer. The citation was verified and *honest* — the system really did use that work
order — which is precisely why the failure is a retrieval problem, not a hallucination.

**Planned fix (Phase 5, measured against the golden set).**
- Boost `manual` / `fault_code` document types for fusion-route queries (a maintenance
  question wants procedure, not incident history).
- Raise retrieval `k` and/or retrieve per-type, so at least one manual and one fault
  code always enter the synthesis context.
- Re-measure retrieval recall@k for the canonical doc on fusion questions before/after.

---

## Finding 2 — Router prefers `trend` where `status` is the right tool

**Symptom.** The answer says Ps30 is "rising but still below the threshold." It is
**not** below threshold — at engine 47's last cycle Ps30 is in alarm.

**Evidence — the two tools on the same sensor:**

```
TREND  (what the router chose):
  Engine 47 Ps30 over last 50 cycles: 47.55 → 48.28 (rising).

STATUS (more accurate for this question):
  Engine 47 Ps30 at cycle 214: 48.28 (IN ALARM; nominal 46.98–47.73; threshold 48.10).
```

The end value 48.28 exceeds the 48.10 alarm threshold — Ps30 **is** in alarm. The
trend tool reports only start→end and a direction word, so the synthesis model, given
"rising," hedged to "still below the threshold." The status tool makes the alarm
explicit (value vs threshold vs nominal band).

**Root cause.** The router maps "elevated / known fault?" questions to the `trend`
intent because the user said "readings." But the *question being asked* is a
threshold/alarm judgment, which the `status` tool answers directly. The right tool was
available; the router picked the weaker one.

**Why it matters.** A trend can be read either way; a status check is unambiguous. For
"is this a problem?" questions, the system should reach for the tool that compares
against the thresholds it already knows.

**Planned fix (Phase 5, measured against routing labels).**
- Bias the router toward `status` (or run both `status` and `trend`) when a
  fusion/alarm-style question asks whether a reading is a problem.
- Add routing-accuracy and "correct-tool" checks to the eval harness so the change is
  validated, not vibes.

---

## What this case study demonstrates

1. **The guarantees held even while the answer was wrong.** Routing, fusion, and
   citation-verification all functioned; every citation traced to a real retrieved
   source. The failure was in *what got retrieved* and *which tool ran* — observable,
   localizable problems, not silent hallucination.
2. **The architecture made the failure diagnosable.** Because telemetry and documents
   are cited with explicit handles, the wrong answer points straight at its causes.
3. **This is why the project leads with evaluation.** Both fixes are deferred to Phase
   5 on purpose: tuning retrieval by hand, before a golden set exists, is guessing.
   With the harness in place, each fix produces a number that moved — the
   before/after delta that proves the engineering, not just the demo.

*Status: baseline captured Phase 3. Fixes + measured before/after to follow in Phase 5.*

---

## Phase 5 addendum — what the human judge-validation review surfaced (2026-07-06)

Findings 1–2 were found by eye. Findings 3–4 below were found *by the eval harness plus
a human validating the LLM judge* — the exact workflow the project is built around. A
15-row blind hand-labeling of the faithfulness judge (`make eval-judge`) produced **raw
agreement 0.867 (13/15), Cohen's κ 0.44**, and — more valuably — two disagreements and a
set of margin notes that localized three additional bugs.

### The methodology insight (why κ was low, and it's not the judge's fault)

Both human/judge disagreements (`g003`, `g039`) were the **same definitional split**: the
system *abstained*, the human called that a failure, the judge called it "faithful."
Both are correct on their own terms — an abstention makes no false claim, so it cannot be
*unfaithful*; but refusing a question you have the answer to *is* a failure. Conclusion:

> **Faithfulness (grounding) structurally cannot see over-abstention. It must always be
> reported alongside the over-abstention rate, never as a standalone proxy for answer
> quality.** The judge is trustworthy for what we use it for (detecting hallucination);
> κ was depressed by a definition gap, not by judge error.

### Finding 3 — The synthesizer abstains with the answer in its context

**Symptom.** On `g003` ("What is the alarm threshold for T50?") the model replied *"I
don't have enough information"* — even though `manual-lpt` **§4 Alarm response**
(`T50 ≥ 1428.11 degR`) and **§2** (the parameter table) were both in its context. Same on
`g004` ("what action was taken for engine 24?"): the retrieved `wo-1001` **Action taken**
section literally lists the actions ("reduce HPC borescope interval to 10 cycles,
compressor wash, begin RUL tracking") and the model still abstained.

**Root cause.** Not the code relevance floor (`should_abstain` can't trigger — RRF scores
are always > 0). The model itself set `sufficient=false`. The synthesis system prompt
framed abstention as the safe default ("never guess"), so the model over-refused whenever
the answer required reading a table or wasn't spoon-fed in prose.

**Why it matters.** This is the single biggest drag on `fact_recall` (0.47 baseline): a
correct, retrievable answer scored as a total miss. Over-abstention (0.25) and low
fact-recall are the *same* bug seen through two metrics.

**Fix (this phase).** Rebalance the synthesis prompt: abstain *only* when the sources
genuinely lack the answer; answer (and cite) when a source contains the fact, even in a
table or across entries. The anti-hallucination guarantee is unchanged — outside
knowledge is still forbidden and every claim is still code-verified against a real source.

### Finding 4 — The router false-negatives an in-scope question as out-of-scope

**Symptom.** On `g005` ("Why is the burner fuel-air ratio not used for trend
monitoring?") the router returned `out_of_scope` ("unrelated to the fleet"), so nothing
was ever retrieved — yet `manual-combustor` answers the question directly (and dense
retrieval ranks it #1–#2 when actually run). A human reviewer's margin note ("No source
retrieved??") caught it; the metric alone would have logged it only as one routing miss.

**Root cause.** The router treats domain-relevant *conceptual* questions (why a sensor
isn't trend-monitored) as off-topic because they don't name an engine or a fault. It
conflates "no engine/sensor mentioned" with "out of scope."

**Fix (later this phase).** Tighten the router's out-of-scope criterion to key on *fleet
relevance*, not on whether a specific engine/sensor is named; add these conceptual
doc-questions to the routing checks so the fix is measured.

*Findings 3–4 confirmed against the corpus and the cached baseline predictions.*

---

## Fixes applied and measured (2026-07-07)

All numbers are means over **3 eval runs** (`make eval-score ARGS="--runs 3"`), because
gpt is not deterministic even at temperature 0 and single-run metrics wobble by ~±1–2
rows on borderline abstention cases. Ranges below are min–max across the three runs.

### Fix 1 — synthesizer over-abstention (Finding 3)

Rebalanced the synthesis prompt: abstain only when the sources genuinely lack the answer;
answer + cite when a source contains the fact, even in a table. Anti-hallucination
guarantee unchanged. `g003`/`g004`/`g006` — flagged in the human review — now answer with
citations. Biggest single lift on `fact_recall`.

### Fix 2 — type-aware fusion retrieval (Finding 1)

Root cause was that engine-named work orders out-rank the generic canonical procedure in
both retrievers. Fix: for fusion-route queries, add a **type-restricted dense list
(manuals + fault codes) as a third RRF input**, so the authoritative doc reliably earns a
top-k slot — no score hand-tuning, no change for doc-route queries (which may legitimately
want a work order). The flagship query now retrieves *and cites* `fault-FC-HPC-001` and
`manual-hpc` (both previously absent from the top 5); `g033`/`g039` stopped abstaining.

**Measured effect (3-run means):**

| Metric | Baseline (Phase 5 start) | After Fix 1 | After Fix 2 | Target |
|---|---|---|---|---|
| retrieval recall@5 | 0.804 | 0.813 (0.804–0.817) | **0.867** (0.867) | ≥ 0.80 |
| routing accuracy | 0.940 | 0.940 | 0.940 | ≥ 0.90 |
| faithfulness (grounding) | 0.975¹ | 0.950 | **1.000** | ≥ 0.85 |
| fact_recall (completeness) | 0.473 | 0.563 | 0.595 | — |
| correct abstention (OOS) | 1.000 | 1.000 | 1.000 | ≥ 0.90 |
| over-abstention (in-scope refused) | 0.250 | 0.192 (0.175–0.200) | **0.158** (0.125–0.200) | → 0 |

¹ Baseline faithfulness/fact_recall are single-run (the N-run harness landed with Fix 1).

**Why faithfulness rose with Fix 2.** The two ungrounded rows before the fix (`g031`,
`g034`) were fusion answers resting only on work orders; once the canonical manual/fault
code entered their context, their claims became fully supported. Better retrieval bought
better grounding — not just better recall.

**Still open:** Finding 2 (router prefers `trend` over `status` — `g031`'s telemetry is
still a trend) and Finding 4 (router false-negatives conceptual in-scope questions —
`g005`). Both are routing-side and untouched by Fixes 1–2.
