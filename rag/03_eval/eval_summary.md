# Eval Results

**Total questions:** 40  
**Evaluated:** 40  
**Errors:** 0

## Metrics

| Metric | Value | Notes |
|--------|-------|-------|
| Source Recall@10 | 94.2% | Did retrieved docs contain gold_sources? |
| Contradiction Detection | 100.0% | For category=contradictory |
| Abstention Rate | 60.0% | For category=unanswerable |
| Answer Quality avg (0-3) | 2.73 | LLM-as-judge |
| Answer Quality ≥2 (good) | 97.5% | Fraction of 'mostly correct' answers |

## Per Category

| Category | N | Recall | Quality |
|----------|---|--------|---------|
| contradictory | 5 | 93.3% | 2.80 |
| factual | 19 | 100.0% | 2.79 |
| multi-doc | 5 | 70.0% | 2.60 |
| procedural | 6 | 91.7% | 2.83 |
| unanswerable | 5 | 100.0% | 2.40 |

## Failures (judge_score < 2)

### q35 — unanswerable/hard
**Q:** What is the API versioning strategy and guidelines?
**Gold:** While an 'API Versioning Guide' is listed in the document manifest (authored by Mike Torres), the actual file does not exist in the knowledge base. Some versioning information can be inferred — v1/v2 
**System:** The API versioning strategy at Meridian Technologies is based on the following guidelines:

1. **Versioning via URL Path**: API versions are denoted in the URL path, such as `/v1/` or `/v2/`. For exam
**Score:** 1 — The system answer provides some relevant information but lacks key facts from the gold answer, such as the absence of a comprehensive versioning guide and the mention of the Dashboard V2 PRD's 6-month backward compatibility.
**Recall:** 100% | Retrieved: ['docs/engineering/adr_007_forward_migrations.md', 'docs/engineering/api_rate_limiting.md', 'code/README_api_gateway.md']
