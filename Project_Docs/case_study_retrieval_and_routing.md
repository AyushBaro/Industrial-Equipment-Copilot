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
