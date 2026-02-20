"""
Evaluation harness — runs all 40 questions from eval/questions.jsonl
and computes metrics against gold answers.

Metrics:
  1. Source Recall@10     — did retrieved docs contain the gold_sources?
  2. Contradiction Rate   — for category=contradictory, was has_contradiction=True?
  3. Abstention Rate      — for category=unanswerable, did the system say IDK?
  4. Answer Quality       — LLM-as-judge score 0-3 vs gold_answer

Output: 03_eval/eval_results.json + 03_eval/eval_summary.md
"""

import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from openai import OpenAI

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE.parent))  # rag/ — for config
from config import LLM_BASE_URL, LLM_MODEL

# questions.jsonl lives in ml_takehome/eval/ next to the rag/ folder
_DEFAULT_EVAL = _HERE.parent.parent / "ml_takehome" / "eval" / "questions.jsonl"
EVAL_PATH    = Path(os.environ.get("EVAL_PATH", str(_DEFAULT_EVAL)))
API_URL      = os.environ.get("API_URL", "http://localhost:8000/query")
RESULTS_PATH = _HERE / "eval_results.json"
SUMMARY_PATH = _HERE / "eval_summary.md"

llm = OpenAI(base_url=LLM_BASE_URL, api_key="dummy")

IDK_PHRASES = [
    "don't have enough information",
    "not in the knowledge base",
    "cannot find",
    "no information",
    "not available",
    "not documented",
    "i don't know",
]


# ─── API call ────────────────────────────────────────────────────────────────

def call_api(question: str) -> dict:
    req = urllib.request.Request(
        API_URL,
        data=json.dumps({"question": question}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


# ─── Metrics ─────────────────────────────────────────────────────────────────

def source_recall(gold_sources: list[str], retrieved: list[dict]) -> float:
    """Fraction of gold_sources found in retrieved docs."""
    if not gold_sources:
        return 1.0  # unanswerable questions have no gold sources
    retrieved_paths = {doc["filepath"] for doc in retrieved}
    hits = sum(1 for gs in gold_sources if gs in retrieved_paths)
    return hits / len(gold_sources)


def is_idk(answer: str) -> bool:
    lower = answer.lower()
    return any(phrase in lower for phrase in IDK_PHRASES)


def llm_judge(question: str, gold_answer: str, system_answer: str) -> int:
    """Score 0-3: 0=wrong/hallucinated, 1=partial, 2=mostly correct, 3=fully correct."""
    prompt = f"""You are evaluating an AI assistant's answer against a gold reference answer.

Question: {question}

Gold answer: {gold_answer}

System answer: {system_answer}

Score the system answer on a scale of 0-3:
  3 = Fully correct — all key facts match, no hallucinations
  2 = Mostly correct — main point is right, minor details missing or slightly off
  1 = Partially correct — some relevant info but missing key facts or has errors
  0 = Wrong or hallucinated — incorrect facts, or refuses to answer when answer exists

Return JSON only: {{"score": <0-3>, "reason": "<one sentence>"}}"""

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
        return int(result.get("score", 0)), result.get("reason", "")
    except Exception as e:
        print(f"    [judge error] {e}")
        return -1, f"judge error: {e}"


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    questions = []
    with open(EVAL_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                questions.append(json.loads(line))

    print(f"Running eval on {len(questions)} questions...\n")

    results = []
    for i, q in enumerate(questions):
        qid = q["id"]
        question = q["question"]
        gold_answer = q["gold_answer"]
        gold_sources = q.get("gold_sources", [])
        category = q["category"]
        difficulty = q["difficulty"]

        print(f"[{i+1:02d}/{len(questions)}] {qid} ({category}/{difficulty}): {question[:60]}...")

        try:
            response = call_api(question)
        except Exception as e:
            print(f"  ERROR calling API: {e}")
            results.append({**q, "error": str(e)})
            continue

        answer = response["answer"]
        retrieved = response.get("retrieved", [])
        has_contradiction = response.get("has_contradiction", False)

        # Metric 1: source recall
        recall = source_recall(gold_sources, retrieved)

        # Metric 2: contradiction detection (for contradictory category)
        contradiction_correct = None
        if category == "contradictory":
            contradiction_correct = has_contradiction

        # Metric 3: abstention (for unanswerable category)
        abstention_correct = None
        if category == "unanswerable":
            abstention_correct = is_idk(answer)

        # Metric 4: LLM judge
        print(f"  → judging answer quality...", end=" ", flush=True)
        judge_score, judge_reason = llm_judge(question, gold_answer, answer)
        print(f"score={judge_score}")

        result = {
            "id": qid,
            "category": category,
            "difficulty": difficulty,
            "question": question,
            "gold_answer": gold_answer,
            "gold_sources": gold_sources,
            "system_answer": answer,
            "retrieved_paths": [doc["filepath"] for doc in retrieved],
            "has_contradiction": has_contradiction,
            "source_recall": recall,
            "contradiction_correct": contradiction_correct,
            "abstention_correct": abstention_correct,
            "judge_score": judge_score,
            "judge_reason": judge_reason,
        }
        results.append(result)
        time.sleep(0.2)

    # ─── Aggregate metrics ────────────────────────────────────────────────────

    valid = [r for r in results if "error" not in r]
    n = len(valid)

    avg_recall = sum(r["source_recall"] for r in valid) / n if n else 0

    contradictory = [r for r in valid if r["category"] == "contradictory"]
    contradiction_rate = (
        sum(1 for r in contradictory if r["contradiction_correct"]) / len(contradictory)
        if contradictory else None
    )

    unanswerable = [r for r in valid if r["category"] == "unanswerable"]
    abstention_rate = (
        sum(1 for r in unanswerable if r["abstention_correct"]) / len(unanswerable)
        if unanswerable else None
    )

    judged = [r for r in valid if r["judge_score"] >= 0]
    avg_judge = sum(r["judge_score"] for r in judged) / len(judged) if judged else 0

    # Per-category breakdown
    categories = sorted(set(r["category"] for r in valid))
    cat_stats = {}
    for cat in categories:
        cat_rows = [r for r in valid if r["category"] == cat]
        cat_stats[cat] = {
            "n": len(cat_rows),
            "avg_recall": round(sum(r["source_recall"] for r in cat_rows) / len(cat_rows), 3),
            "avg_judge":  round(sum(r["judge_score"] for r in cat_rows if r["judge_score"] >= 0) /
                                max(1, sum(1 for r in cat_rows if r["judge_score"] >= 0)), 3),
        }

    # Failures (judge_score < 2)
    failures = [r for r in valid if r["judge_score"] < 2]

    summary = {
        "total_questions": len(questions),
        "evaluated": n,
        "errors": len(questions) - n,
        "metrics": {
            "source_recall_avg": round(avg_recall, 3),
            "contradiction_detection_rate": round(contradiction_rate, 3) if contradiction_rate is not None else None,
            "abstention_rate": round(abstention_rate, 3) if abstention_rate is not None else None,
            "answer_quality_avg_0_3": round(avg_judge, 3),
            "answer_quality_pct_good": round(
                sum(1 for r in judged if r["judge_score"] >= 2) / len(judged) * 100, 1
            ) if judged else 0,
        },
        "per_category": cat_stats,
        "failure_count": len(failures),
    }

    output = {"summary": summary, "results": results}
    RESULTS_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False))

    # ─── Markdown summary ────────────────────────────────────────────────────
    md = _build_markdown(summary, failures, valid)
    SUMMARY_PATH.write_text(md)

    print("\n" + "=" * 60)
    print("EVAL SUMMARY")
    print("=" * 60)
    print(f"  Source Recall@10:           {summary['metrics']['source_recall_avg']:.1%}")
    print(f"  Contradiction Detection:    {(contradiction_rate or 0):.1%}  ({len(contradictory)} questions)")
    print(f"  Abstention Rate:            {(abstention_rate or 0):.1%}  ({len(unanswerable)} questions)")
    print(f"  Answer Quality (avg 0-3):   {avg_judge:.2f}")
    print(f"  Answer Quality (>=2 = good):{summary['metrics']['answer_quality_pct_good']}%")
    print(f"\n  Results → {RESULTS_PATH}")
    print(f"  Summary → {SUMMARY_PATH}")


def _build_markdown(summary: dict, failures: list, all_results: list) -> str:
    m = summary["metrics"]
    lines = [
        "# Eval Results\n",
        f"**Total questions:** {summary['total_questions']}  ",
        f"**Evaluated:** {summary['evaluated']}  ",
        f"**Errors:** {summary['errors']}\n",
        "## Metrics\n",
        "| Metric | Value | Notes |",
        "|--------|-------|-------|",
        f"| Source Recall@10 | {m['source_recall_avg']:.1%} | Did retrieved docs contain gold_sources? |",
        f"| Contradiction Detection | {(m['contradiction_detection_rate'] or 0):.1%} | For category=contradictory |",
        f"| Abstention Rate | {(m['abstention_rate'] or 0):.1%} | For category=unanswerable |",
        f"| Answer Quality avg (0-3) | {m['answer_quality_avg_0_3']:.2f} | LLM-as-judge |",
        f"| Answer Quality ≥2 (good) | {m['answer_quality_pct_good']}% | Fraction of 'mostly correct' answers |\n",
        "## Per Category\n",
        "| Category | N | Recall | Quality |",
        "|----------|---|--------|---------|",
    ]
    for cat, s in summary["per_category"].items():
        lines.append(f"| {cat} | {s['n']} | {s['avg_recall']:.1%} | {s['avg_judge']:.2f} |")

    lines += ["\n## Failures (judge_score < 2)\n"]
    if failures:
        for r in failures:
            lines.append(f"### {r['id']} — {r['category']}/{r['difficulty']}")
            lines.append(f"**Q:** {r['question']}")
            lines.append(f"**Gold:** {r['gold_answer'][:200]}")
            lines.append(f"**System:** {r['system_answer'][:200]}")
            lines.append(f"**Score:** {r['judge_score']} — {r['judge_reason']}")
            lines.append(f"**Recall:** {r['source_recall']:.0%} | Retrieved: {r['retrieved_paths'][:3]}\n")
    else:
        lines.append("No failures!")

    return "\n".join(lines)


if __name__ == "__main__":
    main()
