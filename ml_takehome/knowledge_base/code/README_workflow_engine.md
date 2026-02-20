# workflow-engine

Executes customer-defined automation workflows triggered by events.

## Overview

Customers can create workflows via the dashboard UI or API. A workflow consists of:
- **Trigger**: An event pattern (e.g., "when event 'purchase_completed' with value > $100")
- **Actions**: One or more actions (send email, send Slack notification, update user property, trigger webhook)

## Architecture

```
Kafka (workflows.trigger) → workflow-engine → notification-service
                                            → api-gateway (user property updates)
                                            → external webhooks
```

## Setup

```bash
pip install -r requirements.txt
python -m app.main
```

Requires: Kafka, PostgreSQL (for workflow definitions), Redis (for deduplication)

## API

Workflow definitions are managed through the main api-gateway:

```
POST /v1/workflows — Create workflow
GET /v1/workflows — List workflows
PUT /v1/workflows/{id} — Update workflow
DELETE /v1/workflows/{id} — Delete workflow
POST /v1/workflows/{id}/test — Test workflow with sample event
```

## Execution Guarantees

- **At-least-once delivery**: Workflows may execute more than once for the same event (Kafka consumer semantics). Actions should be idempotent.
- **Ordering**: Events are processed in order within a partition (partitioned by tenant_id).
- **Timeout**: Individual workflow execution timeout: 30 seconds. If exceeded, workflow is marked as failed and retried once.

## Limitations

- Maximum 50 workflows per tenant (Starter plan) or 200 (Professional/Enterprise)
- Maximum 5 actions per workflow
- Webhook actions: 5-second timeout for the external call
- No loops or conditional branching (planned for Q1 2025)
