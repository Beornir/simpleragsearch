"""
Retrieval module — hybrid tag + vector + BM25 search over description embeddings.

Scoring per file:
  final_score = VECTOR_WEIGHT * cosine_sim(query, description)
              + TAG_WEIGHT    * overlap(query_tags, file_tags)
              + BM25_WEIGHT   * bm25_normalized(query, description)
"""

import json
import csv
import math
import numpy as np
from collections import Counter
from pathlib import Path
from openai import OpenAI

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    LLM_BASE_URL, LLM_MODEL,
    EMBED_BASE_URL, EMBED_MODEL,
    METADATA_CSV, MASTER_TAGS_JSON,
    TOP_K, VECTOR_WEIGHT, TAG_WEIGHT, BM25_WEIGHT, MIN_SCORE,
)

llm = OpenAI(base_url=LLM_BASE_URL, api_key="dummy")
embedder = OpenAI(base_url=EMBED_BASE_URL, api_key="dummy")


# ─── BM25 ─────────────────────────────────────────────────────────────────────

class BM25:
    """Simple BM25 scorer over a fixed corpus of texts."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._corpus: list[list[str]] = []
        self._idf: dict[str, float] = {}
        self._avgdl: float = 1.0

    def _tokenize(self, text: str) -> list[str]:
        return text.lower().split()

    def fit(self, texts: list[str]) -> None:
        self._corpus = [self._tokenize(t) for t in texts]
        N = len(self._corpus)
        self._avgdl = sum(len(d) for d in self._corpus) / N if N else 1.0

        df: dict[str, int] = {}
        for doc in self._corpus:
            for term in set(doc):
                df[term] = df.get(term, 0) + 1

        self._idf = {
            term: math.log((N - freq + 0.5) / (freq + 0.5) + 1)
            for term, freq in df.items()
        }

    def scores(self, query: str) -> np.ndarray:
        tokens = self._tokenize(query)
        out = np.zeros(len(self._corpus), dtype=np.float32)
        for i, doc in enumerate(self._corpus):
            dl = len(doc)
            tf = Counter(doc)
            for term in tokens:
                if term not in self._idf:
                    continue
                f = tf.get(term, 0)
                num = self._idf[term] * f * (self.k1 + 1)
                den = f + self.k1 * (1 - self.b + self.b * dl / self._avgdl)
                out[i] += num / den
        return out


# ─── Index (loaded once at startup) ──────────────────────────────────────────

class Index:
    def __init__(self):
        self.records: list[dict] = []
        self.embeddings: np.ndarray | None = None
        self.master_tags: list[str] = []
        self.bm25: BM25 = BM25()
        # list of frozensets — each pair of conflicting file paths
        self.conflict_pairs: list[frozenset] = []

    def load(self):
        with open(MASTER_TAGS_JSON, encoding="utf-8") as f:
            raw = json.load(f)
        self.master_tags = sorted(set(raw.values()))

        rows = []
        vectors = []
        descriptions = []
        with open(METADATA_CSV, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                emb = json.loads(row["embedding"]) if row["embedding"] else []
                if not emb:
                    emb = [0.0] * 1024
                rows.append({
                    "filepath":      row["filepath"],
                    "filename":      row["filename"],
                    "description":   row["description"],
                    "tags":          set(row["tags"].split("|")) if row["tags"] else set(),
                    "last_modified": row["last_modified"],
                    "status":        row["status"],
                    "department":    row["department"],
                    "author":        row["author"],
                    "in_manifest":   row["in_manifest"],
                    "supersedes":    row.get("supersedes", ""),
                    "conflict_with": row.get("conflict_with", ""),
                })
                vectors.append(emb)
                descriptions.append(row["description"])

        self.records = rows
        mat = np.array(vectors, dtype=np.float32)
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self.embeddings = mat / norms  # pre-normalize for fast cosine sim

        # BM25 index over descriptions
        self.bm25.fit(descriptions)

        # Build conflict pairs from supersedes + conflict_with metadata
        seen: set[frozenset] = set()
        self.conflict_pairs = []
        for rec in self.records:
            for field in ("supersedes", "conflict_with"):
                other = rec.get(field, "")
                if other:
                    pair = frozenset([rec["filepath"], other])
                    if pair not in seen:
                        seen.add(pair)
                        self.conflict_pairs.append(pair)

        print(
            f"[Index] Loaded {len(self.records)} documents, "
            f"{len(self.master_tags)} canonical tags, "
            f"{len(self.conflict_pairs)} conflict pairs"
        )


_index = Index()


def load_index():
    _index.load()


# ─── Tag extraction ───────────────────────────────────────────────────────────

def extract_tags_from_query(query: str) -> set[str]:
    """Ask LLM to pick relevant tags from master_tags for the given query."""
    tags_str = ", ".join(_index.master_tags)
    prompt = f"""Select tags for this query. You MUST only use tags from the EXACT list below — no other tags allowed.

ALLOWED TAGS (use ONLY these exact strings):
{tags_str}

User query: {query}

Pick 2-6 tags that best match the query topic. Return ONLY tags from the list above.
Return JSON: {{"tags": ["tag1", "tag2", ...]}}"""

    try:
        response = llm.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "/no_think"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=200,
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)
        raw = result.get("tags", [])
        # Strict validation — only keep tags that exist in master_tags
        valid = set(t for t in raw if t in _index.master_tags)
        return valid
    except Exception as e:
        print(f"[Warning] Tag extraction failed: {e}")
        return set()


# ─── Scoring ──────────────────────────────────────────────────────────────────

def _cosine_scores(query_vec: np.ndarray) -> np.ndarray:
    """Dot product of normalized query against normalized doc embeddings → cosine sims."""
    q = query_vec / (np.linalg.norm(query_vec) + 1e-9)
    scores = _index.embeddings @ q          # shape: (N,)
    return (scores + 1.0) / 2.0            # rescale [-1,1] → [0,1]


def _tag_scores(query_tags: set[str]) -> np.ndarray:
    """Overlap coefficient: |intersection| / |query_tags| for each document."""
    if not query_tags:
        return np.zeros(len(_index.records), dtype=np.float32)
    scores = np.array([
        len(query_tags & rec["tags"]) / len(query_tags)
        for rec in _index.records
    ], dtype=np.float32)
    return scores


def _bm25_scores(query: str) -> np.ndarray:
    """BM25 scores over descriptions, normalized to [0, 1]."""
    raw = _index.bm25.scores(query)
    max_val = raw.max()
    if max_val == 0:
        return raw
    return raw / max_val


def embed_query(query: str) -> np.ndarray:
    response = embedder.embeddings.create(model=EMBED_MODEL, input=query)
    return np.array(response.data[0].embedding, dtype=np.float32)


def _generate_paraphrases(query: str, n: int = 3) -> list[str]:
    """
    Ask LLM to generate n paraphrases of the query.
    Named entities (numbers, product names, system names) are preserved exactly.
    """
    prompt = f"""Generate {n} paraphrases of the question below.
Rules:
- Keep ALL named entities exactly as written: numbers, product names, system names, people's names, tool names.
- Only rephrase the surrounding words and sentence structure.
- Each paraphrase must ask the same question in a different way.

Question: {query}

Return JSON: {{"paraphrases": ["...", "...", "..."]}}"""

    try:
        response = llm.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "/no_think"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=300,
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)
        paraphrases = result.get("paraphrases", [])
        # Keep only non-empty strings, up to n
        return [p for p in paraphrases if isinstance(p, str) and p.strip()][:n]
    except Exception as e:
        print(f"[Warning] Paraphrase generation failed: {e}")
        return []


def _embed_augmented(query: str, paraphrases: list[str]) -> np.ndarray:
    """
    Embed query + paraphrases and return a weighted average vector.
    Weight: 0.5 for original query, 0.5 split equally across paraphrases.
    If no paraphrases, returns the original embedding.
    """
    texts = [query] + paraphrases
    response = embedder.embeddings.create(model=EMBED_MODEL, input=texts)
    vecs = [np.array(d.embedding, dtype=np.float32) for d in response.data]

    if len(vecs) == 1:
        return vecs[0]

    n_para = len(vecs) - 1
    orig_weight = 0.5
    para_weight = 0.5 / n_para

    avg = orig_weight * vecs[0] + sum(para_weight * v for v in vecs[1:])
    return avg


def retrieve(query: str) -> list[dict]:
    """Return top-K documents with scores."""
    query_vec = embed_query(query)
    query_tags = extract_tags_from_query(query)

    vec_scores  = _cosine_scores(query_vec)
    tag_scores  = _tag_scores(query_tags)
    bm25_scores = _bm25_scores(query)

    final_scores = (
        VECTOR_WEIGHT * vec_scores
        + TAG_WEIGHT  * tag_scores
        + BM25_WEIGHT * bm25_scores
    )

    top_indices = np.argsort(final_scores)[::-1][:TOP_K]

    results = []
    for idx in top_indices:
        score = float(final_scores[idx])
        if score < MIN_SCORE:
            break
        rec = _index.records[idx]
        results.append({
            **rec,
            "tags": list(rec["tags"]),
            "score":       round(score, 4),
            "vec_score":   round(float(vec_scores[idx]), 4),
            "tag_score":   round(float(tag_scores[idx]), 4),
            "bm25_score":  round(float(bm25_scores[idx]), 4),
            "query_tags":  list(query_tags),
        })

    return results


def get_conflict_pairs() -> list[frozenset]:
    """Return conflict pairs derived from supersedes metadata."""
    return _index.conflict_pairs
