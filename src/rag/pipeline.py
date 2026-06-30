"""End-to-end RAG pipeline (Phase 3: route → dispatch → synthesize).

    from src.rag.pipeline import answer
    answer("Engine 47 shows elevated Ps30 — is this a known fault and what do we do?")

CLI:
    python -m src.rag.pipeline "your question"
"""
from __future__ import annotations

import sys

from src import config
from src.rag.retrieve import get_retriever
from src.rag.router import route as route_question
from src.rag.synthesize import ABSTENTION_MESSAGE, synthesize
from src.rag.timeseries import engine_overview, sensor_status, sensor_trend

DEFAULT_LAST_N = 50


def run_timeseries(plan: dict) -> list[dict]:
    """Execute the bounded tools implied by a validated plan. Engine is guaranteed valid."""
    engine = plan["engine"]
    sensors = plan.get("sensors") or []
    intent = plan.get("intent")
    last_n = plan.get("last_n") or DEFAULT_LAST_N
    results: list[dict] = []

    if intent == "overview" or (not sensors and intent != "status"):
        results.append(engine_overview(engine))
    elif intent == "status":
        if sensors:
            results.extend(sensor_status(engine, s) for s in sensors)
        else:
            results.append(sensor_status(engine))
    else:  # trend (default when sensors are named)
        results.extend(sensor_trend(engine, s, last_n) for s in sensors)
    return results


def answer(question: str, k: int = config.RETRIEVAL_K, model: str | None = None) -> dict:
    plan = route_question(question)
    route = plan["route"]
    syn_kwargs = {"model": model} if model else {}

    if route == "out_of_scope":
        return {"question": question, "route": route, "answer": ABSTENTION_MESSAGE,
                "citations": [], "confidence": "low", "abstained": True,
                "contexts": [], "plan": plan}

    retrieved = telemetry = None
    if route in ("doc", "fusion"):
        retrieved = get_retriever().hybrid(question, k=k)
    if route in ("timeseries", "fusion"):
        telemetry = run_timeseries(plan)

    result = synthesize(question, retrieved=retrieved, telemetry=telemetry, **syn_kwargs)
    result["question"] = question
    result["route"] = route
    result["plan"] = plan
    return result


def _print(result: dict) -> None:
    print(f"\nQ: {result['question']}\n[route: {result['route']}]\n")
    print(result["answer"])
    if result["citations"]:
        print("\nSources: " + ", ".join(result["citations"]))
    if result.get("abstained"):
        print("\n[abstained]")
    if result.get("contexts"):
        print("\nContext used:")
        for c in result["contexts"]:
            print(f"  - {c}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python -m src.rag.pipeline "your question"')
        raise SystemExit(1)
    _print(answer(" ".join(sys.argv[1:])))
