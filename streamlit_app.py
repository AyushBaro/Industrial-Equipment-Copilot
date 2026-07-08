"""Public cached demo for the Industrial Equipment Copilot (Streamlit Community Cloud).

Self-contained on purpose: it reads pre-computed answers from Data/demo/demo_qa.json and
imports nothing from the app, so it needs no OpenAI key, no database, and no vector index
to run. The answers are genuine pipeline output, frozen — regenerate with `make demo-data`.

Local live version (real "ask anything", needs your own key): `make serve` + `make ui`.
"""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

DEMO_FILE = Path(__file__).parent / "Data" / "demo" / "demo_qa.json"
REPO_URL = "https://github.com/AyushBaro/Industrial-Equipment-Copilot"

ROUTE_LABEL = {
    "doc": "📄 Document lookup",
    "timeseries": "📈 Telemetry",
    "fusion": "🔗 Fusion (docs + sensors)",
    "out_of_scope": "🚫 Out of scope",
}
CONFIDENCE_ICON = {"high": "🟢", "medium": "🟡", "low": "🔴"}


@st.cache_data
def load_demo() -> list[dict]:
    return json.loads(DEMO_FILE.read_text())


def render_contexts(contexts: list[dict]) -> None:
    docs = [c for c in contexts if "doc_id" in c]
    tel = [c for c in contexts if "telemetry" in c]
    if docs:
        st.markdown("**Retrieved document chunks**")
        for c in docs:
            score = c.get("score")
            suffix = f" · score `{score}`" if score is not None else ""
            st.markdown(f"- `{c['doc_id']}` — *{c.get('section', '')}*{suffix}")
    if tel:
        st.markdown("**Telemetry queries**")
        for c in tel:
            st.markdown(f"- `{c['telemetry']}`")
    if not docs and not tel:
        st.caption("No sources were used — the copilot abstained.")


def render_answer(item: dict) -> None:
    route = item.get("route", "out_of_scope")
    abstained = item.get("abstained", False)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Route", ROUTE_LABEL.get(route, route).split(" ", 1)[-1])
    conf = item.get("confidence", "low")
    c2.metric("Confidence", f"{CONFIDENCE_ICON.get(conf, '')} {conf}")
    c3.metric("Latency", f"{item.get('latency_ms', 0)} ms")
    c4.metric("Cost", f"${item.get('cost_usd', 0.0):.5f}",
              help=f"{item.get('total_tokens', 0)} tokens · {item.get('n_calls', 0)} OpenAI calls")
    if item.get("route_blurb"):
        st.caption(item["route_blurb"])

    st.divider()
    if abstained:
        st.warning(f"**Abstained** — {item.get('answer', '')}")
        st.caption("By design: an ungrounded answer is a worse failure than no answer.")
    else:
        st.markdown("### Answer")
        st.markdown(item.get("answer", ""))
        cites = item.get("citations", [])
        if cites:
            st.markdown("### Sources")
            st.markdown("  ".join(f"`{c}`" for c in cites))

    with st.expander("Provenance — what the answer is grounded in", expanded=not abstained):
        render_contexts(item.get("contexts", []))


def main() -> None:
    st.set_page_config(page_title="Industrial Equipment Copilot — Demo",
                       page_icon="🛠️", layout="centered")

    st.title("🛠️ Industrial Equipment Copilot")
    st.caption(
        "Answers equipment maintenance questions by fusing three data sources — sensor "
        "telemetry, an asset hierarchy, and maintenance docs — into one **cited** answer, "
        "and **abstains** when the evidence is thin instead of guessing."
    )
    st.info(
        "🧊 **Cached demo.** These are real, frozen outputs of the pipeline, so the demo "
        "needs no API key and can't run up a bill. Pick a question below. "
        f"For a live *ask-anything* version, run it locally — see the [repo]({REPO_URL}).",
        icon=None,
    )

    demo = load_demo()
    by_route: dict[str, list[dict]] = {}
    for it in demo:
        by_route.setdefault(it["route"], []).append(it)

    # Group the picker by route so the four behaviors are obvious.
    labels, index = [], {}
    for route in ["doc", "timeseries", "fusion", "out_of_scope"]:
        for it in by_route.get(route, []):
            label = f"{ROUTE_LABEL.get(route, route).split(' ', 1)[0]}  {it['question']}"
            labels.append(label)
            index[label] = it

    with st.sidebar:
        st.header("Sample questions")
        st.caption("12 curated questions across the four behaviors the router recognizes.")
        st.markdown(
            "- 📄 **Document** lookup\n- 📈 **Telemetry** query\n"
            "- 🔗 **Fusion** (docs + sensors)\n- 🚫 **Out of scope** → abstains"
        )
        st.divider()
        st.markdown(f"[Source & full write-up →]({REPO_URL})")

    choice = st.selectbox("Choose a question", labels, index=0)
    st.divider()
    render_answer(index[choice])


if __name__ == "__main__":
    main()
