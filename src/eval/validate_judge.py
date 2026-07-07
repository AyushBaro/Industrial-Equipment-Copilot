"""Phase 5 — validate the faithfulness LLM-judge against YOUR hand labels.

Failure mode #3 in the playbook is trusting the LLM-judge without checking it. This
helper closes that gap: it shows you the exact QUESTION, SOURCES, and ANSWER the judge
saw, you rule "faithful / not faithful" **blind** (the judge's verdict is hidden until
after you decide, so you're not anchored), and it reports how often you and the judge
agree.

It reports two numbers, because raw agreement lies when one class dominates (the judge
called 39/40 answers faithful):
  - raw agreement  = fraction of rows where you and the judge match
  - Cohen's kappa  = agreement corrected for what you'd get by chance; ≥0.85 is the bar

    make eval-judge                 # validate a 15-row sample (always includes the
                                    #   judge's flagged-unfaithful rows)
    make eval-judge ARGS=--all      # validate every answerable row (40)
    make eval-judge ARGS=--n 20     # custom sample size

Reads Data/eval/reports/{predictions,report}-baseline.json (run `make eval-score` first).
Autosaves your labels to Data/eval/reports/judge_validation.json — stop and resume.
"""
from __future__ import annotations

import argparse
import json
import threading
import webbrowser

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from src import config

REPORTS_DIR = config.EVAL_DIR / "reports"
LABELS_PATH = REPORTS_DIR / "judge_validation.json"

app = FastAPI(title="Judge Validation")
_STATE: dict = {"items": []}  # populated in main(), read by the API


# ------------------------------------------------------------------ data assembly


def build_items(tag: str = "baseline") -> list[dict]:
    """Join golden rows + cached predictions + judge verdicts into review items."""
    raw = json.loads((REPORTS_DIR / f"predictions-{tag}.json").read_text())
    run0 = raw[0] if raw and isinstance(raw[0], list) else raw  # tolerate list-of-runs
    preds = {p["id"]: p for p in run0}
    report = json.loads((REPORTS_DIR / f"report-{tag}.json").read_text())
    verdicts = {v["id"]: v for v in report["faithfulness_verdicts"]}
    golden = {json.loads(l)["id"]: json.loads(l)
              for l in config.GOLDEN_EVAL.read_text().splitlines() if l.strip()}

    items = []
    for rid, v in verdicts.items():
        p, g = preds.get(rid, {}), golden.get(rid, {})
        items.append({
            "id": rid,
            "route": g.get("route", "?"),
            "question": g.get("question", ""),
            "sources_text": p.get("sources_text", []),
            "answer": p.get("answer", ""),
            "answer_key_facts": g.get("answer_key_facts", []),
            "judge_faithful": bool(v["faithful"]),
            "judge_reason": v.get("reason", ""),
        })
    return items


def sample_items(items: list[dict], n: int) -> list[dict]:
    """Pick n items to review, always including every judge-flagged unfaithful row
    (that's where disagreement is most informative), then spread the rest across routes
    deterministically (no RNG, so a re-run shows the same sample)."""
    flagged = [it for it in items if not it["judge_faithful"]]
    rest = [it for it in items if it["judge_faithful"]]
    if len(flagged) >= n:
        return flagged[:n]
    # round-robin the faithful rows by route for a representative spread
    by_route: dict[str, list[dict]] = {}
    for it in rest:
        by_route.setdefault(it["route"], []).append(it)
    spread, routes = [], sorted(by_route)
    while any(by_route.values()):
        for rt in routes:
            if by_route[rt]:
                spread.append(by_route[rt].pop(0))
    chosen = flagged + spread[: n - len(flagged)]
    return sorted(chosen, key=lambda it: it["id"])


# ------------------------------------------------------------------------ labels


def load_labels() -> dict:
    return json.loads(LABELS_PATH.read_text()) if LABELS_PATH.exists() else {}


def save_labels(labels: dict) -> None:
    LABELS_PATH.write_text(json.dumps(labels, indent=1))


def cohen_kappa(pairs: list[tuple[bool, bool]]) -> float | None:
    """Cohen's kappa for two binary raters over (human, judge) label pairs."""
    n = len(pairs)
    if n == 0:
        return None
    po = sum(1 for h, j in pairs if h == j) / n
    # marginal probabilities per rater for the "faithful" class
    ph = sum(1 for h, _ in pairs if h) / n
    pj = sum(1 for _, j in pairs if j) / n
    pe = ph * pj + (1 - ph) * (1 - pj)  # chance agreement
    if pe == 1.0:
        return 1.0 if po == 1.0 else 0.0
    return (po - pe) / (1 - pe)


def summarize(labels: dict, items: list[dict]) -> dict:
    by_id = {it["id"]: it for it in items}
    pairs, disagreements = [], []
    for rid, lab in labels.items():
        it = by_id.get(rid)
        if not it:
            continue
        human = lab["label"] == "faithful"
        judge = it["judge_faithful"]
        pairs.append((human, judge))
        if human != judge:
            disagreements.append({
                "id": rid, "human": lab["label"],
                "judge": "faithful" if judge else "unfaithful",
                "judge_reason": it["judge_reason"], "notes": lab.get("notes", ""),
            })
    n = len(pairs)
    raw = sum(1 for h, j in pairs if h == j) / n if n else None
    kappa = cohen_kappa(pairs)
    return {
        "n_labeled": n, "n_total": len(items),
        "raw_agreement": None if raw is None else round(raw, 3),
        "cohen_kappa": None if kappa is None else round(kappa, 3),
        "trustworthy": bool(raw is not None and raw >= 0.85),
        "disagreements": disagreements,
    }


# --------------------------------------------------------------------------- API


class Label(BaseModel):
    label: str  # "faithful" | "unfaithful"
    notes: str | None = None


@app.get("/api/items")
def api_items():
    labels = load_labels()
    items = []
    for it in _STATE["items"]:
        items.append({**it, "user_label": labels.get(it["id"], {}).get("label"),
                      "user_notes": labels.get(it["id"], {}).get("notes", "")})
    return JSONResponse(items)


@app.post("/api/label/{rid}")
def api_label(rid: str, body: Label):
    labels = load_labels()
    labels[rid] = {"label": body.label, "notes": body.notes or ""}
    save_labels(labels)
    return JSONResponse({"ok": True})


@app.get("/api/summary")
def api_summary():
    return JSONResponse(summarize(load_labels(), _STATE["items"]))


@app.get("/", response_class=HTMLResponse)
def index():
    return PAGE


PAGE = """<!doctype html><html><head><meta charset=utf-8>
<title>Judge Validation</title><meta name=viewport content="width=device-width,initial-scale=1">
<style>
 :root{--bg:#0f172a;--card:#1e293b;--mut:#94a3b8;--line:#334155;--ok:#22c55e;--no:#ef4444;--acc:#38bdf8;--warn:#fbbf24}
 *{box-sizing:border-box} body{margin:0;font:15px/1.5 system-ui,sans-serif;background:var(--bg);color:#e2e8f0}
 header{position:sticky;top:0;background:#0b1220;border-bottom:1px solid var(--line);padding:12px 20px;display:flex;gap:16px;align-items:center;flex-wrap:wrap;z-index:5}
 .bar{flex:1;height:8px;background:var(--line);border-radius:99px;overflow:hidden;min-width:120px}
 .bar>i{display:block;height:100%;background:var(--ok);width:0}
 .chip{font-size:12px;color:var(--mut)} .chip b{color:#e2e8f0}
 main{max-width:860px;margin:24px auto;padding:0 16px}
 .card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:22px}
 .row1{display:flex;gap:8px;align-items:center;margin-bottom:10px;flex-wrap:wrap}
 .badge{font-size:11px;font-weight:700;letter-spacing:.04em;padding:3px 9px;border-radius:99px;background:#0b1220;border:1px solid var(--line)}
 .q{font-size:19px;font-weight:600;margin:6px 0 14px}
 .lbl{font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:var(--mut);margin:14px 0 4px}
 pre{white-space:pre-wrap;background:#0b1220;border:1px solid var(--line);border-radius:8px;padding:10px;margin:0;font-size:12.5px;color:#cbd5e1;max-height:260px;overflow:auto}
 .ans{background:#0b1e14;border:1px solid #14532d;border-radius:8px;padding:12px;color:#dcfce7}
 .pill{display:inline-block;background:#0b1220;border:1px solid var(--line);border-radius:8px;padding:3px 9px;margin:3px 4px 0 0;font-size:13px}
 .ask{margin-top:20px;padding:14px;border:1px dashed var(--acc);border-radius:10px;text-align:center}
 .acts{display:flex;gap:10px;margin-top:12px;flex-wrap:wrap;justify-content:center}
 button{font:inherit;font-weight:600;border:0;border-radius:10px;padding:11px 18px;cursor:pointer;color:#0b1220}
 .faith{background:var(--ok)}.unfaith{background:var(--no);color:#fff}.nav{background:transparent;color:var(--mut);border:1px solid var(--line)}
 .reveal{margin-top:16px;padding:12px 14px;border-radius:10px;border:1px solid var(--line);background:#0b1220;display:none}
 .reveal.show{display:block} .reveal.agree{border-color:var(--ok)} .reveal.disagree{border-color:var(--warn)}
 .kbd{font-size:11px;color:var(--mut);margin-top:12px;text-align:center}
 input[type=text]{width:100%;background:#0b1220;color:#e2e8f0;border:1px solid var(--line);border-radius:8px;padding:8px;font:inherit;margin-top:6px}
 .done{padding:30px 8px} .metric{font-size:34px;font-weight:700} .metric.bad{color:var(--no)} .metric.good{color:var(--ok)}
 table{border-collapse:collapse;width:100%;margin-top:14px;font-size:13px} td,th{border:1px solid var(--line);padding:7px 9px;text-align:left;vertical-align:top}
</style></head><body>
<header>
 <b>Judge Validation</b>
 <div class=bar><i id=barfill></i></div>
 <span class=chip id=counts></span>
 <button class=nav onclick=showSummary() style=margin-left:auto>Results ▸</button>
</header>
<main id=main></main>
<script>
let items=[], idx=0;
const $=s=>document.querySelector(s);
const esc=s=>(s+'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
async function load(){ items=await (await fetch('/api/items')).json(); idx=items.findIndex(i=>!i.user_label); if(idx<0)idx=0; render(); }
function progress(){ return items.filter(i=>i.user_label).length; }
function render(){
 const done=progress(), total=items.length;
 $('#barfill').style.width=(100*done/total)+'%';
 $('#counts').innerHTML=`<b>${done}</b>/${total} labeled`;
 const it=items[idx]; if(!it){ showSummary(); return; }
 const srcs=(it.sources_text||[]).map(esc).join('\\n\\n')||'(no sources retrieved)';
 const facts=(it.answer_key_facts||[]).map(f=>`<span class=pill>${esc(f)}</span>`).join('')||'<span class=chip>none</span>';
 $('#main').innerHTML=`<div class=card>
   <div class=row1><span class=badge>${it.route}</span><span class=chip>${it.id}</span>
     <span class=chip style=margin-left:auto>${idx+1} of ${total}</span></div>
   <div class=q>${esc(it.question)}</div>
   <div class=lbl>Sources the model was given</div><pre>${srcs}</pre>
   <div class=lbl>Answer the model produced</div><div class="pre ans">${esc(it.answer)}</div>
   <div class=ask>
     <b>Is every claim in the answer supported by the sources above?</b>
     <div class=chip>Judge grounding only — no fabricated / contradicted values. Completeness does NOT matter here. An abstention ("I don't have enough information") is faithful.</div>
     <div class=acts>
       <button class=faith onclick=label('faithful')>✓ Faithful <span class=chip>f</span></button>
       <button class=unfaith onclick=label('unfaithful')>✕ Not faithful <span class=chip>u</span></button>
     </div>
     <input type=text id=notes placeholder="optional note (why)" value="${esc(it.user_notes||'')}">
   </div>
   <div class=reveal id=reveal></div>
   <div class=acts><button class=nav onclick=go(-1)>← Prev</button><button class=nav onclick=go(1)>Next →</button></div>
   <div class=kbd>Keys: f faithful · u not faithful · ← → navigate. The judge's verdict is hidden until you decide.</div>
 </div>`;
 // if already labeled, show the reveal
 if(it.user_label) reveal(it.user_label);
}
async function label(v){ const it=items[idx]; const notes=$('#notes')?$('#notes').value:'';
 await fetch('/api/label/'+it.id,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({label:v,notes})});
 it.user_label=v; it.user_notes=notes; reveal(v);
 const c=$('#counts'); c.innerHTML=`<b>${progress()}</b>/${items.length} labeled`;
 $('#barfill').style.width=(100*progress()/items.length)+'%';
 setTimeout(()=>go(1), 700);
}
function reveal(v){ const it=items[idx]; const jf=it.judge_faithful?'faithful':'unfaithful';
 const agree=(v===jf); const el=$('#reveal'); el.className='reveal show '+(agree?'agree':'disagree');
 el.innerHTML=`${agree?'✓ You agree with the judge':'⚠ You DISAGREE with the judge'} — judge said <b>${jf}</b>.<br><span class=chip>${esc(it.judge_reason)}</span>`;
}
function go(d){ const j=idx+d; if(j>=items.length){ showSummary(); return; } if(j<0)return; idx=j; render(); }
async function showSummary(){ const s=await (await fetch('/api/summary')).json();
 const kappa=s.cohen_kappa==null?'—':s.cohen_kappa.toFixed(3);
 const raw=s.raw_agreement==null?'—':(100*s.raw_agreement).toFixed(1)+'%';
 const ok=s.raw_agreement!=null&&s.raw_agreement>=0.85;
 const dis=s.disagreements.map(d=>`<tr><td>${d.id}</td><td>you: <b>${d.human}</b><br>judge: <b>${d.judge}</b></td><td>${esc(d.judge_reason)}${d.notes?'<br><i>your note: '+esc(d.notes)+'</i>':''}</td></tr>`).join('');
 $('#main').innerHTML=`<div class="card done">
   <h2>Judge validation — ${s.n_labeled}/${s.n_total} labeled</h2>
   <div style=display:flex;gap:40px;flex-wrap:wrap;margin:16px 0>
     <div><div class=chip>RAW AGREEMENT</div><div class="metric ${ok?'good':'bad'}">${raw}</div><div class=chip>bar: ≥ 85%</div></div>
     <div><div class=chip>COHEN'S κ</div><div class="metric">${kappa}</div><div class=chip>chance-corrected</div></div>
   </div>
   ${s.n_labeled<s.n_total?`<p class=chip>Label all ${s.n_total} for a final number.</p>`:''}
   ${s.disagreements.length?`<div class=lbl>Disagreements — inspect these</div><table><tr><th>id</th><th>labels</th><th>judge reason / your note</th></tr>${dis}</table>`:'<p>✓ No disagreements.</p>'}
   <div class=acts><button class=nav onclick="idx=0;render()">◂ Back to review</button></div>
   <p class=kbd>κ near 1 = strong agreement beyond chance. With few unfaithful examples, κ is noisy — treat raw agreement as primary and inspect every disagreement.</p>
 </div>`;
}
document.addEventListener('keydown',e=>{ if(e.target.tagName==='INPUT')return;
 if(e.key==='f')label('faithful'); else if(e.key==='u')label('unfaithful');
 else if(e.key==='ArrowRight')go(1); else if(e.key==='ArrowLeft')go(-1); });
load();
</script></body></html>"""


def main():
    import uvicorn

    ap = argparse.ArgumentParser(description="Validate the faithfulness judge by hand.")
    ap.add_argument("--n", type=int, default=15, help="sample size to review")
    ap.add_argument("--all", action="store_true", help="review every answerable row")
    ap.add_argument("--tag", default="baseline", help="which report to validate")
    args = ap.parse_args()

    items = build_items(args.tag)
    n = len(items) if args.all else min(args.n, len(items))
    _STATE["items"] = sample_items(items, n)

    url = "http://127.0.0.1:8001"
    print(f"Judge validation ({len(_STATE['items'])} rows) → {url}  "
          f"(Ctrl+C to stop; autosaves to {LABELS_PATH})")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="warning")


if __name__ == "__main__":
    main()
