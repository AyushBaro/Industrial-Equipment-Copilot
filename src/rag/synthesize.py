"""Grounded answer synthesis with forced, verified citations.

The model is instructed to answer ONLY from the retrieved context and to cite the
source doc id for its claims. We then verify in code that every citation was actually
retrieved — the model cannot cite something it was not shown. If retrieval found
nothing relevant, we abstain *without* calling the model.
"""
from __future__ import annotations

import json

from src import config
from src.llm_client import MODEL_SYNTHESIS
from src.llm_client import client as llm
from src.rag.retrieve import Retrieved

ABSTENTION_MESSAGE = "I don't have enough information to answer that."

SYSTEM_PROMPT = """You are an industrial-equipment maintenance assistant. You answer \
ONLY from the provided numbered sources. This is a low-tolerance domain: never use \
outside knowledge, never guess.

Rules:
- Use only facts present in the sources. If they are insufficient, set "sufficient" \
to false and put the exact string "I don't have enough information to answer that." \
in "answer".
- Cite the source doc_id(s) you used in "citations". Cite only doc_ids that appear in \
the provided sources.
- Be concise and specific; include exact numbers/thresholds when the sources give them.

Return ONLY a JSON object:
{"answer": str, "citations": [doc_id, ...], "confidence": "high"|"medium"|"low", \
"sufficient": bool}"""


def should_abstain(retrieved: list[Retrieved]) -> bool:
    """Abstain when nothing cleared the relevance floor."""
    if not retrieved:
        return True
    return max(r.score for r in retrieved) <= config.ABSTAIN_MIN_RRF


def verify_citations(citations, allowed_doc_ids) -> list[str]:
    """Keep only citations that were actually in the retrieved set (order-preserving)."""
    allowed = set(allowed_doc_ids)
    seen, out = set(), []
    for c in citations or []:
        if c in allowed and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _format_context(retrieved: list[Retrieved]) -> str:
    blocks = []
    for i, r in enumerate(retrieved, 1):
        blocks.append(
            f"[{i}] doc_id={r.chunk.doc_id} (section: {r.chunk.section})\n{r.chunk.text}"
        )
    return "\n\n".join(blocks)


def synthesize(question: str, retrieved: list[Retrieved], model: str = MODEL_SYNTHESIS) -> dict:
    if should_abstain(retrieved):
        return {
            "answer": ABSTENTION_MESSAGE,
            "citations": [],
            "confidence": "low",
            "abstained": True,
            "contexts": [],
        }

    allowed = [r.chunk.doc_id for r in retrieved]
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Question: {question}\n\nSources:\n{_format_context(retrieved)}",
        },
    ]
    raw = llm.chat(messages, model=model, temperature=0.0, json_mode=True)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {"answer": raw, "citations": [], "confidence": "low", "sufficient": False}

    citations = verify_citations(data.get("citations", []), allowed)
    sufficient = bool(data.get("sufficient", True))
    answer = data.get("answer", "").strip()

    # Enforce abstention if the model declared insufficiency or gave no valid citation.
    abstained = (not sufficient) or (not citations)
    if abstained:
        answer = ABSTENTION_MESSAGE
        citations = []

    return {
        "answer": answer,
        "citations": citations,
        "confidence": data.get("confidence", "low"),
        "abstained": abstained,
        "contexts": [{"doc_id": r.chunk.doc_id, "section": r.chunk.section,
                      "score": round(r.score, 5)} for r in retrieved],
    }
