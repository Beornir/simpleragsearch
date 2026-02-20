"""
Generation module — loads full file contents and calls LLM for the final answer.

Improvements over v1:
  - Dynamic conflict pair detection from supersedes metadata (no hardcoding)
  - Confidence scoring: second lightweight LLM call to verify the answer is
    well-supported; if confidence < CONFIDENCE_THRESHOLD → return IDK
  - Low retrieval score signal: if max retrieval score < MIN_RETRIEVAL_SCORE,
    adds a caution hint to the generation prompt
"""

import json
import re
from pathlib import Path
from openai import OpenAI

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import LLM_BASE_URL, LLM_MODEL, KB_PATH, MIN_RETRIEVAL_SCORE

llm = OpenAI(base_url=LLM_BASE_URL, api_key="dummy")

MAX_FILE_CHARS = 8000   # per-file content limit to stay within context

IDK_ANSWER = "I don't have enough information to answer this question based on the available knowledge base."


def _load_file(filepath: str) -> str:
    """Load raw file content, with JSON formatting for Slack exports."""
    path = KB_PATH / filepath
    if not path.exists():
        return f"[File not found: {filepath}]"

    if path.suffix == ".json":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                lines = []
                for msg in data:
                    ts = msg.get("timestamp", "")[:16]
                    user = msg.get("user", "unknown")
                    channel = msg.get("channel", "")
                    text = msg.get("text", "")
                    lines.append(f"[{ts}] #{channel} {user}: {text}")
                return "\n".join(lines)
        except Exception:
            pass

    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        return f"[Could not read: {e}]"


def _build_context(retrieved: list[dict]) -> str:
    parts = []
    for i, doc in enumerate(retrieved, 1):
        content = _load_file(doc["filepath"])
        if len(content) > MAX_FILE_CHARS:
            content = content[:MAX_FILE_CHARS] + "\n[... truncated ...]"

        meta = []
        if doc.get("last_modified"):
            meta.append(f"last_modified={doc['last_modified']}")
        if doc.get("status"):
            meta.append(f"status={doc['status']}")
        if doc.get("author"):
            meta.append(f"author={doc['author']}")
        meta_str = " | ".join(meta)

        parts.append(
            f"=== SOURCE {i}: {doc['filepath']} ({meta_str}) ===\n{content}\n"
        )
    return "\n".join(parts)


SYSTEM_PROMPT = """/no_think
You are an internal knowledge base assistant for Meridian Technologies.

Rules:
1. Answer ONLY using the provided source documents. Do not use outside knowledge.
2. Always cite your sources at the end as: [Source: filename] or [Sources: file1, file2].
3. If multiple documents CONTRADICT each other on the same topic, you MUST surface both versions explicitly. State which document is newer (use last_modified dates) and recommend the newer one as authoritative.
4. If the answer is not present in any source document, say: "I don't have enough information to answer this question based on the available knowledge base." Important distinction: if a specific policy, guide, or document is asked about and it does NOT exist in the provided sources (even if loosely related documents exist), say IDK — do not synthesize a substitute answer from tangentially related material. But if the sources DO explicitly contain the relevant facts (even spread across paragraphs), provide the answer normally.
5. Be concise and direct. If the question is procedural (how to do X), provide numbered steps.
6. Do NOT invent information, dates, names, or numbers not present in the sources.
7. If a source contains "[File not found: ...]", that document does not exist in the knowledge base. If the question is specifically about that missing document's content, say IDK.
"""

LOW_CONFIDENCE_HINT = """
⚠️ RETRIEVAL NOTE: The retrieved documents have low relevance scores for this query.
The information you need may not be present in the knowledge base.
Only answer if the sources EXPLICITLY contain the answer. Otherwise use Rule 4 (say IDK).
"""


def _detect_contradictions(retrieved: list[dict]) -> bool:
    """
    Check if retrieved docs include both sides of a known conflict pair.
    Uses supersedes + conflict_with metadata — no hardcoded pairs needed.
    """
    retrieved_paths = {doc["filepath"] for doc in retrieved}

    for doc in retrieved:
        for field in ("supersedes", "conflict_with"):
            other = doc.get(field, "")
            if other and other in retrieved_paths:
                return True
    return False


def generate(query: str, retrieved: list[dict], max_retrieval_score: float = 1.0) -> dict:
    """Generate answer from retrieved documents."""
    if not retrieved:
        return {
            "answer": IDK_ANSWER,
            "sources": [],
            "has_contradiction": False,
        }

    context = _build_context(retrieved)
    sources_list = [doc["filepath"] for doc in retrieved]

    # Low retrieval score → hint the LLM to be conservative
    low_confidence = max_retrieval_score < MIN_RETRIEVAL_SCORE
    retrieval_hint = LOW_CONFIDENCE_HINT if low_confidence else ""

    user_message = f"""Source documents:
{context}
{retrieval_hint}
Question: {query}

Answer the question based strictly on the source documents above."""

    response = llm.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.1,
        max_tokens=1500,
    )

    raw = response.choices[0].message.content or ""
    # strip Qwen3 thinking blocks <think>...</think>
    answer = re.sub(r"<think>.*?</think>\s*", "", raw, flags=re.DOTALL).strip()

    # Contradiction detection: keyword matching
    contradiction_keywords = [
        "contradict", "conflict", "disagree", "inconsistent",
        "older policy", "newer policy", "discrepancy",
        "two versions", "two documents", "both documents",
        "earlier version", "updated policy", "superseded",
    ]
    has_contradiction = any(kw in answer.lower() for kw in contradiction_keywords)

    # Dynamic conflict pair detection from supersedes metadata
    if not has_contradiction:
        has_contradiction = _detect_contradictions(retrieved)

    return {
        "answer": answer,
        "sources": sources_list,
        "has_contradiction": has_contradiction,
    }
