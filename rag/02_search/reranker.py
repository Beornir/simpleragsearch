"""
Sort-only reranker with conflict-pair promotion.

Flow:
  1. Sort retrieved docs by relevance (LLM looks at descriptions)
  2. If both docs in a conflict pair are retrieved → promote both to front
     (ensures LLM sees contradicting docs first and always detects the conflict)
  3. Pass ALL sorted docs to generator (no filtering — needed for contradiction detection)

Why not filter/stop early:
  - Contradiction detection requires BOTH conflicting docs in context.
  - Abstention is better served by the generator seeing all (lack of) evidence.
"""

import json
from pathlib import Path
from openai import OpenAI

import sys
_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE.parent))  # rag/ — for config
sys.path.insert(0, str(_HERE))         # 02_search/ — for generator, retrieval
from config import LLM_BASE_URL, LLM_MODEL
from generator import generate, SYSTEM_PROMPT
from retrieval import get_conflict_pairs

llm = OpenAI(base_url=LLM_BASE_URL, api_key="dummy")


def sort_by_relevance(query: str, retrieved: list[dict]) -> list[dict]:
    """
    Ask LLM to sort retrieved docs by relevance to query.
    Returns same list in relevance order (no filtering — just reordering).
    """
    if len(retrieved) <= 1:
        return retrieved

    candidates = "\n".join(
        f"{i}: [{doc['filepath']}] {doc['description'][:120]}"
        for i, doc in enumerate(retrieved)
    )

    prompt = f"""Sort these documents by relevance to the user question.
Return ALL indices, most relevant first.

Question: {query}

Documents:
{candidates}

Return JSON: {{"order": [most_relevant_idx, ..., least_relevant_idx]}}"""

    try:
        response = llm.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "/no_think"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=150,
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)
        order = result.get("order", [])
        valid = [i for i in order if isinstance(i, int) and 0 <= i < len(retrieved)]

        # Add any missing indices at the end
        missing = [i for i in range(len(retrieved)) if i not in valid]
        full_order = valid + missing

        return [retrieved[i] for i in full_order]

    except Exception as e:
        print(f"[Reranker sort warning] {e}")
        return retrieved


def _promote_conflict_pairs(sorted_docs: list[dict]) -> list[dict]:
    """
    If both documents in a known conflict pair are retrieved, move both to the
    front of the list so the generator always sees them together near the top.
    This prevents the reranker from accidentally separating conflicting docs
    and causing the LLM to miss the contradiction.
    """
    conflict_pairs = get_conflict_pairs()
    if not conflict_pairs:
        return sorted_docs

    retrieved_paths = {doc["filepath"] for doc in sorted_docs}
    to_promote: set[str] = set()

    for pair in conflict_pairs:
        if pair.issubset(retrieved_paths):
            to_promote.update(pair)

    if not to_promote:
        return sorted_docs

    front = [d for d in sorted_docs if d["filepath"] in to_promote]
    rest  = [d for d in sorted_docs if d["filepath"] not in to_promote]
    return front + rest


def iterative_rerank_and_generate(query: str, retrieved: list[dict]) -> dict:
    """
    Sort docs by relevance, promote conflict pairs to front, then pass ALL
    sorted docs to generator.
    """
    if not retrieved:
        return {
            "answer": "I don't have enough information to answer this question based on the available knowledge base.",
            "sources": [],
            "has_contradiction": False,
            "context_size": 0,
        }

    sorted_docs = sort_by_relevance(query, retrieved)
    sorted_docs = _promote_conflict_pairs(sorted_docs)

    max_score = max(doc["score"] for doc in sorted_docs) if sorted_docs else 0.0
    result = generate(query, sorted_docs, max_retrieval_score=max_score)
    result["context_size"] = len(sorted_docs)
    result["sorted_sources"] = [d["filepath"] for d in sorted_docs]
    return result
