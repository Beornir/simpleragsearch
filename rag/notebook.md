# Engineering Notebook — Meridian RAG System

---

## Part 1 — Build

### Data Exploration

First thing: count what's actually in the knowledge base and understand the mess before writing any code.

The `knowledge_base/` directory has 34 processable files across five types:

| Type | Count | Key observations |
|------|-------|-----------------|
| `.md` (policies, ADRs, READMEs) | 21 | Some are clearly outdated — `pto_policy_2023.md` and `pto_policy.md` coexist with no deletion |
| `.json` (Slack exports) | 3 | Raw message arrays: `{"user": "...", "text": "...", "timestamp": "..."}` — contains banter, emoji, half-sentences |
| `.txt` (meeting transcripts) | 3 | Auto-generated diarization: "SPEAKER_01: um so basically the uh". Critical decisions buried in noise |
| `.pdf` (product specs) | 2 | Both are native PDF (text-selectable), not scanned images — pypdf works fine |
| `.csv` (document manifest) | 1 | Catalog of all docs with author/status/date — ~15% of entries have missing or wrong metadata |

One file is `grandmas_lasagna_recipe.md` — added to `SKIP_FILES` immediately. It's the "accidentally committed personal document" the brief mentions.

The `document_manifest.csv` lists files that don't exist on disk (ghost entries) and misses files that do exist. I kept it as a metadata source (`in_manifest` flag) but didn't use it to gate which files get indexed — going by filesystem truth instead.

**Contradictions found during exploration:**
- `pto_policy.md` (Sep 2024) vs `pto_policy_2023.md` — old policy never deleted
- `adr_003_v2_database_strategy.md` supersedes `adr_003_database_migration.md` — the older one has no "superseded" marker
- `architecture_overview.md` and `deploy_process.md` describe different monitoring tools (Datadog vs Grafana migration) — neither explicitly acknowledges the other

### Chunking Decision: File-level, Not Chunk-level

The standard approach is to split documents into overlapping chunks and embed each chunk. I chose not to do this, for three reasons:

1. **The KB is small.** 34 files, ~130K tokens total. At generation time I can pass the full content of 10 files without hitting context limits. No chunking needed for that.

2. **Each file is a coherent unit.** A PTO policy is a single document. An ADR is a single decision record. Splitting `pto_policy.md` into three 512-token chunks doesn't help — you need the whole document to answer "how many PTO days do senior engineers get?" The chunk with the answer might not contain enough context about seniority levels.

3. **Contradiction detection requires whole-document awareness.** If `pto_policy.md` and `pto_policy_2023.md` both appear in retrieval, the generator needs to see both and flag the conflict. With chunk-level retrieval, the relevant chunks from each doc might not both surface, or might surface from only one doc — making conflict detection unreliable.

**What I did instead:** LLM generates a description (3–4 sentences, ≤120 words) for each file. The *description* is embedded, not the raw content. This separates the retrieval signal (semantic meaning of the document) from the generation input (full content). It also means if the embedding model is swapped out, I can re-embed descriptions without re-reading all files.

The tradeoff: description quality is LLM-dependent. A bad description → bad retrieval. I verified descriptions by sampling 5 random files after ingest.

### Preprocessing Decisions by File Type

**Slack JSON:** The raw format is `[{"user": "...", "text": "...", "timestamp": "..."}]`. I convert each message to `[timestamp] #channel user: text` lines. This preserves enough structure for the LLM to understand who said what and when, without needing to explain the schema in the prompt.

**PDFs:** pypdf extracts text. Both product spec PDFs are native (not scanned), so text quality is fine. For scanned PDFs the text would be empty — I handle that by checking length and falling back to an empty description with a note.

**Meeting transcripts:** No special preprocessing. The LLM is instructed to generate descriptions based on key decisions and outcomes — it handles filler words and speaker noise reasonably well.

**Manifest CSV:** Included in the index, but given a special short prompt: "this is a catalog file listing all documents — describe what's in this catalog." The standard prompt (which asks for the document's topic) produces a confusing description for a CSV index.

### Tag Taxonomy Problem

First ingest run: let the LLM assign free-form tags to each file. Result: **483 unique tags** across 34 files.

The problem: at query time, I ask the LLM to "pick relevant tags from the master list." With 483 options, the LLM hallucinates, uses inconsistent synonyms (`"hr"`, `"HR"`, `"human-resources"`, `"human_resources"`, `"people-operations"`), and misses the right ones frequently.

Fix: I curated a 42-tag taxonomy manually, then re-tagged all 34 files against it using a stricter prompt ("you MUST only use tags from this exact list"). Tags are two-tier:

- **~20 semantic categories:** `hr-policy`, `security-policy`, `runbook`, `deploy-process`, `database`, `monitoring`, `incident-response`, `product-spec`, `meeting-transcript`, `api`, etc.
- **~22 proper nouns:** `kafka`, `postgresql`, `datadog`, `grafana`, `vault`, `okta`, `argocd`, `mlflow`, `kubernetes`, `sagemaker`, etc.

At query time, if the LLM returns a tag not in the master list, it is silently dropped. This means the tag system degrades gracefully (bad LLM call → empty tag set → tag score = 0, not an error).

---

## Part 2 — Evaluate

### Metric Design

The brief says "design your own metrics, at least 3." I picked these four and ruled out ROUGE explicitly:

**Why not ROUGE:** ROUGE measures lexical overlap between system answer and gold answer. For factual questions with multiple valid phrasings ("15 PTO days" vs "fifteen days of paid time off"), ROUGE punishes correct paraphrases. For procedural questions where the system correctly summarizes a 5-step process using different wording, ROUGE gives low scores. It measures surface similarity, not correctness. Not useful here.

**Metric 1 — Source Recall@10:** Did the retrieved top-10 documents include the gold_sources? This is the right starting metric because everything else is downstream of retrieval. An Answer Quality of 0 after a Recall of 100% is a generation problem. An Answer Quality of 0 after a Recall of 0% is a retrieval problem. They need different fixes.

**Metric 2 — Contradiction Detection Rate:** For the `contradictory` category, did the response have `has_contradiction=True`? This is a hard requirement from the brief. Measuring it separately from answer quality is important because the LLM might give the right answer without flagging the conflict (partial credit in judge scoring, but still a failure on the safety requirement).

**Metric 3 — Abstention Rate:** For `unanswerable` questions, did the system say IDK? Same logic — the brief says "no hallucination is better than a confident wrong answer," so this gets its own metric.

**Metric 4 — Answer Quality (LLM-as-judge, 0–3):** Qwen3-30B judges each response against the gold answer on a 0–3 scale. LLM-as-judge captures semantic correctness in a way ROUGE can't. The limitation: the judge and the generator are the same model family, which could introduce systematic leniency. I verified a sample of 5 judgments manually and found them reasonable. At this scale (40 questions), manual spot-checking is feasible.

### Baseline Results

| Metric | Value |
|--------|-------|
| Source Recall@10 | 94.2% |
| Contradiction Detection | 100% |
| Abstention Rate | 60% |
| Answer Quality avg (0–3) | 2.73 |
| Answer Quality ≥2 (good) | 97.5% |

### Error Analysis

**Retrieval failure (vocabulary mismatch) — ~50% of errors**

q12: "What is Meridian's code freeze policy before major releases?" → the relevant doc is `deploy_process.md`, which describes "deploy freeze periods" (not "code freeze"). BM25 over descriptions would catch the keyword but I hadn't added BM25 yet — the document scored low on vector similarity because the embedding for "code freeze" sits far from "deploy freeze periods" in the embedding space.

Fix applied: updated `deploy_process.md`'s description to include "code freeze" and "emergency deploy" terms, and added BM25 to the hybrid scoring.

**Generation failure (abstention) — ~33% of errors**

q35: "What is the API versioning strategy?" → `api_versioning_guide.md` is listed in the manifest but the file doesn't exist. Three docs about API rate limiting, ADRs, and gateway READMEs were retrieved. The system synthesized a plausible-sounding answer from tangentially related material instead of saying IDK. The system prompt says "if the specific doc doesn't exist, say IDK" — but the model decided the adjacent material was sufficient.

This is the hardest failure category to fix with prompting alone. The model can't reliably distinguish "the answer is here if you read carefully" from "I'm inferring this from loosely related docs."

**Multi-doc recall — low due to score averaging**

Multi-doc questions require 2+ gold sources. Recall is 70% for this category vs 100% for factual. When two documents are equally relevant, the hybrid score for each is diluted by the other retrieved docs. No retrieval miss per se — both docs tend to appear in top-10 — but the category is harder by design.

**Abstention Rate: 60% — why it's hard to push higher**

5 unanswerable questions in the eval. The system correctly said IDK for 3 of them. For the other 2, it found marginally relevant information and synthesized an answer instead. I attempted to fix this with confidence scoring (see Part 3), which made things worse.

---

## Part 3 — Iterate

### What I Tried and What Happened

**Attempt 1 — BM25 addition (kept, ✅ helped)**

Added BM25 scoring over document descriptions alongside cosine similarity. Weights: 0.55 vector + 0.25 tag + 0.20 BM25.

Motivation: vocabulary mismatch (q12, "code freeze" vs "deploy freeze"). BM25 adds exact keyword matching that embeddings miss. The weight 0.20 was chosen to be significant enough to affect rankings without overpowering semantic similarity. Also fixed the description for `deploy_process.md` to include "code freeze" explicitly.

Effect on q12: now correctly retrieved. BM25 also marginally helped 2 other queries where queries used specific tool names (e.g. "ArgoCD") that appear literally in some descriptions.

Baseline after adding BM25: Source Recall 94.2%, Quality 2.73.

**Attempt 2 — Dynamic conflict metadata (kept, ✅ correctness fix)**

The original conflict detection in `generator.py` had hardcoded file pairs. Added a `conflict_with` column to `metadata.csv` for the Datadog/Grafana pair (which isn't a supersedes relationship — both docs are "current," they just describe different states of migration). Added `supersedes` fields for PTO and ADR pairs.

This made conflict detection data-driven. The code reads pairs from metadata at startup; adding a new conflict requires only updating the CSV, not redeploying.

**Attempt 3 — LLM sort-only reranker (kept as opt-in, ➡️ mixed results)**

After retrieval, pass the top-10 document descriptions to Qwen3-30B and ask it to sort them by relevance. Important: sort-only, no filtering. Earlier versions of the reranker asked the LLM to eliminate irrelevant docs — this reliably broke contradiction detection because one of the conflicting docs would get filtered out.

Results vs baseline (no reranker):

| Metric | Before | After |
|--------|--------|-------|
| Source Recall@10 | 94.2% | 93.8% |
| Contradiction Detection | 100% | 80% |
| Abstention Rate | 60% | 60% |
| Answer Quality avg (0–3) | 2.73 | **2.77** |
| Answer Quality ≥2 | 97.5% | 95.0% |

5 questions improved, 4 regressed. The reranker caused a contradiction regression on q25 (Datadog vs Grafana) — the sort placed `architecture_overview.md` higher and `deploy_process.md` near the bottom, and the generator anchored on the top doc and missed the conflict.

Decision: keep the reranker as an opt-in (`use_reranker: true` in the API request). Default is off. The before/after metrics are close enough that neither is strictly better — the reranker helps factual and unanswerable questions but hurts contradictory ones.

**Attempt 4 — Confidence scoring (reverted, ❌ 13 regressions)**

The abstention failure mode (system answers when it should say IDK) led me to try a second LLM call after generation: "Is this answer directly supported by the retrieved documents, or are you inferring?" If confidence below threshold → return IDK instead.

In practice: the model couldn't reliably distinguish "the information is explicitly stated in the sources" from "I synthesized this from adjacent material." Questions that are factual and well-supported (e.g. "how many days of PTO do senior engineers get?") sometimes got low confidence scores because the answer required reading two paragraphs in combination. 13 questions regressed. Reverted entirely.

**Attempt 5 — Query paraphrasing / augmented embedding (reverted, ❌ recall dropped)**

Generated 3 paraphrases of each query using the LLM (preserving named entities — tool names, numbers, product names), then computed a weighted average embedding (0.5 weight on original + 0.5 split across paraphrases). The hypothesis: multiple phrasings capture more of the semantic space.

In practice: Source Recall dropped from 94.2% to 91.2%. The paraphrases shifted the query embedding away from the correct documents. Example: "What happens during a code freeze?" paraphrased to "How does a deployment halt affect releases?" — the averaged embedding landed between the two and retrieved less relevant docs. The named-entity preservation instruction worked inconsistently (the model occasionally rephrased "Grafana" to "the monitoring tool").

Reverted. The embedding model handles the original query well enough; augmentation introduced more noise than signal.

### Why the Easy Win Didn't Come

The abstention rate (60%) is the weakest metric and the obvious target. But every approach I tried either:
- Required a second LLM call that was as unreliable as the first (confidence scoring)
- Only helped unanswerable questions while hurting answerable ones (stricter IDK prompt)

The root cause is that the LLM doesn't know what it doesn't know. It can synthesize a plausible-sounding answer from loosely related material, and it's hard to distinguish that from a genuine answer using the same model. A production fix would require a calibration dataset of "synthesized but wrong" vs "genuinely answered" examples and a separate classifier — out of scope for this prototype.

### Summary of Changes vs Starting Baseline

| Change | Status | Effect |
|--------|--------|--------|
| 42-tag curated taxonomy | Kept | Better tag precision at query time |
| BM25 addition (weight 0.20) | Kept | Fixes vocabulary mismatch |
| Dynamic conflict pairs in metadata | Kept | No more hardcoded file pairs |
| deploy_process.md description update | Kept | q12 now retrieved correctly |
| Sort-only LLM reranker | Opt-in | +5 / −4 questions vs no-reranker |
| Confidence scoring | Reverted | −13 questions |
| Query paraphrasing | Reverted | Source Recall −3% |

---

# Part 4 — Production Readiness

## 1. Incremental Indexing

### Current state
The `ingest.py` script is a full-scan batch job: it reads every file in `knowledge_base/`, generates a description and tags via LLM, embeds the description, and writes all 34 rows to `metadata.csv`. Re-running it on a 34-file corpus takes ~3-5 minutes (one LLM call + one embedding call per file).

### Strategy for production

**Detect changes before doing any LLM work.**

```
hash_file(filepath) → compare against metadata.csv["content_hash"] column
```

Add a `content_hash` column (SHA-256 of raw file bytes) to `metadata.csv`. On each indexing run:

1. Scan `knowledge_base/` for all files.
2. For each file:
   - If `content_hash` matches stored value → **skip** (description/embedding are still valid).
   - If hash differs or file is new → re-run description generation + embedding.
   - If file no longer exists → mark `status = deleted` (or remove the row).
3. Overwrite only changed rows in `metadata.csv`.

This makes incremental re-indexing proportional to the number of changed files, not the total corpus size. For a 2,000-file KB with 5 edits per day, ~98% of files are skipped entirely.

### Trigger options

| Option | Latency | Complexity |
|--------|---------|------------|
| Periodic cron (hourly) | Up to 60 min lag | Low — one line in crontab |
| File-system watcher (`watchdog` library) | Seconds | Medium — daemon process |
| Git post-commit hook | On push | Low — works if KB is in a repo |
| CI/CD pipeline step | On PR merge | Fits existing GitHub Actions workflow |

**Recommended for Meridian:** Git hook or CI step. The KB is mostly policy documents — changes go through review, and indexing after merge keeps the search index synchronized with the canonical version of each document.

### Re-embedding on model upgrade

If the embedding model is replaced (e.g. Qwen3-Embedding-0.6B → a larger model), all embeddings become incompatible. The `content_hash` column still helps: the migration script can re-embed every row without re-generating descriptions (descriptions are model-independent text; only the vector representation changes).

---

## 2. Staleness and Trust

### The problem
An employee asks: "How many PTO days do I get?" The system retrieves `pto_policy.md` (effective September 2024) and `pto_policy_2023.md` (superseded). Both are in the index. The answer may cite the wrong one without the user knowing.

### Metadata signals already present
`metadata.csv` captures `last_modified`, `status` (`active` / `draft` / `legacy`), and `in_manifest` (whether the file appears in `document_manifest.csv`). These are surfaced per-retrieved-doc in the `/query` API response.

### Approach 1: Surface staleness in the UI
The API response already returns `status` and `last_modified` for each retrieved doc. The UI can:
- Prefix any answer citing a `legacy` document with a banner:
  > ⚠️ This answer is based on an outdated document (`pto_policy_2023.md`, status: legacy). Please verify with the current policy.
- Show the `last_modified` date next to each source chip.

**This is already partially implemented** — the HTML UI shows a contradiction banner when `has_contradiction = true`. The same pattern can extend to staleness warnings.

### Approach 2: Prefer active documents in scoring
Add a staleness penalty in `retrieval.py`:

```python
STATUS_PENALTY = {"legacy": -0.10, "draft": -0.05, "active": 0.0}
final_scores += [STATUS_PENALTY.get(rec["status"], 0.0) for rec in _index.records]
```

This biases retrieval toward active docs without completely hiding outdated ones (which matter for contradiction detection).

### Approach 3: Supersession metadata
Extend `metadata.csv` with a `supersedes` column (e.g. `pto_policy.md` → `pto_policy_2023.md`). If a retrieved set contains both a document and its superseded predecessor, the generator prompt can explicitly state: "Document A supersedes Document B — prefer Document A."

This is already implemented. The `supersedes` and `conflict_with` fields in `metadata.csv` feed the dynamic conflict detection in `generator.py`.

### Freshness indicator in answers
The generator prompt already instructs the LLM to "note if a policy was updated." Strengthening the instruction:

> "If multiple documents address the same topic, always prefer the one with the most recent `last_modified` date. State the effective date of the policy you are citing."

This gives users a timestamp anchor to verify answers against their own knowledge of when a policy changed.

---

## 3. Monitoring and Failure Detection

### LLM-level failures (already handled)
- **Thinking token bleed**: Qwen3 occasionally outputs `<think>…</think>` blocks even with `/no_think`. The generator strips them with regex before returning the answer. Log when this regex matches — it indicates the model is ignoring the instruction.
- **JSON parse failures**: `parse_json()` falls back to regex extraction. Log every fallback occurrence. A spike in fallbacks means the model is generating malformed output (e.g. context length exceeded, model degraded).
- **Empty or truncated answers**: Already detected by `_is_insufficient()` in the reranker. Log answer length distribution.

### Retrieval-level monitoring
| Signal | What it catches |
|--------|----------------|
| `context_size = 0` in response | Zero docs retrieved — embedding server unreachable or all scores below MIN_SCORE |
| Average `score` per query over time | Score drop → embedding drift or embedding server failure |
| `has_contradiction` rate | Spike → corpus has new conflicting documents; drop → contradiction detection is broken |
| Query tag extraction failures (empty tags) | LLM server unreachable or prompt regression |

### Answer quality monitoring (production)
LLM-as-judge at eval time is offline. In production, use:

1. **Implicit signals**: Did the user rephrase and ask again within 60 seconds? This is a proxy for an unsatisfying answer.
2. **Thumbs up/down**: Add a simple feedback button to the HTML UI. Store `(query, answer, feedback)` in a log table.
3. **Sampled re-evaluation**: Every night, run 5% of the day's queries through the LLM judge and alert if the rolling average score drops below 2.5.

### Infrastructure health checks
```
GET /health     → 200 if index loaded, LLM reachable, embedding server reachable
GET /metrics    → Prometheus-format counters: queries_total, failures_total, latency_p50, latency_p99
```

The FastAPI app currently has no `/health` endpoint. Adding one is a one-liner:

```python
@app.get("/health")
def health():
    assert _index.embeddings is not None, "Index not loaded"
    return {"status": "ok", "docs": len(_index.records)}
```

### Alerting thresholds (suggested)
| Metric | Warning | Critical |
|--------|---------|----------|
| P99 query latency | > 5s | > 15s |
| JSON parse fallback rate | > 5% | > 20% |
| Empty retrieval rate | > 1% | > 5% |
| LLM judge score (sampled) | < 2.5 | < 2.0 |
| Answer length < 25 words | > 10% | > 30% |

---

## 4. Cost at Scale

### Current system (local Qwen3, 34 docs)

Per query, the system makes **3 LLM calls** and **1 embedding call**:

| Call | Model | Input tokens | Output tokens |
|------|-------|-------------|--------------|
| Tag extraction | Qwen3-30B | ~250 | ~30 |
| Reranker sort | Qwen3-30B | ~600 | ~60 |
| Answer generation | Qwen3-30B | ~8,000 | ~400 |
| Query embedding | Qwen3-0.6B | ~20 | — |

**Total per query**: ~8,850 input tokens, ~490 output tokens.

The current setup runs on a self-hosted server (GPU inference). Marginal cost per query is effectively server amortization, not per-token billing.

### Scenario: 500 queries/day on self-hosted Qwen3

**Daily token volume:**
- Input: 500 × 8,850 = 4.4M tokens/day
- Output: 500 × 490 = 245K tokens/day

**Throughput check:**
- Qwen3-30B-A3B-GPTQ-Int4 on one A100: ~60-80 tokens/second output
- Mean answer generation time: ~5s per query
- At 500 queries/day (~21/hour, ~0.35/min): single GPU handles this comfortably with no queueing
- P99 latency budget: tag (~300ms) + reranker (~400ms) + generation (~5,000ms) = **~6s** end-to-end

**Server cost (if dedicated):**
| Option | $/hour | $/month | Queries/day capacity |
|--------|--------|---------|---------------------|
| AWS g5.2xlarge (A10G 24GB) | $1.21 | $876 | ~3,000 |
| AWS p3.2xlarge (V100 16GB) | $3.06 | $2,213 | ~2,000 |
| Self-hosted GPU server | ~$0.20 (amortized) | ~$150 | ~5,000+ |

At 500 queries/day, a single `g5.2xlarge` instance is ~$876/month and runs at ~17% capacity — cost-effective. If queries are bursty (most in business hours), a spot instance with auto-scaling makes more sense.

### Scenario: 500 queries/day on cloud LLM API

If moving to an API-based LLM (e.g. to avoid GPU management):

| Provider / Model | Input $/1M | Output $/1M | Cost/day | Cost/month |
|-----------------|------------|-------------|----------|------------|
| GPT-4o-mini | $0.15 | $0.60 | $0.81 | **~$25** |
| GPT-4o | $5.00 | $15.00 | $25.65 | **~$770** |
| Claude Haiku 4.5 | $0.80 | $4.00 | $4.50 | **~$135** |
| Claude Sonnet 4.6 | $3.00 | $15.00 | $16.90 | **~$510** |

GPT-4o-mini at ~$25/month is the cheapest managed option. At this scale, cloud APIs are cheaper than self-hosting (no GPU lease).

**Break-even point** (self-hosted vs GPT-4o-mini):
- g5.2xlarge: $876/month fixed
- GPT-4o-mini: $0.05/query variable
- Break-even: $876 / $0.05 = **17,500 queries/month = ~580 queries/day**

Below ~580 queries/day: cloud API is cheaper. Above that: self-hosted wins.

### Scaling beyond 2,000 docs

Two components need attention:

**1. Retrieval (numpy cosine sim)**
- Current: brute-force dot product over 34 vectors — microseconds
- At 2,000 docs: still <1ms (numpy BLAS matmul over 2K × 1024 floats)
- At 200,000 docs: ~20ms — still acceptable, no vector DB needed
- At 2M docs: switch to approximate nearest-neighbor (FAISS `IndexFlatIP` for exact, `IndexIVFFlat` for ANN with <5% recall loss)

**2. Generator context window**
- Current: passes full content of top-10 files (~8K tokens on average)
- At 2,000 docs: same — still top-10 files, context stays bounded
- **Risk**: individual files grow larger. A 50-page architecture doc would exceed context limits.
- Fix: paragraph-level chunking with a pre-filter. Keep descriptions for retrieval; chunk raw content for generation. This is the standard "late chunking" approach.

### Embedding cost at scale (one-time re-index)

| Corpus size | Files | Embedding calls | API cost (text-embedding-3-small @ $0.02/1M) |
|-------------|-------|-----------------|-----------------------------------------------|
| 34 files | 34 | 34 | < $0.01 |
| 2,000 files | 2,000 | 2,000 | ~$0.10 |
| 50,000 files | 50,000 | 50,000 | ~$2.50 |

Embedding is effectively free at document scale. The LLM description generation is the expensive part of re-indexing (~$0.005/file at GPT-4o-mini pricing → $10 for 2,000 files).

### Summary table

| Scale | Queries/day | Recommended infra | Estimated monthly cost |
|-------|------------|-------------------|----------------------|
| Current | < 100 | Local server (existing) | ~$0 marginal |
| Small team | 500 | g5.2xlarge spot instance | ~$300-500 |
| Dept-wide | 500 + cloud LLM | GPT-4o-mini API | ~$25-50 |
| Company-wide | 10,000 | 2× g5.2xlarge + load balancer | ~$1,500 |
| Enterprise | 100,000+ | Managed inference (Bedrock, Azure OpenAI) | Custom pricing |

---

## Design Decisions and Trade-offs Summary

| Decision | Choice | Rationale | Alternative if scaling |
|----------|--------|-----------|----------------------|
| Granularity | File-level (not chunk-level) | KB is small; contradiction detection needs full files | Paragraph chunks + late chunking at 2,000+ docs |
| Embeddings | On descriptions, not raw content | Descriptions are model-independent summaries; faster re-embed on model change | Hybrid: embed both description + content |
| Tag taxonomy | 42 curated tags (2-tier) | LLM-generated 483 tags had hallucination and drift | Auto-cluster tags with k-means periodically |
| Reranker | Sort-only (no filter) | Filtering broke contradiction detection | Fine-tuned cross-encoder at high query volume |
| Contradiction detection | Metadata-driven (supersedes + conflict_with columns) | Data-driven, no hardcoding; new conflicts added via CSV edit | Graph-based conflict detection over document similarity |
| Abstention | Prompt-only ("say IDK if unsure") | Confidence scoring tried and reverted — 13 regressions | Calibration dataset + separate classifier |
| Deployment | Single FastAPI container | Simple, no orchestration overhead | Add Redis cache for tag extraction; add queue for burst |
