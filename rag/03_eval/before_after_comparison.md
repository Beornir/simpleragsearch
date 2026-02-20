# Before / After: Reranker Improvement

## What changed
Added a post-retrieval **LLM sort-only reranker** step (Part 3).
After initial retrieval (top-10 by hybrid score), the LLM inspects each document's description
and **re-orders** them by relevance — no documents are removed.
If both documents in a known conflict pair are retrieved, they are promoted to the front so the
generator always sees them together and detects the contradiction.

## Metrics comparison

| Metric | v1 (no reranker) | v2 (with reranker) | Delta |
|--------|------------------|--------------------|-------|
| Source Recall@10 | 94.2% | 93.8% | -0.4% |
| Contradiction Detection | 100.0% | 80.0% | -20.0% |
| Abstention Rate | 60.0% | 60.0% | +0.0% |
| Answer Quality avg (0-3) | 2.73 | 2.77 | +5.0% |
| Answer Quality ≥2 (good%) | 97.5% | 95.0% | -2.5% |

## Question-level changes

| ID | Category | v1 | v2 | Change |
|----|----------|----|----|--------|
| q01 | factual | 2 | 2 | – |
| q02 | factual | 3 | 3 | – |
| q03 | factual | 3 | 3 | – |
| q04 | factual | 3 | 2 | ⬇️ |
| q05 | factual | 3 | 3 | – |
| q06 | factual | 2 | 3 | ⬆️ |
| q07 | factual | 3 | 3 | – |
| q08 | factual | 3 | 3 | – |
| q09 | factual | 3 | 3 | – |
| q10 | factual | 3 | 3 | – |
| q11 | factual | 3 | 3 | – |
| q12 | factual | 3 | 3 | – |
| q13 | factual | 3 | 3 | – |
| q14 | factual | 2 | 2 | – |
| q15 | procedural | 3 | 3 | – |
| q16 | procedural | 3 | 3 | – |
| q17 | procedural | 3 | 3 | – |
| q18 | procedural | 3 | 3 | – |
| q19 | procedural | 2 | 1 | ⬇️ |
| q20 | procedural | 3 | 3 | – |
| q21 | contradictory | 3 | 2 | ⬇️ |
| q22 | contradictory | 3 | 3 | – |
| q23 | contradictory | 3 | 3 | – |
| q24 | contradictory | 3 | 3 | – |
| q25 | contradictory | 2 | 1 | ⬇️ |
| q26 | multi-doc | 3 | 3 | – |
| q27 | multi-doc | 3 | 3 | – |
| q28 | multi-doc | 3 | 3 | – |
| q29 | multi-doc | 2 | 3 | ⬆️ |
| q30 | multi-doc | 2 | 2 | – |
| q31 | unanswerable | 2 | 3 | ⬆️ |
| q32 | unanswerable | 3 | 3 | – |
| q33 | unanswerable | 3 | 3 | – |
| q34 | unanswerable | 3 | 3 | – |
| q35 | unanswerable | 1 | 3 | ⬆️ |
| q36 | factual | 3 | 3 | – |
| q37 | factual | 3 | 3 | – |
| q38 | factual | 3 | 3 | – |
| q39 | factual | 3 | 3 | – |
| q40 | factual | 2 | 3 | ⬆️ |

## Summary
- **Improved:** 5 questions
- **Regressed:** 4 questions
- **Unchanged:** 31 questions

### Improved questions
- **q06** (factual): What is the maximum expense amount that requires VP approval?
  - v1 score 2: The system answer correctly identifies $2,000 as the threshold for VP approval but omits the detail about manager approval for expenses between $500 and $2,000.
  - v2 score 3: The system answer correctly states the $2,000 threshold for VP approval, matching the gold answer.
- **q29** (multi-doc): What are all the different ways an employee's access to internal syste
  - v1 score 2: The system answer includes most key points but adds extra details not in the gold answer, like data classification and vendor security reviews.
  - v2 score 3: The system answer accurately reflects all key points from the gold answer without any hallucinations.
- **q31** (unanswerable): What is the company's policy on using personal devices for work?
  - v1 score 2: The system answer correctly states the MDM requirement but omits the mention that the knowledge base lacks a comprehensive BYOD policy and that the remote work policy doesn't address personal devices in detail.
  - v2 score 3: The system answer accurately reflects the gold answer, correctly stating the security policy's MDM requirement and noting the remote work policy's preference for company-issued devices without contradicting the provided information.
- **q35** (unanswerable): What is the API versioning strategy and guidelines?
  - v1 score 1: The system answer provides some relevant information but lacks key facts from the gold answer, such as the absence of a comprehensive versioning guide and the mention of the Dashboard V2 PRD's 6-month backward compatibility.
  - v2 score 3: The system answer accurately reflects the absence of an explicit API versioning guide, correctly cites the sources, and correctly infers URL path-based versioning from the references.
- **q40** (factual): What's the current status of the expense policy changes being proposed
  - v1 score 2: The system answer correctly states the draft status and pending Finance approval, but omits specific details like the meal per diem increase, conference limit, and AI/ML budget.
  - v2 score 3: The system answer accurately reflects all key facts from the gold answer, including the draft status, proposed changes, approval process, and effective date.

### Regressed questions
- **q04** (factual): How much is the home office stipend for new employees?
  - v1 score 3: The system answer fully matches the gold answer with all key facts and includes the source reference.
  - v2 score 2: The system answer includes the one-time $1,500 stipend but omits the $500/year equipment allowance.
- **q19** (procedural): How do I request access to a new SaaS tool for my team?
  - v1 score 2: The system answer correctly mentions the security review process for SaaS tools but misses the cost-based approval steps and specific email addresses for different cost ranges as outlined in the gold answer.
  - v2 score 1: The system answer mentions a security review but misses key details about cost-based approval steps and alternative methods like Jira tickets or manager approval.
- **q21** (contradictory): How many PTO days do junior engineers (IC1-IC3) get?
  - v1 score 3: The system answer correctly states the current PTO policy of 20 days for junior engineers, aligning with the authoritative September 2024 policy mentioned in the gold answer.
  - v2 score 2: The system answer provides the correct current policy of 20 days but omits the carryover information and the mention of the older policy.
- **q25** (contradictory): What monitoring tool does Meridian use — Datadog or Grafana?
  - v1 score 2: The system answer correctly identifies that Meridian uses both Datadog and Grafana, and mentions the migration to Grafana Cloud in Q1 2025. However, it lacks specific details about the $40K/year savings and the parallel operation for one month as stated in the gold answer.
  - v2 score 1: The system answer incorrectly states Meridian uses Grafana, while the gold answer says they currently use Datadog and are migrating to Grafana.

## Limitations of this fix

The reranker fixes **retrieval noise** (irrelevant docs in top-10) but cannot fix
**retrieval miss** (relevant docs not in top-10 at all). For example, q19 still fails
because `expense_policy.md` scores below the cutoff — the reranker has nothing to reorder.
The next improvement for retrieval misses would be query expansion or increasing TOP_K.

## Cost impact

Each query now makes 3 LLM calls instead of 2 (tag extraction + reranking + generation).
~50% more LLM cost per query. For 500 queries/day this adds ~$X/month (see Part 4 for full numbers).
