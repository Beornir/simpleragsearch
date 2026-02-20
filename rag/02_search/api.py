"""
FastAPI app — simple web UI + /query endpoint.
"""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from retrieval import load_index, retrieve
from reranker import iterative_rerank_and_generate
from generator import generate

app = FastAPI(title="Meridian Knowledge Base")


@app.on_event("startup")
def startup():
    load_index()


# ─── Models ───────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str
    top_k: int = 10
    use_reranker: bool = False


class RetrievedDoc(BaseModel):
    filepath: str
    score: float
    vec_score: float
    tag_score: float
    description: str
    status: str
    last_modified: str


class QueryResponse(BaseModel):
    answer: str
    sources: list[str]
    has_contradiction: bool
    retrieved: list[RetrievedDoc]
    query_tags: list[str]


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest):
    retrieved = retrieve(req.question)
    if req.use_reranker:
        result = iterative_rerank_and_generate(req.question, retrieved)
    else:
        max_score = max(doc["score"] for doc in retrieved) if retrieved else 0.0
        result = generate(req.question, retrieved, max_retrieval_score=max_score)
    return QueryResponse(
        answer=result["answer"],
        sources=result["sources"],
        has_contradiction=result["has_contradiction"],
        retrieved=[
            RetrievedDoc(
                filepath=doc["filepath"],
                score=doc["score"],
                vec_score=doc["vec_score"],
                tag_score=doc["tag_score"],
                description=doc["description"],
                status=doc.get("status", ""),
                last_modified=doc.get("last_modified", ""),
            )
            for doc in retrieved
        ],
        query_tags=retrieved[0]["query_tags"] if retrieved else [],
    )


@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse(content=HTML_UI)


HTML_UI = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Meridian Knowledge Base</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #f5f5f5; color: #333; }
  .container { max-width: 900px; margin: 40px auto; padding: 0 20px; }
  h1 { font-size: 1.6rem; font-weight: 600; margin-bottom: 4px; }
  .subtitle { color: #666; font-size: 0.9rem; margin-bottom: 28px; }
  .search-box { display: flex; gap: 10px; margin-bottom: 28px; }
  textarea { flex: 1; padding: 12px 14px; font-size: 0.95rem; border: 1px solid #ddd;
             border-radius: 8px; resize: vertical; min-height: 70px; font-family: inherit; }
  button { padding: 12px 24px; background: #2563eb; color: white; border: none;
           border-radius: 8px; font-size: 0.95rem; cursor: pointer; align-self: flex-end; }
  button:hover { background: #1d4ed8; }
  button:disabled { background: #93c5fd; cursor: not-allowed; }
  .answer-card { background: white; border-radius: 10px; padding: 24px;
                 box-shadow: 0 1px 3px rgba(0,0,0,.08); margin-bottom: 20px; }
  .contradiction-banner { background: #fef3c7; border: 1px solid #f59e0b;
                          border-radius: 8px; padding: 10px 14px; margin-bottom: 14px;
                          font-size: 0.88rem; color: #92400e; }
  .answer-text { line-height: 1.7; white-space: pre-wrap; font-size: 0.95rem; }
  .sources { margin-top: 16px; padding-top: 14px; border-top: 1px solid #eee; }
  .sources h3 { font-size: 0.8rem; text-transform: uppercase; color: #888;
                letter-spacing: .05em; margin-bottom: 8px; }
  .source-tag { display: inline-block; background: #eff6ff; color: #2563eb;
                border-radius: 4px; padding: 2px 8px; font-size: 0.8rem;
                margin: 2px 4px 2px 0; font-family: monospace; }
  .debug { background: white; border-radius: 10px; padding: 20px;
           box-shadow: 0 1px 3px rgba(0,0,0,.08); }
  .debug h2 { font-size: 0.9rem; text-transform: uppercase; color: #888;
              letter-spacing: .05em; margin-bottom: 14px; }
  .doc-row { border-bottom: 1px solid #f0f0f0; padding: 10px 0; font-size: 0.85rem; }
  .doc-row:last-child { border-bottom: none; }
  .doc-name { font-weight: 600; font-family: monospace; color: #1e40af; }
  .doc-score { float: right; color: #888; }
  .doc-desc { color: #555; margin-top: 3px; }
  .tag-list { margin-top: 6px; }
  .tag { display: inline-block; background: #f3f4f6; color: #555; border-radius: 3px;
         padding: 1px 6px; font-size: 0.75rem; margin: 1px 2px 1px 0; }
  .query-tags { margin-bottom: 20px; font-size: 0.85rem; color: #555; }
  .query-tags strong { color: #333; }
  .spinner { display: none; margin: 20px auto; text-align: center; color: #666; }
  .error { background: #fef2f2; border: 1px solid #fca5a5; border-radius: 8px;
           padding: 14px; color: #991b1b; }
</style>
</head>
<body>
<div class="container">
  <h1>Meridian Knowledge Base</h1>
  <p class="subtitle">Ask anything about company policies, engineering systems, or product decisions.</p>

  <div class="search-box">
    <textarea id="question" placeholder="e.g. How many PTO days do senior engineers get?&#10;What is the current database migration strategy?"></textarea>
    <button id="askBtn" onclick="ask()">Ask</button>
  </div>

  <div class="spinner" id="spinner">Thinking...</div>
  <div id="result"></div>
</div>

<script>
async function ask() {
  const q = document.getElementById('question').value.trim();
  if (!q) return;
  const btn = document.getElementById('askBtn');
  btn.disabled = true;
  document.getElementById('spinner').style.display = 'block';
  document.getElementById('result').innerHTML = '';

  try {
    const res = await fetch('/query', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({question: q})
    });
    const data = await res.json();

    let html = '';

    if (data.query_tags && data.query_tags.length) {
      html += `<div class="query-tags"><strong>Matched tags:</strong> ${data.query_tags.map(t => `<span class="tag">${t}</span>`).join(' ')}</div>`;
    }

    html += '<div class="answer-card">';
    if (data.has_contradiction) {
      html += '<div class="contradiction-banner">⚠️ Contradictory information detected across sources — review carefully.</div>';
    }
    html += `<div class="answer-text">${escHtml(data.answer)}</div>`;
    if (data.sources && data.sources.length) {
      html += '<div class="sources"><h3>Sources used</h3>';
      data.sources.forEach(s => { html += `<span class="source-tag">${escHtml(s)}</span>`; });
      html += '</div>';
    }
    html += '</div>';

    if (data.retrieved && data.retrieved.length) {
      html += '<div class="debug"><h2>Retrieved documents</h2>';
      data.retrieved.forEach(doc => {
        html += `<div class="doc-row">
          <span class="doc-name">${escHtml(doc.filepath)}</span>
          <span class="doc-score">score ${doc.score} (vec ${doc.vec_score} | tag ${doc.tag_score})</span>
          <div class="doc-desc">${escHtml(doc.description)}</div>
        </div>`;
      });
      html += '</div>';
    }

    document.getElementById('result').innerHTML = html;
  } catch(e) {
    document.getElementById('result').innerHTML = `<div class="error">Error: ${e.message}</div>`;
  } finally {
    btn.disabled = false;
    document.getElementById('spinner').style.display = 'none';
  }
}

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

document.getElementById('question').addEventListener('keydown', e => {
  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) ask();
});
</script>
</body>
</html>
"""
