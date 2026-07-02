"""Generate 60 candidate golden-eval rows with pre-filled PROPOSED labels.

Doc / fusion / out-of-scope questions are authored here (grounded in the corpus I
wrote). Time-series answers are COMPUTED from the data via the query tools, so they are
objective ground truth, not guesses. Every row starts as status="unreviewed" — the
human reviewer approves/edits/rejects (see src/eval/review.py).

Run:  python -m src.eval.generate_candidates
"""
from __future__ import annotations

import json

from src import config
from src.rag import timeseries as ts

# ---------------------------------------------------------------------------
# DOC candidates — answerable from a single corpus document.
# (question, expected_sources, answer_key_facts, difficulty, notes)
# ---------------------------------------------------------------------------
DOC = [
    ("What is the recommended inspection interval for the HPC?",
     ["manual-hpc"], ["borescope every 30 cycles", "every 10 cycles once in alarm"], "easy", ""),
    ("What does fault code FC-HPC-001 mean and what is its primary sensor signature?",
     ["fault-FC-HPC-001"], ["HPC degradation", "T30 rising >=1607.89", "Ps30 rising >=48.10",
                            "P30 falling <=551.16", "phi falling <=519.69"], "medium", ""),
    ("What is the alarm threshold for the LPT outlet temperature T50?",
     ["manual-lpt"], ["T50 alarm >= 1428.11 degR"], "easy", ""),
    ("What action was taken for engine 24's HPC over-temperature advisory?",
     ["wo-1001-engine24"], ["borescope reduced to every 10 cycles", "compressor wash scheduled",
                            "RUL tracking started"], "medium", ""),
    ("Why is the burner fuel-air ratio not used for trend monitoring?",
     ["manual-combustor"], ["farB held constant ~0.03", "no measurable degradation trend"], "medium", ""),
    ("What is the alarm condition for the HPT coolant bleed W31?",
     ["manual-hpt"], ["W31 alarm <= 38.35 lbm/s (low)"], "easy", ""),
    ("How often should the LPC be inspected?",
     ["manual-lpc"], ["gas-path inspection every 40 cycles", "inspected with the HPC"], "easy", ""),
    ("Which fault codes exist and what subsystem does each cover?",
     ["fault-code-reference"], ["FC-HPC-001 HPC", "FC-LPT-001 LPT", "FC-FAN-001 Fan", "FC-HPT-001 HPT"], "medium", ""),
    ("What is the primary signature of fault code FC-LPT-001?",
     ["fault-FC-LPT-001"], ["T50 rising >= 1428.11", "W32 falling <= 23.00"], "medium", ""),
    ("What are the alarm thresholds for core speed (Nc and NRc)?",
     ["manual-core-engine"], ["Nc alarm >= 9092.00 rpm", "NRc alarm >= 8169.77 rpm"], "medium", ""),
    ("What is the recommended procedure once FC-HPC-001 is confirmed?",
     ["fault-FC-HPC-001"], ["confirm over 5 cycles", "reduce borescope to 10 cycles",
                            "compressor wash then re-baseline", "schedule removal if still in alarm"], "hard", ""),
    ("What did the work order for engine 58 find, and what fault code was raised?",
     ["wo-1007-engine58"], ["htBleed >= 397.50 with T30 in alarm", "FC-HPC-001", "late-life indicator"], "medium", ""),
    ("Which fan sensors are non-informative under FD001 conditions?",
     ["manual-fan"], ["T2, P2, P15, Nf_dmd, PCNfR_dmd held constant", "excluded from trend monitoring"], "medium", ""),
    ("What does a rising bypass ratio (BPR) with no HPC alarm indicate?",
     ["manual-fan"], ["usually secondary effect, not a fan fault", "correlate with HPC first"], "hard", ""),
    ("What was observed and done for engine 91's combined LPT event?",
     ["wo-1009-engine91"], ["T50 >= 1428.11 and W32 <= 23.00", "FC-LPT-001 with HPC elevated",
                            "end-of-life planning"], "hard", ""),
]

# ---------------------------------------------------------------------------
# FUSION candidates — need BOTH telemetry (a specific engine/sensor) and docs.
# (question, engine, sensor, expected_doc_sources, extra_facts, difficulty, notes)
# The correct telemetry tool here is STATUS (a threshold/alarm judgment).
# ---------------------------------------------------------------------------
FUSION = [
    ("Engine 47 is showing elevated Ps30 readings — is this a known fault pattern, and what does the manual say to do?",
     47, 11, ["fault-FC-HPC-001", "manual-hpc"], ["HPC degradation pattern", "compressor wash / reduce borescope interval"],
     "hard", "KNOWN-HARD: baseline system retrieves work orders over manuals and uses trend not status (see case study)."),
    ("Engine 47's HPC discharge temperature T30 looks high — is that a known fault and what is the procedure?",
     47, 3, ["fault-FC-HPC-001", "manual-hpc"], ["T30 over-temp", "compressor wash, re-baseline"], "hard", ""),
    ("Engine 91's LPT outlet temperature is elevated — what fault is this and what should we do?",
     91, 4, ["fault-FC-LPT-001", "manual-lpt"], ["LPT thermal degradation", "inspect blades/exhaust, check coolant"], "hard", ""),
    ("Engine 12 shows rising core speed — what's happening and is it a known issue?",
     12, 9, ["fault-FC-HPC-001", "manual-core-engine"], ["core compensating for gas-path loss", "localize via HPC"], "hard", ""),
    ("Engine 5's HPT coolant bleed W31 is dropping — is it in alarm and what does the manual advise?",
     5, 20, ["manual-hpt"], ["W31 low alarm", "inspect coolant passages and HP shaft seals"], "medium", ""),
    ("Is engine 76's LPT temperature a problem, and what fault code would apply?",
     76, 4, ["fault-FC-LPT-001", "manual-lpt"], ["check T50 vs 1428.11", "FC-LPT-001 if with W32 low"], "medium", ""),
    ("Engine 58's bleed enthalpy htBleed is rising — is this a known fault and what does it indicate?",
     58, 17, ["fault-FC-HPC-001", "manual-core-engine"], ["rising core temps", "late-life HPC-degradation indicator"], "hard", ""),
    ("Is engine 89's Ps30 a concern, and what should we do about it?",
     89, 11, ["manual-hpc"], ["compare Ps30 vs nominal 46.98-47.73", "if nominal, no action"], "medium", "Nominal case: correct answer is 'not in alarm, no action'."),
    ("Engine 91's LPT coolant bleed W32 is low — what fault does this point to?",
     91, 21, ["fault-FC-LPT-001", "manual-lpt"], ["W32 low with T50 high", "FC-LPT-001"], "hard", ""),
    ("Engine 47's HPC discharge pressure P30 is dropping — is that a known fault?",
     47, 7, ["fault-FC-HPC-001", "manual-hpc"], ["P30 falling is HPC efficiency loss", "part of FC-HPC-001 signature"], "hard", ""),
    ("Engine 12's corrected core speed NRc looks high — what does that mean and is it known?",
     12, 14, ["manual-core-engine", "fault-FC-HPC-001"], ["core compensating", "localize via HPC"], "hard", ""),
    ("Engine 33's bypass ratio BPR is elevated — is this a fan fault or something else?",
     33, 15, ["manual-fan"], ["rising BPR usually secondary", "correlate with HPC before blaming fan"], "medium", ""),
    ("Engine 24's HPC discharge temperature T30 is high — what's the fault and the procedure?",
     24, 3, ["fault-FC-HPC-001", "manual-hpc"], ["T30 over-temp", "reduce borescope to 10 cycles, wash"], "medium", ""),
    ("Engine 5's LPT coolant bleed W32 — is there an LPT coolant issue?",
     5, 21, ["manual-lpt", "fault-FC-LPT-001"], ["check W32 vs 23.00", "shared-supply check with W31"], "medium", ""),
    ("Engine 76's LPT outlet temperature T50 is elevated — is this end-of-life degradation?",
     76, 4, ["fault-FC-LPT-001", "manual-lpt"], ["T50 vs 1428.11", "late-life if with HPC alarm"], "hard", ""),
]

# ---------------------------------------------------------------------------
# TIME-SERIES candidates — answer computed from the data.
# (question, engine, sensor|None, intent, difficulty, notes)
# ---------------------------------------------------------------------------
TIMESERIES_SPECS = [
    ("What was sensor 4's trend for engine 23 over its last 50 cycles?", 23, 4, "trend", "easy", ""),
    ("Show me the Ps30 trend for engine 1.", 1, 11, "trend", "easy", ""),
    ("How has the HPC discharge temperature T30 changed for engine 5?", 5, 3, "trend", "medium", ""),
    ("Is engine 12's core speed in alarm right now?", 12, 9, "status", "medium", ""),
    ("Is engine 89's HPC static pressure Ps30 within nominal range?", 89, 11, "status", "medium", ""),
    ("Give me an overview of engine 76's current status.", 76, None, "overview", "easy", ""),
    ("How many operational cycles does engine 100 have?", 100, None, "overview", "easy", ""),
    ("What is the current status of all sensors on engine 47?", 47, None, "status", "medium", ""),
    ("Show the LPT outlet temperature T50 trend for engine 91.", 91, 4, "trend", "medium", ""),
    ("Is the HPT coolant bleed W31 in alarm on engine 5?", 5, 20, "status", "medium", ""),
    ("What's the trend of bleed enthalpy htBleed on engine 58?", 58, 17, "trend", "medium", ""),
    ("Overview of engine 33, please.", 33, None, "overview", "easy", ""),
    ("Is engine 24's HPC discharge temperature T30 in alarm?", 24, 3, "status", "medium", ""),
    ("Show the LPT coolant bleed W32 trend for engine 91.", 91, 21, "trend", "medium", ""),
    ("What is the corrected core speed NRc trend on engine 12?", 12, 14, "trend", "medium", ""),
]

# ---------------------------------------------------------------------------
# OUT-OF-SCOPE / unanswerable — correct behavior is abstention.
# ---------------------------------------------------------------------------
OUT_OF_SCOPE = [
    ("What is the tire pressure of a Boeing 747 main landing gear?", "unrelated to this fleet's telemetry/docs"),
    ("What's the current stock price of the engine manufacturer?", "not in scope"),
    ("Show me the sensor trend for engine 999.", "engine 999 does not exist (1-100)"),
    ("What was the sensor trend last week?", "no engine identified; dataset is cycle-indexed, not dated"),
    ("What will the weather be tomorrow at the test facility?", "unrelated"),
    ("Who won the 2022 World Cup?", "unrelated"),
    ("How do I reset my maintenance-portal password?", "not covered by corpus"),
    ("What color is engine 47 painted?", "not in the data or docs"),
    ("Give me the trend for engine 250.", "engine out of range (1-100)"),
    ("What is sensor 45's reading on engine 10?", "sensor out of range (1-21)"),
]


def _ts_answer(engine, sensor, intent):
    """Compute objective telemetry ground truth + a normalized expected handle."""
    if intent == "overview":
        r = ts.engine_overview(engine)
        facts = [f"{r['n_cycles']} operational cycles",
                 f"{len(r['alarms'])} sensors in alarm at last cycle"]
        return f"telemetry:engine{engine}/overview", facts
    if intent == "status":
        r = ts.sensor_status(engine, sensor)
        if sensor:
            s = r["statuses"][0]
            facts = [f"{s['symbol']}={s['value']}", "in alarm" if s["in_alarm"] else "nominal",
                     f"nominal {s['nominal_min']}-{s['nominal_max']}"]
            return f"telemetry:engine{engine}/sensor{sensor}/status", facts
        facts = [f"{len(r['alarms'])} of {len(r['statuses'])} informative sensors in alarm"]
        if r["alarms"]:
            facts.append("in alarm: " + ", ".join(a["symbol"] for a in r["alarms"]))
        return f"telemetry:engine{engine}/all/status", facts
    # trend
    r = ts.sensor_trend(engine, sensor)
    facts = [f"{r['symbol']} {r['start']:.2f} -> {r['end']:.2f}", r["direction"]]
    return f"telemetry:engine{engine}/sensor{sensor}/trend", facts


def build_rows() -> list[dict]:
    rows, n = [], 0

    def add(route, question, sources, facts, answerable, difficulty, notes, engine=None):
        nonlocal n
        n += 1
        rows.append({
            "id": f"g{n:03d}", "question": question, "route": route,
            "expected_engine": engine, "expected_sources": sources,
            "answer_key_facts": facts, "answerable": answerable,
            "difficulty": difficulty, "status": "unreviewed", "notes": notes,
        })

    for q, srcs, facts, diff, notes in DOC:
        add("doc", q, srcs, facts, True, diff, notes)

    for q, eng, sen, intent, diff, notes in TIMESERIES_SPECS:
        handle, facts = _ts_answer(eng, sen, intent)
        add("timeseries", q, [handle], facts, True, diff, notes, engine=eng)

    for q, eng, sen, docs, extra, diff, notes in FUSION:
        handle, ts_facts = _ts_answer(eng, sen, "status")
        add("fusion", q, docs + [handle], ts_facts + extra, True, diff, notes, engine=eng)

    for q, why in OUT_OF_SCOPE:
        add("out_of_scope", q, [], ["should abstain: " + why], False, "easy", "")

    return rows


def main():
    rows = build_rows()
    config.EVAL_DIR.mkdir(parents=True, exist_ok=True)
    with config.GOLDEN_EVAL.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    by_route = {}
    for r in rows:
        by_route[r["route"]] = by_route.get(r["route"], 0) + 1
    print(f"Wrote {len(rows)} candidates to {config.GOLDEN_EVAL}")
    print("By route:", by_route)


if __name__ == "__main__":
    main()
