"""Public cached demo for the Industrial Equipment Copilot (Streamlit Community Cloud).

Self-contained on purpose: it reads pre-computed answers from Data/demo/*.json and imports
nothing from the app, so it needs no OpenAI key, no database, and no vector index to run.
The answers are genuine pipeline output, frozen — regenerate with `make demo-data`.

Local live version (real "ask anything", needs your own key): `make serve` + `make ui`.
"""
from __future__ import annotations

import html
import json
import random
from pathlib import Path

import streamlit as st

DEMO_DIR = Path(__file__).parent / "Data" / "demo"
REPO_URL = "https://github.com/AyushBaro/Industrial-Equipment-Copilot"

ROUTE_META = {
    "doc":          {"icon": "📄", "label": "Document lookup",         "color": "#3b82f6"},
    "timeseries":   {"icon": "📈", "label": "Telemetry",               "color": "#10b981"},
    "fusion":       {"icon": "🔗", "label": "Fusion · docs + sensors", "color": "#8b5cf6"},
    "out_of_scope": {"icon": "🚫", "label": "Out of scope",            "color": "#64748b"},
}
ROUTES = ["doc", "timeseries", "fusion", "out_of_scope"]
CONF_COLOR = {"high": "#10b981", "medium": "#f59e0b", "low": "#ef4444"}

KPIS = [
    ("Retrieval recall@5", "96.7%", "↑ from 80%"),
    ("Routing accuracy",   "100%",  ""),
    ("Faithfulness",       "100%",  "no ungrounded claims"),
    ("Over-abstention",    "6.7%",  "↓ from 25%"),
]
SOURCES = [
    ("📊", "Sensor telemetry", "100 engines · 21 sensors", "NASA CMAPSS (real data)"),
    ("🗂️", "Asset hierarchy",  "21 sensors → subsystems",  "nominal + alarm thresholds"),
    ("📚", "Maintenance docs", "19 docs → 73 chunks",      "manuals · faults · work orders"),
]

CSS = """
<style>
.block-container {padding-top: 2rem; max-width: 1100px;}
.hero {background: linear-gradient(120deg,#0f2027 0%,#203a43 55%,#2c5364 100%);
       border-radius:16px; padding:22px 28px; color:#fff; margin-bottom:18px;
       box-shadow:0 8px 30px rgba(0,0,0,.18);}
.hero h1 {font-size:1.8rem; margin:0 0 6px; font-weight:750; letter-spacing:-.01em;}
.hero p {margin:0; opacity:.92; font-size:.96rem; line-height:1.5; max-width:800px;}
.flow {margin-top:12px; font-size:.8rem; opacity:.82; font-family:ui-monospace,Menlo,monospace;}
.flow b {color:#7dd3fc; font-weight:600;}
.badge {display:inline-block; padding:5px 15px; border-radius:999px; color:#fff;
        font-weight:650; font-size:.92rem; box-shadow:0 2px 8px rgba(0,0,0,.15);}
.chips {margin:11px 0 4px;}
.chip {display:inline-block; padding:4px 11px; margin:0 7px 7px 0; border-radius:8px;
       border:1px solid rgba(128,128,128,.25); font-size:.8rem;}
.chip .k {opacity:.6;} .chip .v {font-weight:650;}
.dot {display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:6px; vertical-align:middle;}
.bar-row {display:flex; align-items:center; gap:10px; margin:4px 0; font-size:.8rem;}
.bar-lab {flex:0 0 175px; font-family:ui-monospace,Menlo,monospace; opacity:.85;
          overflow:hidden; text-overflow:ellipsis; white-space:nowrap;}
.bar-track {flex:1; background:rgba(128,128,128,.15); border-radius:6px; height:14px;}
.bar-fill {height:14px; border-radius:6px; background:linear-gradient(90deg,#6366f1,#8b5cf6);}
.ground {border-left:3px solid rgba(128,128,128,.35); padding:6px 12px; margin:8px 0;
         font-size:.8rem; opacity:.9; white-space:pre-wrap; font-family:ui-monospace,Menlo,monospace;}
.side-kpi {border:1px solid rgba(128,128,128,.2); border-radius:10px; padding:8px 11px; margin-bottom:8px;}
.side-kpi .v {font-size:1.25rem; font-weight:750; line-height:1;}
.side-kpi .k {font-size:.66rem; text-transform:uppercase; letter-spacing:.04em; opacity:.65;}
.side-kpi .d {font-size:.68rem; color:#10b981; font-weight:600;}
.ba {border-radius:12px; padding:14px 16px; height:100%;}
.ba.bad {border:1px solid rgba(239,68,68,.5); background:rgba(239,68,68,.06);}
.ba.good {border:1px solid rgba(16,185,129,.5); background:rgba(16,185,129,.06);}
.ba h4 {margin:0 0 6px; font-size:.92rem;}
.foot {font-size:.8rem; opacity:.7; text-align:center; margin-top:6px;}
</style>
"""


def load(name: str):
    return _load(name, (DEMO_DIR / name).stat().st_mtime)


@st.cache_data
def _load(name: str, _mtime: float):
    return json.loads((DEMO_DIR / name).read_text())


def badge(route: str) -> str:
    m = ROUTE_META.get(route, {"icon": "", "label": route, "color": "#64748b"})
    return f'<span class="badge" style="background:{m["color"]}">{m["icon"]} {m["label"]}</span>'


def chips(item: dict) -> str:
    conf = item.get("confidence", "low")
    dot = f'<span class="dot" style="background:{CONF_COLOR.get(conf,"#999")}"></span>'
    parts = [
        f'<span class="chip">{dot}<span class="v">{conf}</span> <span class="k">confidence</span></span>',
        f'<span class="chip"><span class="k">latency</span> <span class="v">{item.get("latency_ms",0)} ms</span></span>',
        f'<span class="chip"><span class="k">cost</span> <span class="v">${item.get("cost_usd",0.0):.5f}</span></span>',
        f'<span class="chip"><span class="k">tokens</span> <span class="v">{item.get("total_tokens",0)}</span></span>',
    ]
    return '<div class="chips">' + "".join(parts) + "</div>"


def ranking_bars(contexts: list[dict]) -> None:
    docs = [c for c in contexts if "doc_id" in c and c.get("score") is not None]
    if not docs:
        return
    top = max(c["score"] for c in docs) or 1
    st.markdown("**Retrieval ranking** — hybrid dense + BM25, fused with RRF")
    rows = []
    for c in docs:
        pct = max(6, round(c["score"] / top * 100))
        rows.append(
            f'<div class="bar-row"><div class="bar-lab">{html.escape(c["doc_id"])}</div>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{pct}%"></div></div>'
            f'<div style="flex:0 0 58px;text-align:right;opacity:.7">{c["score"]:.4f}</div></div>'
        )
    st.markdown("".join(rows), unsafe_allow_html=True)


def router_panel(item: dict) -> None:
    p = item.get("plan", {}) or {}
    eng = p.get("engine")
    sensors = p.get("sensors") or []
    st.markdown(
        f"- **Route:** `{p.get('route', item.get('route'))}`\n"
        f"- **Engine:** `{eng if eng is not None else '—'}`\n"
        f"- **Sensor(s):** `{', '.join(map(str, sensors)) if sensors else '—'}`\n"
        f"- **Intent:** `{p.get('intent') or '—'}`"
    )
    if p.get("rationale"):
        st.caption(f"Rationale: {p['rationale']}")


def provenance(item: dict) -> None:
    contexts = item.get("contexts", [])
    docs = [c for c in contexts if "doc_id" in c]
    tel = [c for c in contexts if "telemetry" in c]
    if docs:
        st.markdown("**Retrieved document chunks**")
        for c in docs:
            sc = c.get("score")
            st.markdown(f"- `{c['doc_id']}` — *{c.get('section','')}*" + (f" · score `{sc}`" if sc is not None else ""))
    if tel:
        st.markdown("**Telemetry query**")
        for c in tel:
            st.markdown(f"- `{c['telemetry']}`")
    if not contexts:
        st.caption("No sources were used — the copilot abstained.")
    grounding = item.get("sources_text", [])
    if grounding:
        st.markdown("**Exact source text the model read** — every claim is checked against this")
        for block in grounding:
            st.markdown(f'<div class="ground">{html.escape(block)}</div>', unsafe_allow_html=True)


def render_answer(item: dict) -> None:
    with st.container(border=True):
        st.markdown(badge(item.get("route", "out_of_scope")), unsafe_allow_html=True)
        st.markdown(chips(item), unsafe_allow_html=True)
        st.markdown(f"**Q — {item['question']}**")
        if item.get("route_blurb"):
            st.caption(item["route_blurb"])
        st.divider()

        if item.get("abstained"):
            st.warning(f"**Abstained** — {item.get('answer','')}")
            st.caption("By design: an ungrounded answer is a worse failure than no answer.")
        else:
            st.markdown(item.get("answer", ""))
            if item.get("citations"):
                st.markdown("**Sources:** " + "  ".join(f"`{c}`" for c in item["citations"]))
            st.write("")
            ranking_bars(item.get("contexts", []))

        with st.expander("🧭 Router decision — what the classifier extracted"):
            router_panel(item)
        with st.expander("🔎 Provenance & grounding — what the answer rests on"):
            provenance(item)


def render_before_after() -> None:
    try:
        sc = load("showcase.json")
    except FileNotFoundError:
        return
    st.divider()
    with st.expander("⭐ Watch the system improve — a real failure that the eval caught and fixed"):
        st.markdown(f"**The flagship fusion question:** *{sc['question']}*")
        b, a = st.columns(2, gap="medium")
        with b:
            st.markdown('<div class="ba bad"><h4>❌ Before (baseline)</h4></div>', unsafe_allow_html=True)
            st.markdown(sc["before"]["answer"])
            st.markdown("**Cited:** " + ("  ".join(f"`{c}`" for c in sc["before"]["citations"]) or "—"))
        with a:
            st.markdown('<div class="ba good"><h4>✅ After (fixed)</h4></div>', unsafe_allow_html=True)
            st.markdown(sc["after"]["answer"])
            st.markdown("**Cited:** " + ("  ".join(f"`{c}`" for c in sc["after"]["citations"]) or "—"))
        st.info(sc["fix_note"], icon="🛠️")


def sidebar() -> None:
    with st.sidebar:
        st.markdown("### 📊 Results")
        st.caption("50-question hand-labeled eval set (3-run mean)")
        for k, v, d in KPIS:
            st.markdown(f'<div class="side-kpi"><div class="k">{k}</div>'
                        f'<div class="v">{v}</div><div class="d">{d}</div></div>',
                        unsafe_allow_html=True)
        st.markdown("### 🧩 Data fused")
        for i, t, m, s in SOURCES:
            st.markdown(f"**{i} {t}** — {m}  \n<span style='opacity:.6;font-size:.8rem'>{s}</span>",
                        unsafe_allow_html=True)
        st.divider()
        st.caption("🧊 Cached demo — real, frozen pipeline outputs. No API key, no bill.")
        st.markdown(f"[Source & full write-up →]({REPO_URL})")


def main() -> None:
    st.set_page_config(page_title="Industrial Equipment Copilot — Demo",
                       page_icon="🛠️", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    sidebar()

    st.markdown(
        '<div class="hero"><h1>🛠️ Industrial Equipment Copilot</h1>'
        '<p>Answers equipment maintenance questions by fusing three data sources — sensor '
        'telemetry, an asset hierarchy, and maintenance docs — into one <b>cited</b> answer, '
        'and <b>abstains</b> when the evidence is thin instead of guessing.</p>'
        '<div class="flow">flow &nbsp;→&nbsp; <b>route</b> &nbsp;→&nbsp; <b>retrieve</b> '
        '(hybrid search) / <b>query sensors</b> &nbsp;→&nbsp; <b>grounded synthesis</b> '
        '&nbsp;→&nbsp; cited answer <i>or</i> abstain</div></div>',
        unsafe_allow_html=True,
    )

    demo = load("demo_qa.json")
    ids = [it["id"] for it in demo]
    by_id = {it["id"]: it for it in demo}
    by_route: dict[str, list[dict]] = {}
    for it in demo:
        by_route.setdefault(it["route"], []).append(it)

    if "qid" not in st.session_state:
        st.session_state.qid = ids[0]

    head, shuf = st.columns([4, 1])
    with head:
        st.markdown("#### Pick a question — grouped by what the router does with it")
    with shuf:
        if st.button("🎲 Shuffle", use_container_width=True):
            st.session_state.qid = random.choice(ids)

    tabs = st.tabs([f'{ROUTE_META[r]["icon"]} {ROUTE_META[r]["label"].split(" ")[0]}'
                    f' ({len(by_route.get(r, []))})' for r in ROUTES])
    for tab, route in zip(tabs, ROUTES):
        with tab:
            for it in by_route.get(route, []):
                kind = "primary" if it["id"] == st.session_state.qid else "secondary"
                if st.button(it["question"], key=f"b_{it['id']}", use_container_width=True, type=kind):
                    st.session_state.qid = it["id"]

    st.write("")
    render_answer(by_id[st.session_state.qid])

    # aggregate footer
    avg_lat = round(sum(i["latency_ms"] for i in demo) / len(demo))
    avg_cost = sum(i["cost_usd"] for i in demo) / len(demo)
    n_abs = sum(1 for i in demo if i["abstained"])
    st.markdown(
        f'<div class="foot">Across all {len(demo)} demo questions · avg {avg_lat} ms · '
        f'avg ${avg_cost:.4f}/query · {n_abs} correct abstentions · '
        f'gpt-4o synthesis · gpt-4o-mini routing · text-embedding-3-small</div>',
        unsafe_allow_html=True,
    )

    render_before_after()


if __name__ == "__main__":
    main()
