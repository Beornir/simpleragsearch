# data-privacy-service

Handles GDPR and CCPA data deletion and export requests.

## Overview

When a customer requests data deletion or export via the Privacy Center (privacy.meridian.tech), this service orchestrates the cascade across all data stores.

## Deletion Flow

1. Request received via API from Privacy Center
2. Service queries all known data stores for data associated with the user/tenant
3. Deletion tasks queued per store (PostgreSQL, ClickHouse, Redis, S3, Kafka)
4. Each deletion confirmed, status updated
5. Confirmation email sent to requester

## Data Stores and Handlers

| Store | Handler | Method |
|-------|---------|--------|
| PostgreSQL | `handlers/postgres.py` | SQL DELETE with cascade |
| ClickHouse | `handlers/clickhouse.py` | ALTER TABLE DELETE |
| Redis | `handlers/redis.py` | Key pattern deletion |
| S3 | `handlers/s3.py` | Object deletion by prefix |
| Kafka | N/A | Data expires naturally (7-day retention) |

## SLA

- Deletion requests must be completed within **30 days** (legal requirement)
- Current average completion time: **~4 hours**
- Export requests: **~2 hours** (generates ZIP file, uploads to S3, sends download link)

## Setup

```bash
pip install -r requirements.txt
python -m app.main

# Requires access to all data stores listed above
```

## Monitoring

- Dashboard: Grafana → "Data Privacy SLAs"
- Alert: If any request is >7 days old and not completed
- Metric: `privacy.deletion.completed` / `privacy.deletion.pending` in Datadog
