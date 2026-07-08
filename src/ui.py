"""Streamlit UI for the Industrial Equipment RAG Copilot (Phase 6).

A thin front-end over the FastAPI backend: it POSTs the question to `/ask` and renders
the grounded answer with its citations and the exact provenance (retrieved doc chunks +
telemetry queries) the answer rests on. All logic lives in the pipeline/API — this file
only presents. Abstentions are shown honestly, not hidden.

Run the API first, then the UI:

    make serve      # terminal 1 — FastAPI on :8100
    make ui         # terminal 2 — Streamlit on :8501
"""
from __future__ import annotations

import os

import requests
import streamlit as st

from src import config

# Where the FastAPI backend lives. Overridable so the UI can point at a remote deploy.
API_BASE = os.environ.get("COPILOT_API", f"http://{config.API_HOST}:{config.API_PORT}")
ASK_URL = f"{API_BASE}/ask"
HEALTH_URL = f"{API_BASE}/health"

ROUTE_LABELS = {
    "doc": ("📄 Document lookup", "Answered from the maintenance corpus."),
    "timeseries": ("📈 Telemetry", "Answered from live sensor data."),
    "fusion": ("🔗 Fusion", "Answered from both documents and sensor telemetry."),
    "out_of_scope": ("🚫 Out of scope", "Outside the copilot's knowledge — abstained."),
}
CONFIDENCE_ICON = {"high": "🟢", "medium": "🟡", "low": "🔴"}

EXAMPLES = [
    "What is the alarm threshold for sensor T50?",
    "Engine 47 shows elevated Ps30 — is this a known fault and what should we do?",
    "What is the status of engine 12's sensors right now?",
    "How often should the HPC be borescope-inspected?",
    "What's the capital of France?",  # out-of-scope → should abstain
]


def check_health() -> dict | None:
    try:
        r = requests.get(HEALTH_URL, timeout=5)
        r.raise_for_status()
        return r.json()
    except requests.RequestException:
        return None


def ask(question: str, k: int | None) -> dict:
    payload: dict = {"question": question}
    if k:
        payload["k"] = k
    r = requests.post(ASK_URL, json=payload, timeout=120)
    r.raise_for_status()
    return r.json()


def render_contexts(contexts: list[dict]) -> None:
    """Render the provenance actually used: retrieved doc chunks and telemetry handles."""
    docs = [c for c in contexts if "doc_id" in c]
    tel = [c for c in contexts if "telemetry" in c]

    if docs:
        st.markdown("**Retrieved document chunks**")
        for c in docs:
            score = c.get("score")
            score_str = f" · score `{score}`" if score is not None else ""
            st.markdown(f"- `{c['doc_id']}` — *{c.get('section', '')}*{score_str}")
    if tel:
        st.markdown("**Telemetry queries**")
        for c in tel:
            st.markdown(f"- `{c['telemetry']}`")
    if not docs and not tel:
        st.caption("No sources were used (the copilot abstained).")


def main() -> None:
    st.set_page_config(page_title="Industrial Equipment RAG Copilot",
                       page_icon="🛠️", layout="centered")

    st.title("🛠️ Industrial Equipment RAG Copilot")
    st.caption(
        "Maintenance & troubleshooting Q&A over **fused** heterogeneous data — sensor "
        "telemetry (NASA CMAPSS), an asset hierarchy, and maintenance docs. Every answer "
        "is **grounded and cited**; when evidence is thin, it **abstains** instead of guessing."
    )

    with st.sidebar:
        st.header("About")
        health = check_health()
        if health:
            st.success(f"API connected · v{health.get('version', '?')}")
            models = health.get("models", {})
            st.caption(f"routing: `{models.get('routing', '?')}`")
            st.caption(f"synthesis: `{models.get('synthesis', '?')}`")
        else:
            st.error("API not reachable.")
            st.markdown(f"Start it with `make serve`, then reload.\n\nExpected at `{API_BASE}`.")

        st.divider()
        k = st.slider("Retrieval depth (k)", min_value=1, max_value=20,
                      value=config.RETRIEVAL_K,
                      help="How many document chunks hybrid retrieval returns.")
        st.divider()
        st.markdown("**Try an example**")
        for ex in EXAMPLES:
            if st.button(ex, key=f"ex_{hash(ex)}", use_container_width=True):
                st.session_state["question"] = ex

    question = st.text_area(
        "Ask a maintenance question",
        key="question",
        placeholder="e.g. Engine 47 shows elevated Ps30 — is this a known fault?",
        height=90,
    )
    submit = st.button("Ask", type="primary", disabled=not check_health())

    if not submit:
        return
    if not question.strip():
        st.warning("Enter a question first.")
        return

    with st.spinner("Retrieving, routing, and grounding an answer…"):
        try:
            result = ask(question, k)
        except requests.RequestException as e:
            st.error(f"Request failed: {e}")
            return

    route = result.get("route", "out_of_scope")
    abstained = result.get("abstained", False)
    label, blurb = ROUTE_LABELS.get(route, (route, ""))

    # Headline row: route + confidence + latency + cost
    usage = result.get("usage", {})
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Route", label.split(" ", 1)[-1] if " " in label else label)
    conf = result.get("confidence", "low")
    c2.metric("Confidence", f"{CONFIDENCE_ICON.get(conf, '')} {conf}")
    c3.metric("Latency", f"{result.get('latency_ms', 0)} ms")
    cost = usage.get("cost_usd", 0.0)
    c4.metric("Cost", f"${cost:.5f}", help=f"{usage.get('total_tokens', 0)} tokens · "
                                           f"{usage.get('n_calls', 0)} OpenAI calls")
    st.caption(blurb)

    st.divider()

    if abstained:
        st.warning(f"**Abstained** — {result.get('answer', '')}")
        st.caption("This is by design: an ungrounded answer is a worse failure than no answer.")
    else:
        st.markdown("### Answer")
        st.markdown(result.get("answer", ""))

        citations = result.get("citations", [])
        if citations:
            st.markdown("### Sources")
            st.markdown("  ".join(f"`{c}`" for c in citations))

    with st.expander("Provenance — what the answer is grounded in", expanded=not abstained):
        render_contexts(result.get("contexts", []))
        by_model = usage.get("by_model", {})
        if by_model:
            st.divider()
            st.markdown("**OpenAI cost breakdown**")
            for model, m in by_model.items():
                st.caption(
                    f"`{model}` — {m['calls']} call(s) · "
                    f"{m['prompt_tokens']}+{m['completion_tokens']} tokens · "
                    f"${m['cost_usd']:.6f}"
                )


if __name__ == "__main__":
    main()
