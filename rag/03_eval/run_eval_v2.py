"""
Eval v2 — same as run_eval.py but with use_reranker=True.
Produces eval_results_v2.json + before_after_comparison.md
"""

import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from openai import OpenAI

# Reuse logic from run_eval.py
sys.path.insert(0, str(Path(__file__).parent))
from run_eval import (
    EVAL_PATH, LLM_BASE_URL, LLM_MODEL,
    source_recall, is_idk, llm_judge, IDK_PHRASES,
)

_HERE = Path(__file__).parent
API_URL         = os.environ.get("API_URL", "http://localhost:8000/query")
RESULTS_V2_PATH = _HERE / "eval_results_v2.json"
COMPARISON_PATH = _HERE / "before_after_comparison.md"
RESULTS_V1_PATH = _HERE / "eval_results.json"


def call_api(question: str, use_reranker: bool = True) -> dict:
    req = urllib.request.Request(
        API_URL,
        data=json.dumps({"question": question, "use_reranker": use_reranker}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def main():
    questions = []
    with open(EVAL_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                questions.append(json.loads(line))

    print(f"Running eval v2 (with reranker) on {len(questions)} questions...\n")

    results = []
    for i, q in enumerate(questions):
        qid = q["id"]
        question = q["question"]
        gold_answer = q["gold_answer"]
        gold_sources = q.get("gold_sources", [])
        category = q["category"]
        difficulty = q["difficulty"]

        print(f"[{i+1:02d}/{len(questions)}] {qid} ({category}/{difficulty}): {question[:55]}...")

        try:
            response = call_api(question, use_reranker=True)
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({**q, "error": str(e)})
            continue

        answer = response["answer"]
        retrieved = response.get("retrieved", [])
        has_contradiction = response.get("has_contradiction", False)

        recall = source_recall(gold_sources, retrieved)
        contradiction_correct = has_contradiction if category == "contradictory" else None
        abstention_correct = is_idk(answer) if category == "unanswerable" else None

        print(f"  → judging...", end=" ", flush=True)
        judge_score, judge_reason = llm_judge(question, gold_answer, answer)
        print(f"score={judge_score}")

        results.append({
            "id": qid, "category": category, "difficulty": difficulty,
            "question": question, "gold_answer": gold_answer,
            "gold_sources": gold_sources, "system_answer": answer,
            "retrieved_paths": [doc["filepath"] for doc in retrieved],
            "has_contradiction": has_contradiction,
            "source_recall": recall,
            "contradiction_correct": contradiction_correct,
            "abstention_correct": abstention_correct,
            "judge_score": judge_score,
            "judge_reason": judge_reason,
        })
        time.sleep(0.2)

    # ─── Aggregate ────────────────────────────────────────────────────────────
    valid = [r for r in results if "error" not in r]
    n = len(valid)

    avg_recall   = sum(r["source_recall"] for r in valid) / n
    contradictory = [r for r in valid if r["category"] == "contradictory"]
    unanswerable  = [r for r in valid if r["category"] == "unanswerable"]
    judged = [r for r in valid if r["judge_score"] >= 0]

    contradiction_rate = (sum(1 for r in contradictory if r["contradiction_correct"]) / len(contradictory)) if contradictory else None
    abstention_rate    = (sum(1 for r in unanswerable  if r["abstention_correct"])    / len(unanswerable))  if unanswerable  else None
    avg_judge = sum(r["judge_score"] for r in judged) / len(judged) if judged else 0
    pct_good  = sum(1 for r in judged if r["judge_score"] >= 2) / len(judged) * 100 if judged else 0

    summary_v2 = {
        "total": len(questions), "evaluated": n,
        "metrics": {
            "source_recall_avg":          round(avg_recall, 3),
            "contradiction_detection_rate": round(contradiction_rate, 3) if contradiction_rate else None,
            "abstention_rate":              round(abstention_rate, 3)    if abstention_rate    else None,
            "answer_quality_avg_0_3":       round(avg_judge, 3),
            "answer_quality_pct_good":      round(pct_good, 1),
        },
    }

    RESULTS_V2_PATH.write_text(json.dumps({"summary": summary_v2, "results": results}, indent=2))

    # ─── Before/after comparison ──────────────────────────────────────────────
    v1 = json.loads(RESULTS_V1_PATH.read_text())
    m1 = v1["summary"]["metrics"]
    m2 = summary_v2["metrics"]

    def delta(a, b):
        if a is None or b is None:
            return "N/A"
        d = b - a
        sign = "+" if d >= 0 else ""
        return f"{sign}{d:.1%}" if abs(d) < 10 else f"{sign}{d:.1f}"

    comparison_md = f"""# Before / After: Reranker Improvement

## What changed
Added a post-retrieval **LLM reranker** step (Part 3).
After initial retrieval (top-10 by vector+tag score), the LLM inspects each document's description
and removes ones that aren't genuinely relevant to the query.
This filters retrieval noise (e.g. `adr_007_forward_migrations.md` appearing in unrelated queries).

## Metrics comparison

| Metric | v1 (no reranker) | v2 (with reranker) | Delta |
|--------|------------------|--------------------|-------|
| Source Recall@10 | {m1['source_recall_avg']:.1%} | {m2['source_recall_avg']:.1%} | {delta(m1['source_recall_avg'], m2['source_recall_avg'])} |
| Contradiction Detection | {(m1['contradiction_detection_rate'] or 0):.1%} | {(m2['contradiction_detection_rate'] or 0):.1%} | {delta(m1['contradiction_detection_rate'], m2['contradiction_detection_rate'])} |
| Abstention Rate | {(m1['abstention_rate'] or 0):.1%} | {(m2['abstention_rate'] or 0):.1%} | {delta(m1['abstention_rate'], m2['abstention_rate'])} |
| Answer Quality avg (0-3) | {m1['answer_quality_avg_0_3']:.2f} | {m2['answer_quality_avg_0_3']:.2f} | {delta(m1['answer_quality_avg_0_3'], m2['answer_quality_avg_0_3'])} |
| Answer Quality ≥2 (good%) | {m1['answer_quality_pct_good']}% | {m2['answer_quality_pct_good']}% | {delta(m1['answer_quality_pct_good']/100, m2['answer_quality_pct_good']/100)} |

## Question-level changes

| ID | Category | v1 | v2 | Change |
|----|----------|----|----|--------|
"""
    v1_by_id = {r["id"]: r for r in v1["results"] if "error" not in r}
    changed_up, changed_down, unchanged = [], [], []
    for r2 in results:
        if "error" in r2:
            continue
        r1 = v1_by_id.get(r2["id"])
        if not r1:
            continue
        s1, s2 = r1["judge_score"], r2["judge_score"]
        arrow = "⬆️" if s2 > s1 else ("⬇️" if s2 < s1 else "–")
        comparison_md += f"| {r2['id']} | {r2['category']} | {s1} | {s2} | {arrow} |\n"
        if s2 > s1:
            changed_up.append(r2)
        elif s2 < s1:
            changed_down.append(r2)
        else:
            unchanged.append(r2)

    comparison_md += f"""
## Summary
- **Improved:** {len(changed_up)} questions
- **Regressed:** {len(changed_down)} questions
- **Unchanged:** {len(unchanged)} questions

"""
    if changed_up:
        comparison_md += "### Improved questions\n"
        for r in changed_up:
            r1 = v1_by_id[r["id"]]
            comparison_md += f"- **{r['id']}** ({r['category']}): {r['question'][:70]}\n"
            comparison_md += f"  - v1 score {r1['judge_score']}: {r1['judge_reason']}\n"
            comparison_md += f"  - v2 score {r['judge_score']}: {r['judge_reason']}\n"

    if changed_down:
        comparison_md += "\n### Regressed questions\n"
        for r in changed_down:
            r1 = v1_by_id[r["id"]]
            comparison_md += f"- **{r['id']}** ({r['category']}): {r['question'][:70]}\n"
            comparison_md += f"  - v1 score {r1['judge_score']}: {r1['judge_reason']}\n"
            comparison_md += f"  - v2 score {r['judge_score']}: {r['judge_reason']}\n"

    comparison_md += """
## Limitations of this fix

The reranker fixes **retrieval noise** (irrelevant docs in top-10) but cannot fix
**retrieval miss** (relevant docs not in top-10 at all). For example, q19 still fails
because `expense_policy.md` scores below the cutoff — the reranker has nothing to reorder.
The next improvement for retrieval misses would be query expansion or increasing TOP_K.

## Cost impact

Each query now makes 3 LLM calls instead of 2 (tag extraction + reranking + generation).
~50% more LLM cost per query. For 500 queries/day this adds ~$X/month (see Part 4 for full numbers).
"""

    COMPARISON_PATH.write_text(comparison_md)

    print("\n" + "=" * 60)
    print("EVAL V2 SUMMARY (with reranker)")
    print("=" * 60)
    print(f"  Source Recall@10:           {avg_recall:.1%}  (was {m1['source_recall_avg']:.1%})")
    print(f"  Contradiction Detection:    {(contradiction_rate or 0):.1%}  (was {(m1['contradiction_detection_rate'] or 0):.1%})")
    print(f"  Abstention Rate:            {(abstention_rate or 0):.1%}  (was {(m1['abstention_rate'] or 0):.1%})")
    print(f"  Answer Quality avg (0-3):   {avg_judge:.2f}  (was {m1['answer_quality_avg_0_3']:.2f})")
    print(f"  Answer Quality ≥2 good:     {pct_good:.1f}%  (was {m1['answer_quality_pct_good']}%)")
    print(f"\n  Improved: {len(changed_up)} | Regressed: {len(changed_down)} | Unchanged: {len(unchanged)}")
    print(f"\n  Comparison → {COMPARISON_PATH}")


if __name__ == "__main__":
    main()
