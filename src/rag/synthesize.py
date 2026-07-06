"""Grounded answer synthesis with forced, verified citations — docs and/or telemetry.

The model answers ONLY from the provided sources and cites each claim: a document by
its doc_id, a telemetry result by its short token (TS1, TS2, ...). We then verify in
code that every citation was actually provided, and translate telemetry tokens back to
their query handles for the final answer. If there are no sources, we abstain without
calling the model.
"""
from __future__ import annotations

import json

from src import config
from src.llm_client import MODEL_SYNTHESIS
from src.llm_client import client as llm
from src.rag.retrieve import Retrieved

ABSTENTION_MESSAGE = "I don't have enough information to answer that."

SYSTEM_PROMPT = """You are an industrial-equipment maintenance assistant. You answer \
ONLY from the provided sources. This is a low-tolerance domain: never use outside \
knowledge, never guess.

Sources come in two kinds:
- DOCUMENTS, each tagged with a doc_id (manuals, fault codes, work orders).
- TELEMETRY, each tagged TS1, TS2, ... (live sensor-data query results).

Rules:
- Use only facts present in the sources. If they are insufficient, set "sufficient" \
to false and put the exact string "I don't have enough information to answer that." \
in "answer".
- Cite every claim: documents by their doc_id, telemetry by its TS tag. Cite only \
tags/ids that appear in the sources.
- Be concise and specific; include exact sensor values and thresholds from the sources.

Return ONLY JSON:
{"answer": str, "citations": [doc_id or TS tag, ...], "confidence": "high"|"medium"|"low", "sufficient": bool}"""


def should_abstain(retrieved: list[Retrieved]) -> bool:
    """Doc-only relevance floor (used by the doc path)."""
    if not retrieved:
        return True
    return max(r.score for r in retrieved) <= config.ABSTAIN_MIN_RRF


def verify_citations(citations, allowed) -> list[str]:
    """Keep only citations that were actually provided (order-preserving, de-duped)."""
    allowed = set(allowed)
    seen, out = set(), []
    for c in citations or []:
        if c in allowed and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _format_docs(retrieved):
    blocks = []
    for r in retrieved or []:
        blocks.append(f"[doc_id={r.chunk.doc_id} | section: {r.chunk.section}]\n{r.chunk.text}")
    return blocks


def _format_telemetry(telemetry):
    """Return (blocks, token->handle map). telemetry items are tool-result dicts."""
    blocks, token_map = [], {}
    for i, t in enumerate(telemetry or [], 1):
        tag = f"TS{i}"
        token_map[tag] = t.get("query_handle", tag)
        detail = t.get("result_summary", "")
        # include a compact alarm/status detail when present
        if t.get("alarms"):
            detail += " In-alarm: " + ", ".join(
                f"{a['symbol']}={a['value']}(thr {a['alarm_threshold']})" for a in t["alarms"])
        blocks.append(f"[{tag} | {token_map[tag]}]\n{detail}")
    return blocks, token_map


def synthesize(question, retrieved=None, telemetry=None, model: str = MODEL_SYNTHESIS) -> dict:
    has_docs = bool(retrieved)
    has_tel = any(t.get("ok") for t in (telemetry or []))

    # Abstain when there is nothing usable to ground an answer in.
    doc_floor_ok = has_docs and not should_abstain(retrieved)
    if not doc_floor_ok and not has_tel:
        return {"answer": ABSTENTION_MESSAGE, "citations": [], "confidence": "low",
                "abstained": True, "contexts": [], "sources_text": []}

    doc_blocks = _format_docs(retrieved if doc_floor_ok else [])
    tel_items = [t for t in (telemetry or []) if t.get("ok")]
    tel_blocks, token_map = _format_telemetry(tel_items)

    allowed_docs = {r.chunk.doc_id for r in (retrieved if doc_floor_ok else [])}
    allowed = allowed_docs | set(token_map)

    parts = []
    if doc_blocks:
        parts.append("DOCUMENTS:\n" + "\n\n".join(doc_blocks))
    if tel_blocks:
        parts.append("TELEMETRY:\n" + "\n\n".join(tel_blocks))
    user = f"Question: {question}\n\n" + "\n\n".join(parts)

    raw = llm.chat(
        [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}],
        model=model, temperature=0.0, json_mode=True,
    )
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {"answer": raw, "citations": [], "confidence": "low", "sufficient": False}

    cited = verify_citations(data.get("citations", []), allowed)
    sufficient = bool(data.get("sufficient", True))
    answer = (data.get("answer") or "").strip()

    abstained = (not sufficient) or (not cited)
    if abstained:
        answer, cited = ABSTENTION_MESSAGE, []

    # translate TS tokens back to query handles for the final, human-meaningful citations
    final_citations = [token_map.get(c, c) for c in cited]

    contexts = [{"doc_id": r.chunk.doc_id, "section": r.chunk.section, "score": round(r.score, 5)}
                for r in (retrieved if doc_floor_ok else [])]
    contexts += [{"telemetry": t["query_handle"]} for t in tel_items]

    return {"answer": answer, "citations": final_citations,
            "confidence": data.get("confidence", "low"),
            "abstained": abstained, "contexts": contexts,
            # the exact grounding material shown to the model — used by the eval judge
            # to verify faithfulness against real sources, not against the answer key.
            "sources_text": doc_blocks + tel_blocks}
