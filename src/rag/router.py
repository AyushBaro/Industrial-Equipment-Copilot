"""Query router: classify a question and extract a structured execution plan.

One cheap structured-output call (gpt-4o-mini). The model sees the full sensor table so
it can map "sensor 11" / "Ps30" / "HPC static discharge pressure" → sensor_id=11. Code
then validates the plan and downgrades unresolvable data queries to abstention.
"""
from __future__ import annotations

import json

from src.data.sensor_meta import SENSORS
from src.llm_client import MODEL_ROUTING
from src.llm_client import client as llm
from src.rag.timeseries import N_ENGINES, engine_exists, sensor_exists

VALID_ROUTES = {"doc", "timeseries", "fusion", "out_of_scope"}
VALID_INTENTS = {"trend", "status", "overview", None}

_SENSOR_TABLE = "\n".join(
    f"  {s.sensor_id}: {s.symbol} — {s.description} ({s.subsystem})" for s in SENSORS
)

SYSTEM_PROMPT = f"""You route maintenance questions for a turbofan engine fleet \
(engines 1–{N_ENGINES}). Classify the question and extract a structured plan.

Routes:
- "doc": answerable from manuals / fault codes / work orders alone. This includes not \
only procedures, intervals, what a fault code means, and what was done on a work order, \
but also CONCEPTUAL questions about this fleet's sensors, subsystems, faults, or \
monitoring practice — e.g. "why is <sensor> not used for trend monitoring?", "what does \
a rising <sensor> with no <other> alarm indicate?", "what is the alarm threshold for \
<sensor>?". A question naming no specific engine is usually a doc question, NOT \
out-of-scope.
- "timeseries": needs live sensor data (a sensor's trend, whether a sensor/engine is in \
alarm, an engine's status). Route a request for ACTUAL sensor values/trend/status here \
even if it names no engine — it will be validated downstream and rejected if the engine \
is missing or a named sensor is invalid. Do not send a data request to "doc" just \
because it lacks an engine number.
- "fusion": needs BOTH — e.g. "engine X shows elevated <sensor>, is it a known fault \
and what does the manual say?"
- "out_of_scope": use this when the question is (a) about a DIFFERENT domain (other \
equipment, other aircraft, unrelated topics), or (b) impossible to answer from this \
fleet — it asks about a sensor id or quantity NOT in the list above (only sensors 1–21 \
exist; e.g. "sensor 45" is out of scope), or for something the data cannot provide (the \
data is indexed by operational cycle, not calendar date/time — e.g. "last week"). \
A conceptual "why / what does it mean" question about this fleet's real sensors or \
subsystems, with no engine number, is IN scope — route it to "doc", not out_of_scope.

Sensors (map names/symbols to ids):
{_SENSOR_TABLE}

Intents (for timeseries/fusion):
- "status": whether a reading is in alarm / normal / a problem right now — compares the \
latest value against its threshold. PREFER this whenever the question asks if something \
is "elevated", "a problem", "a known fault", "abnormal", "in alarm", or "end-of-life".
- "trend": ONLY when the user explicitly asks for history / direction / change over time \
("trend", "over the last N cycles", "rising or falling").
- "overview": whole-engine summary — also answers how many operational cycles an engine \
has run (its age/life), so "how many cycles does engine X have?" is a timeseries \
"overview" question, NOT out-of-scope.
For an alarm/fault-style question (including most fusion questions), choose "status", \
not "trend".

Return ONLY JSON:
{{"route": "...", "engine": int|null, "sensors": [int], "intent": "trend"|"status"|"overview"|null, "last_n": int|null, "rationale": "..."}}

Rules: extract engine number when present; map every sensor mentioned to its id; if a \
data question names no engine, still set route but leave engine null (it will be \
rejected). Use last_n only if the user implies a window (default null)."""


def route(question: str) -> dict:
    raw = llm.chat(
        [{"role": "system", "content": SYSTEM_PROMPT},
         {"role": "user", "content": question}],
        model=MODEL_ROUTING, temperature=0.0, json_mode=True,
    )
    try:
        plan = json.loads(raw)
    except json.JSONDecodeError:
        plan = {"route": "out_of_scope", "rationale": "unparseable router output"}
    return validate_plan(plan)


def validate_plan(plan: dict) -> dict:
    """Normalize and enforce safety: bad/missing engine or sensors → abstain."""
    route_ = plan.get("route")
    if route_ not in VALID_ROUTES:
        route_ = "out_of_scope"

    engine = plan.get("engine")
    engine = int(engine) if isinstance(engine, (int, float)) and engine_exists(int(engine)) else None

    raw_sensors = [s for s in (plan.get("sensors") or [])
                   if isinstance(s, (int, float))] if isinstance(plan.get("sensors"), list) else []
    sensors = [int(s) for s in raw_sensors if sensor_exists(int(s))]

    intent = plan.get("intent") if plan.get("intent") in VALID_INTENTS else None
    last_n = plan.get("last_n") if isinstance(plan.get("last_n"), int) else None

    abstain_reason = None
    if route_ in ("timeseries", "fusion"):
        # data queries we cannot run safely → abstain
        if engine is None:
            abstain_reason = "no valid engine identified for a data query"
            route_ = "out_of_scope"
        elif raw_sensors and not sensors:
            # the user named a specific sensor, but it is outside the valid range (1–21)
            abstain_reason = "named sensor(s) are not in the valid range 1–21"
            route_ = "out_of_scope"

    return {
        "route": route_, "engine": engine, "sensors": sensors,
        "intent": intent, "last_n": last_n,
        "rationale": plan.get("rationale", ""), "abstain_reason": abstain_reason,
    }


if __name__ == "__main__":
    for q in [
        "What was sensor 4's trend for engine 23 over its last 50 cycles?",
        "Engine 47 shows elevated Ps30 — is this a known fault and what should we do?",
        "What is the recommended inspection interval for the HPC?",
        "Show me the trend for engine 999",
        "What's the stock price of Boeing?",
    ]:
        print(q, "->", route(q))
