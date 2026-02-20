# feature-store

Feast-based feature store for ML features.

## Overview

This repo contains Feast feature definitions and materialization jobs for the ML platform.

## Feature Groups

| Feature Group | Entity | Update Frequency | Source |
|--------------|--------|-----------------|--------|
| user_activity | user_id | Hourly | ClickHouse |
| account_health | tenant_id | Daily | PostgreSQL |
| event_patterns | tenant_id | Daily | ClickHouse |
| support_metrics | tenant_id | Daily | Zendesk API |

## Key Features

### user_activity
- `login_count_7d` — Number of logins in last 7 days
- `login_count_30d` — Number of logins in last 30 days
- `login_frequency_trend` — Slope of daily login count (30-day window)
- `last_active_days_ago` — Days since last activity
- `feature_usage_count_30d` — Number of distinct features used

### account_health
- `account_age_days` — Days since account creation
- `monthly_active_users` — Unique active users in last 30 days
- `mau_trend` — Month-over-month MAU change (%)
- `plan_type` — Current subscription plan
- `total_events_30d` — Total events ingested in last 30 days

### support_metrics
- `support_tickets_last_30d` — Open tickets in last 30 days
- `avg_ticket_resolution_hours` — Average resolution time
- `escalation_count_90d` — Escalated tickets in last 90 days

## Online vs Offline Store

- **Online (Redis)**: Materialized daily at 4:00 AM PT. Used by ml-scoring for real-time predictions.
- **Offline (S3/Parquet)**: Full history. Used for training data generation.

## Setup

```bash
pip install feast
cd feature_repo
feast apply  # Register features
feast materialize-incremental $(date -u +"%Y-%m-%dT%H:%M:%S")  # Materialize
```

## Troubleshooting

**Features are stale**: Check the Airflow DAG `feast_materialize_daily`. If it failed, manually run `feast materialize-incremental`.

**Feature not found**: Make sure the feature is defined in `feature_repo/features.py` AND has been applied with `feast apply`.
