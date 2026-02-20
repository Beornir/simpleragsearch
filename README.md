# Meridian Knowledge Base — RAG System

Question-answering system over the internal knowledge base of Meridian Technologies. 34 documents: HR policies, engineering ADRs, runbooks, meeting transcripts, Slack exports.

---

## Quick Start

### Prerequisites

- Docker and Docker Compose
- LLM server (vLLM, OpenAI-compatible) — configure endpoints in `docker-compose.yml`
- The `rag/metadata.csv` and `rag/master_tags.json` files must exist (produced by the ingestion step)

### 1. Run ingestion (first time only)

Reads all files from `knowledge_base/`, generates descriptions + tags via LLM, embeds descriptions, writes `rag/metadata.csv` and `rag/master_tags.json`.

```bash
docker compose --profile ingest up --build
```

This takes ~3–5 minutes for 34 documents (one LLM call + one embedding call per file).

### 2. Start the search API + UI

```bash
docker compose up --build search
```

When you see:
```
[Index] Loaded 34 documents, 42 canonical tags, 4 conflict pairs
INFO:     Application startup complete.
```

Open **http://localhost:8000** in your browser.

### 3. Query via API

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "How many PTO days do senior engineers get?"}'
```

To use the LLM reranker (slower but higher quality on factual questions):

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "...", "use_reranker": true}'
```

### 4. Run evaluation

Requires the search service to be running on `localhost:8000`.

```bash
# Basic eval (no reranker)
docker compose run --rm search python3 03_eval/run_eval.py

# Eval with reranker + before/after comparison
docker compose run --rm search python3 03_eval/run_eval_v2.py
```

Results saved to `rag/03_eval/eval_results.json` and `rag/03_eval/eval_summary.md`.

### Configuration

All settings are in `rag/config.py` and can be overridden via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_BASE_URL` | `http://100.86.119.53:2000/v1` | LLM server (vLLM / OpenAI-compatible) |
| `LLM_MODEL` | `Qwen3-30B-A3B-GPTQ-Int4` | Model name |
| `EMBED_BASE_URL` | `http://100.86.119.53:2001/v1` | Embedding server |
| `EMBED_MODEL` | `Qwen3-Embedding-0.6B` | Embedding model name |
| `KB_PATH` | `ml_takehome/knowledge_base` | Path to knowledge base directory |
| `METADATA_CSV` | `rag/metadata.csv` | Path to metadata index |
| `MASTER_TAGS_JSON` | `rag/master_tags.json` | Path to tag taxonomy |

---

## Architecture

The core idea: instead of chunking documents and embedding raw text, the LLM writes a description for each file — and that description is embedded. Retrieval runs over descriptions; generation runs over full file content.

```
Each file in knowledge_base/
        │
        ▼
  LLM reads the full file
  → writes a description (3–4 sentences, ≤120 words)
  → assigns tags from a 42-tag taxonomy
  → embedder turns description into a 1024d vector
        │
        ▼
  metadata.csv  ←  filepath | description | tags | embedding | metadata
```

**Why file-level instead of chunks:** The KB is small (34 files). Each file is a coherent unit — one policy, one ADR, one runbook. A whole-file description captures meaning better than a fragment. Contradiction detection also requires both conflicting documents to appear in retrieval, which chunk-level indexing makes harder. Full rationale in `rag/notebook.md`.

---

## Models

| Role | Model | Host |
|------|-------|------|
| LLM (descriptions, tags, reranking, generation) | Qwen3-30B-A3B-GPTQ-Int4 | configurable via `LLM_BASE_URL` |
| Embeddings | Qwen3-Embedding-0.6B (dim=1024) | configurable via `EMBED_BASE_URL` |

Both servers run vLLM with an OpenAI-compatible API. The system message `/no_think` suppresses Qwen3 thinking tokens.

---

## Tags

42-tag curated taxonomy, two tiers:
- **Semantic categories** (~20): `hr-policy`, `security-policy`, `runbook`, `product-spec`, `meeting-transcript`, `deploy-process`, `monitoring`, `database`, etc.
- **Proper nouns** (~22): `kafka`, `postgresql`, `vault`, `datadog`, `grafana`, `okta`, `argocd`, `mlflow`, `sagemaker`, etc.

The LLM assigns tags from this fixed list only. At query time, any tag not in the list is silently dropped.

---

## Retrieval

Three signals computed in parallel per query:

```
user query
    │
    ├── embed(query) → cosine similarity against each description  × 0.55
    │
    ├── LLM extracts query tags → overlap(query_tags, doc_tags)    × 0.25
    │   tag_score = |intersection| / |query_tags|
    │
    └── BM25(query) over description texts, normalized to [0,1]    × 0.20

final_score = 0.55 × vec + 0.25 × tag + 0.20 × bm25
```

Top-10 documents by score are passed to the generator.

**Why BM25 on top of embeddings:** Embeddings capture semantics but miss vocabulary gaps — e.g. a query about "code freeze" doesn't vector-match a document about "deploy freeze periods." BM25 adds exact keyword matching and closes that gap.

---

## Reranker

The top-10 are passed to Qwen3-30B which **sorts** them by relevance. This is a sort-only reranker — no filtering, all 10 documents stay.

**Why not filter:** An earlier version stopped at top-1 when the answer seemed sufficient. This broke contradiction detection — the LLM only saw one version of a conflicting policy. Keeping all docs in context is more important than saving tokens.

**Conflict pair promotion:** If both documents in a known conflict pair appear in the top-10 (e.g. `pto_policy.md` and `pto_policy_2023.md`), they are moved to the front — so the LLM always sees them together and flags the contradiction.

Conflict pairs are stored in `metadata.csv` via `supersedes` and `conflict_with` columns — no hardcoding:

| Document | Relationship |
|----------|-------------|
| `pto_policy.md` | supersedes `pto_policy_2023.md` |
| `adr_003_v2_database_strategy.md` | supersedes `adr_003_database_migration.md` |
| `expense_policy_DRAFT.md` | supersedes `expense_policy.md` |
| `architecture_overview.md` | conflict_with `deploy_process.md` |

---

## Generation

The generator loads the **full content** of all top-10 files (up to 8,000 characters per file) and passes them with the question to Qwen3-30B.

System prompt instructs the model to:
- Answer only from the provided sources and always cite them
- When two documents contradict each other — show both versions, identify which is newer, recommend it as authoritative
- Say "I don't have enough information" when the specific document doesn't exist in the KB — not just when the topic is vaguely absent, but when the exact document is missing
- Treat `[File not found: ...]` entries as missing files and answer IDK

Contradiction detection is double: keyword matching in the answer ("contradict", "two versions", "updated policy", etc.) + automatic check via `supersedes`/`conflict_with` metadata columns.

---

## Evaluation Results

Evaluated on 40 questions across 5 categories. Judge: Qwen3-30B, scale 0–3.

| Metric | Baseline | Final system |
|--------|----------|--------------|
| Source Recall@10 | 94.2% | 93.8% |
| Contradiction Detection | 100% | 80% |
| Abstention Rate | 60% | 60% |
| Answer Quality avg (0–3) | 2.73 | **2.77** |
| Answer Quality ≥2 | 97.5% | 97.5% |
| Questions improved | — | +5 |
| Questions regressed | — | −4 |

**Baseline** — hybrid search (vector + tags, no BM25) → direct generation. Conflict pairs hardcoded in source, tags generated freely without a fixed vocabulary.

**Final system** adds BM25, sort-only reranker with conflict pair promotion, 42-tag curated taxonomy, and data-driven conflict detection via metadata.

**Contradiction Detection regression (100% → 80%)** is an intentional trade-off. An earlier iterative reranker that truncated context to top-1 scored 40% on this metric. The sort-only reranker brought it back to 80% by keeping both conflicting documents in context. The remaining miss is the Datadog vs Grafana question — those files don't always co-appear in top-10.

**Abstention Rate 60%** — the hardest category. Confidence scoring (a second LLM call to verify the answer is grounded) was attempted and reverted: it caused 13 regressions because the model can't reliably distinguish "directly stated in the source" from "synthesized from loosely related material."

Full per-question breakdown: `rag/03_eval/before_after_comparison.md`

---

## Repository Structure

```
simpleragsearch/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .gitignore
├── README.md
├── rag/
│   ├── config.py               # single shared config, all settings via env vars
│   ├── metadata.csv            # document index (generated by ingest)
│   ├── master_tags.json        # 42-tag taxonomy (generated by ingest)
│   ├── notebook.md             # engineering notebook (Parts 1–4)
│   ├── 01_ingestion/
│   │   ├── ingest.py           # full ingestion pipeline
│   │   ├── retag.py            # re-tag existing index with new taxonomy
│   │   └── fix_manifest_row.py # patch manifest CSV row
│   ├── 02_search/
│   │   ├── api.py              # FastAPI app + web UI
│   │   ├── retrieval.py        # hybrid retrieval (vector + tag + BM25)
│   │   ├── reranker.py         # sort-only LLM reranker
│   │   └── generator.py        # answer generation
│   └── 03_eval/
│       ├── run_eval.py         # evaluation harness (no reranker)
│       ├── run_eval_v2.py      # evaluation with reranker + comparison
│       ├── eval_results.json
│       ├── eval_summary.md
│       └── before_after_comparison.md
└── ml_takehome/
    ├── knowledge_base/         # source documents (mounted read-only in Docker)
    └── eval/
        └── questions.jsonl     # 40 evaluation questions
```
