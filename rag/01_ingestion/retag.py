"""
Retag — regenerates tags for all files using a curated 2-tier taxonomy.
Updates only the `tags` column in metadata.csv (descriptions/embeddings unchanged).

Tier 1 — ~15 semantic categories (broad topics)
Tier 2 — ~20 proper nouns (tools, services, systems)

Why: 483 tags was too many — LLM couldn't select accurately during query time.
~35 curated tags give precise, consistent matching.
"""

import csv
import json
import sys
import time
from pathlib import Path
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import LLM_BASE_URL, LLM_MODEL, METADATA_CSV, MASTER_TAGS_JSON

llm = OpenAI(base_url=LLM_BASE_URL, api_key="dummy")

# ─── Curated taxonomy ─────────────────────────────────────────────────────────

SEMANTIC_CATEGORIES = [
    "hr-policy",          # PTO, sick leave, parental, remote work, referral bonus
    "expense-policy",     # expenses, reimbursement, budgets, approval limits
    "security-policy",    # access control, credentials, MFA, Vault, BYOD
    "legal-policy",       # data retention, GDPR, CCPA, deletion, privacy
    "deploy-process",     # CI/CD, deployment, code freeze, hotfix, canary
    "incident-response",  # incidents, P1/P2/P3, on-call, post-mortem
    "ml-platform",        # ML models, training, evaluation, model serving
    "feature-store",      # Feast, feature groups, materialization, online/offline store
    "database",           # PostgreSQL, Aurora, Citus, sharding, migrations, ADR
    "infrastructure",     # AWS, Kubernetes, architecture overview, networking
    "api",                # API gateway, rate limiting, endpoints, versioning, auth
    "kafka-events",       # Kafka, event ingestion, event processing, ClickHouse
    "monitoring",         # Datadog, Grafana, alerting, metrics, PagerDuty
    "product-spec",       # PRD, product requirements, dashboard, analytics pipeline
    "meeting-transcript", # All-hands, team syncs, decisions in meeting notes
    "slack-export",       # Slack conversations, channel announcements
    "runbook",            # Operational runbooks, failover procedures, recovery steps
    "adr",                # Architecture Decision Records, technical decisions
    "document-catalog",   # Manifest, index, metadata catalog
]

PROPER_NOUNS = [
    "kafka", "postgresql", "aurora", "clickhouse", "redis",
    "sagemaker", "mlflow", "feast",
    "pagerduty", "datadog", "grafana",
    "workday", "bamboohr",
    "kubernetes", "argocd", "github-actions",
    "launchdarkly", "okta", "vault",
    "fastapi", "python",
    "citus", "pgbouncer",
]

ALL_TAGS = sorted(SEMANTIC_CATEGORIES + PROPER_NOUNS)


def generate_tags_for_file(filepath: str, description: str) -> list[str]:
    """Ask LLM to assign tags from the curated taxonomy."""
    categories_str = "\n".join(f"  - {t}" for t in SEMANTIC_CATEGORIES)
    nouns_str = ", ".join(PROPER_NOUNS)

    prompt = f"""Assign tags to this document from the provided taxonomy. Be accurate — only assign tags that clearly apply.

Document: {filepath}
Description: {description}

Semantic categories (assign 1-4 most relevant):
{categories_str}

Proper nouns — tools/systems mentioned (assign all that apply):
{nouns_str}

Return JSON: {{"tags": ["tag1", "tag2", ...]}}
Return between 2 and 8 tags total."""

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
        tags = result.get("tags", [])
        # Validate — only keep tags in our taxonomy
        valid = [t for t in tags if t in ALL_TAGS]
        return valid if valid else tags[:5]  # fallback if LLM returned custom tags
    except Exception as e:
        print(f"  [tag error] {e}")
        return []


def main():
    print("Reading metadata.csv...")
    rows = []
    with open(METADATA_CSV, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    print(f"Retagging {len(rows)} files with {len(ALL_TAGS)}-tag taxonomy...\n")

    for i, row in enumerate(rows):
        print(f"[{i+1:02d}/{len(rows)}] {row['filename']} ... ", end="", flush=True)
        tags = generate_tags_for_file(row["filepath"], row["description"])
        row["tags"] = "|".join(sorted(set(tags)))
        print(row["tags"])
        time.sleep(0.1)

    print("\nSaving metadata.csv...")
    with open(METADATA_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print("Saving master_tags.json...")
    # New master_tags: identity mapping (tag → tag) for our curated list
    mapping = {t: t for t in ALL_TAGS}
    MASTER_TAGS_JSON.write_text(json.dumps(mapping, indent=2))

    print(f"\nDone. Tags: {ALL_TAGS}")


if __name__ == "__main__":
    main()
