"""Local browser review app for the golden eval set.

    python -m src.eval.review_server      # starts on http://127.0.0.1:8000 and opens your browser

Click (or keyboard) to approve/reject/skip/edit each row. "Verify" shows the cited doc
text and runs the telemetry query (offline) so you can confirm a label inline. Every
action autosaves to Data/eval/golden.jsonl — stop and resume anytime. Local only.
"""
from __future__ import annotations

import threading
import webbrowser

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from src import config
from src.eval.triage import _corpus_map, _load, _run_handle, _save

app = FastAPI(title="Golden Eval Review")


class RowUpdate(BaseModel):
    status: str | None = None
    question: str | None = None
    route: str | None = None
    expected_sources: list[str] | None = None
    answer_key_facts: list[str] | None = None
    notes: str | None = None


def apply_update(rid: str, update: dict) -> dict | None:
    """Apply a partial update to the row with id `rid`, save, and return it."""
    rows = _load()
    for r in rows:
        if r["id"] == rid:
            for k, v in update.items():
                if v is not None:
                    r[k] = v
            _save(rows)
            return r
    return None


def verify_row(rid: str) -> list[dict]:
    """Return renderable evidence for each expected source of a row."""
    rows = {r["id"]: r for r in _load()}
    corpus = _corpus_map()
    row = rows.get(rid)
    if not row:
        return []
    out = []
    for src in row["expected_sources"]:
        if src.startswith("telemetry:"):
            out.append({"kind": "telemetry", "label": src, "text": _run_handle(src)})
        elif src in corpus:
            out.append({"kind": "doc", "label": f"{src} — {corpus[src].meta.get('title','')}",
                        "text": corpus[src].body})
        else:
            out.append({"kind": "unknown", "label": src, "text": "(source not found)"})
    return out


@app.get("/api/rows")
def api_rows():
    return JSONResponse(_load())


@app.post("/api/rows/{rid}")
def api_update(rid: str, update: RowUpdate):
    row = apply_update(rid, update.model_dump(exclude_none=True))
    return JSONResponse(row or {"error": "not found"}, status_code=200 if row else 404)


@app.get("/api/verify/{rid}")
def api_verify(rid: str):
    return JSONResponse(verify_row(rid))


@app.get("/", response_class=HTMLResponse)
def index():
    return PAGE


PAGE = """<!doctype html><html><head><meta charset=utf-8>
<title>Golden Eval Review</title><meta name=viewport content="width=device-width,initial-scale=1">
<style>
 :root{--bg:#0f172a;--card:#1e293b;--mut:#94a3b8;--line:#334155;--ok:#22c55e;--no:#ef4444;--acc:#38bdf8}
 *{box-sizing:border-box} body{margin:0;font:15px/1.5 system-ui,sans-serif;background:var(--bg);color:#e2e8f0}
 header{position:sticky;top:0;background:#0b1220;border-bottom:1px solid var(--line);padding:12px 20px;display:flex;gap:16px;align-items:center;flex-wrap:wrap}
 .bar{flex:1;height:8px;background:var(--line);border-radius:99px;overflow:hidden;min-width:120px}
 .bar>i{display:block;height:100%;background:var(--ok);width:0}
 .chip{font-size:12px;color:var(--mut)} .chip b{color:#e2e8f0}
 main{max-width:820px;margin:24px auto;padding:0 16px}
 .card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:22px}
 .row1{display:flex;gap:8px;align-items:center;margin-bottom:10px;flex-wrap:wrap}
 .badge{font-size:11px;font-weight:700;letter-spacing:.04em;padding:3px 9px;border-radius:99px;background:#0b1220;border:1px solid var(--line)}
 .badge.doc{color:#a5b4fc}.badge.timeseries{color:#7dd3fc}.badge.fusion{color:#fbbf24}.badge.out_of_scope{color:#fca5a5}
 .q{font-size:20px;font-weight:600;margin:6px 0 16px}
 .lbl{font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:var(--mut);margin-top:12px}
 .pill{display:inline-block;background:#0b1220;border:1px solid var(--line);border-radius:8px;padding:3px 9px;margin:3px 4px 0 0;font-size:13px}
 .notes{margin-top:12px;padding:10px 12px;background:#3b2f0b;border:1px solid #a16207;border-radius:8px;color:#fde68a;font-size:13px}
 .acts{display:flex;gap:10px;margin-top:22px;flex-wrap:wrap}
 button{font:inherit;font-weight:600;border:0;border-radius:10px;padding:11px 18px;cursor:pointer;color:#0b1220}
 .approve{background:var(--ok)}.reject{background:var(--no);color:#fff}.skip{background:var(--line);color:#e2e8f0}
 .edit,.verify{background:#0b1220;color:var(--acc);border:1px solid var(--acc)}
 .nav{background:transparent;color:var(--mut);border:1px solid var(--line)}
 .kbd{font-size:11px;color:var(--mut);margin-top:14px}
 .evi{margin-top:18px;border-top:1px solid var(--line);padding-top:14px;display:none}
 .evi.show{display:block}
 .evi .src{margin-bottom:12px} .evi .src .h{color:var(--acc);font-size:13px;font-weight:600;margin-bottom:4px}
 .evi pre{white-space:pre-wrap;background:#0b1220;border:1px solid var(--line);border-radius:8px;padding:10px;margin:0;font-size:12px;color:#cbd5e1;max-height:280px;overflow:auto}
 textarea,input,select{width:100%;background:#0b1220;color:#e2e8f0;border:1px solid var(--line);border-radius:8px;padding:8px;font:inherit;margin-top:4px}
 .done{text-align:center;padding:60px 20px;color:var(--mut)}
 .st{font-size:12px;padding:2px 8px;border-radius:99px} .st.approved{background:#052e16;color:var(--ok)} .st.rejected{background:#450a0a;color:#fca5a5} .st.unreviewed{background:#1e293b;color:var(--mut)}
</style></head><body>
<header>
 <b>Golden Eval Review</b>
 <div class=bar><i id=barfill></i></div>
 <span class=chip id=counts></span>
 <label class=chip><input type=checkbox id=onlyun checked> only unreviewed</label>
</header>
<main id=main></main>
<script>
let rows=[], idx=0, editing=false;
const $=s=>document.querySelector(s);
async function load(){ rows=await (await fetch('/api/rows')).json(); idx=firstIdx(); render(); }
function pool(){ return $('#onlyun').checked ? rows.filter(r=>r.status==='unreviewed') : rows; }
function firstIdx(){ const p=pool(); return p.length?rows.indexOf(p[0]):0; }
function counts(){ const c={approved:0,rejected:0,unreviewed:0}; rows.forEach(r=>c[r.status]=(c[r.status]||0)+1); return c; }
function render(){
 const c=counts(), total=rows.length, done=c.approved+c.rejected;
 $('#barfill').style.width=(100*done/total)+'%';
 $('#counts').innerHTML=`<b>${done}</b>/${total} reviewed · <span style=color:#22c55e>${c.approved} ok</span> · <span style=color:#ef4444>${c.rejected} rej</span> · ${c.unreviewed} left`;
 const p=pool();
 if(!p.length){ $('#main').innerHTML=`<div class=done><h2>🎉 All reviewed</h2><p>Finish in your terminal:<br><code>make eval-validate ARGS=--require-approved</code></p></div>`; return; }
 if(rows[idx]===undefined||( $('#onlyun').checked && rows[idx].status!=='unreviewed')) idx=firstIdx();
 const r=rows[idx];
 const srcs=r.expected_sources.map(s=>`<span class=pill>${esc(s)}</span>`).join('')||'<span class=chip>none</span>';
 const facts=r.answer_key_facts.map(s=>`<span class=pill>${esc(s)}</span>`).join('');
 const eng=r.expected_engine!=null?`<span class=chip>engine ${r.expected_engine}</span>`:'';
 $('#main').innerHTML=`<div class=card>
   <div class=row1><span class="badge ${r.route}">${r.route}</span><span class=chip>[${r.difficulty}]</span>${eng}
     <span class="st ${r.status}">${r.status}</span><span class=chip style=margin-left:auto>${r.id}</span></div>
   <div class=q>${esc(r.question)}</div>
   <div class=lbl>Proposed sources</div><div>${srcs}</div>
   <div class=lbl>Proposed answer facts</div><div>${facts}</div>
   ${r.notes?`<div class=notes>⚠ ${esc(r.notes)}</div>`:''}
   <div class=acts>
     <button class=approve onclick=act('approved')>✓ Approve <span class=chip>⏎</span></button>
     <button class=reject onclick=act('rejected')>✕ Reject <span class=chip>r</span></button>
     <button class=skip onclick=next()>Skip <span class=chip>s</span></button>
     <button class=verify onclick=verify()>🔍 Verify <span class=chip>v</span></button>
     <button class=edit onclick=edit()>✎ Edit <span class=chip>e</span></button>
   </div>
   <div class=acts><button class=nav onclick=prev()>← Prev</button><button class=nav onclick=next()>Next →</button></div>
   <div class=kbd>Keys: ⏎ approve · r reject · s skip · v verify · e edit · ← → navigate</div>
   <div class=evi id=evi></div>
 </div>`;
}
function esc(s){return (s+'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
async function act(status){ const r=rows[idx]; const u=await (await fetch('/api/rows/'+r.id,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({status})})).json(); rows[idx]=u; next(); }
function next(){ const p=pool(); let j=idx; do{ j++; }while(j<rows.length && $('#onlyun').checked && rows[j] && rows[j].status!=='unreviewed'); if(j<rows.length){idx=j;} else {idx=firstIdx();} render(); }
function prev(){ let j=idx; do{ j--; }while(j>=0 && $('#onlyun').checked && rows[j] && rows[j].status!=='unreviewed'); if(j>=0)idx=j; render(); }
async function verify(){ const e=$('#evi'); if(e.classList.contains('show')){e.classList.remove('show');return;} e.innerHTML='<div class=chip>loading…</div>'; e.classList.add('show'); const ev=await (await fetch('/api/verify/'+rows[idx].id)).json(); e.innerHTML=ev.map(s=>`<div class=src><div class=h>${s.kind==='telemetry'?'📈':'📄'} ${esc(s.label)}</div><pre>${esc(s.text)}</pre></div>`).join('')||'<div class=chip>no sources</div>'; }
function edit(){ const r=rows[idx]; $('#main').querySelector('.card').innerHTML=`
   <div class=lbl>Question</div><textarea id=e_q rows=2>${esc(r.question)}</textarea>
   <div class=lbl>Route</div><select id=e_route>${['doc','timeseries','fusion','out_of_scope'].map(x=>`<option ${x===r.route?'selected':''}>${x}</option>`).join('')}</select>
   <div class=lbl>Expected sources (one per line)</div><textarea id=e_src rows=3>${esc(r.expected_sources.join('\\n'))}</textarea>
   <div class=lbl>Answer facts (one per line)</div><textarea id=e_facts rows=4>${esc(r.answer_key_facts.join('\\n'))}</textarea>
   <div class=lbl>Notes</div><textarea id=e_notes rows=2>${esc(r.notes||'')}</textarea>
   <div class=acts><button class=approve onclick=saveEdit()>Save & Approve</button><button class=nav onclick=render()>Cancel</button></div>`; }
async function saveEdit(){ const r=rows[idx]; const body={question:$('#e_q').value.trim(),route:$('#e_route').value,
   expected_sources:$('#e_src').value.split('\\n').map(x=>x.trim()).filter(Boolean),
   answer_key_facts:$('#e_facts').value.split('\\n').map(x=>x.trim()).filter(Boolean),
   notes:$('#e_notes').value.trim(),status:'approved'};
   const u=await (await fetch('/api/rows/'+r.id,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})).json(); rows[idx]=u; next(); }
document.addEventListener('keydown',e=>{ if(editing||['TEXTAREA','INPUT','SELECT'].includes(e.target.tagName))return;
  if(e.key==='Enter')act('approved'); else if(e.key==='r')act('rejected'); else if(e.key==='s')next();
  else if(e.key==='v')verify(); else if(e.key==='e')edit(); else if(e.key==='ArrowRight')next(); else if(e.key==='ArrowLeft')prev(); });
$('#onlyun').addEventListener('change',()=>{idx=firstIdx();render();});
load();
</script></body></html>"""


def main():
    import uvicorn

    url = "http://127.0.0.1:8000"
    print(f"Golden eval review → {url}  (Ctrl+C to stop; autosaves to {config.GOLDEN_EVAL})")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")


if __name__ == "__main__":
    main()
