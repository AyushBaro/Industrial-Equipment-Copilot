"""End-to-end document RAG pipeline (Phase 2: documents only).

    from src.rag.pipeline import answer
    answer("What is the recommended inspection interval for the HPC?")

CLI:
    python -m src.rag.pipeline "your question"
"""
from __future__ import annotations

import sys

from src import config
from src.rag.retrieve import get_retriever
from src.rag.synthesize import synthesize


def answer(question: str, k: int = config.RETRIEVAL_K, model: str | None = None) -> dict:
    retrieved = get_retriever().hybrid(question, k=k)
    kwargs = {"model": model} if model else {}
    result = synthesize(question, retrieved, **kwargs)
    result["question"] = question
    return result


def _print(result: dict) -> None:
    print(f"\nQ: {result['question']}\n")
    print(result["answer"])
    if result["citations"]:
        print("\nSources: " + ", ".join(result["citations"]))
    if result.get("abstained"):
        print("\n[abstained]")
    print("\nRetrieved context:")
    for c in result["contexts"]:
        print(f"  - {c['doc_id']} ({c['section']})  score={c['score']}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python -m src.rag.pipeline "your question"')
        raise SystemExit(1)
    _print(answer(" ".join(sys.argv[1:])))
