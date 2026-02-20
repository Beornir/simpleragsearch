# Analytics Pipeline — Product Specification

**Author:** David Kim (Product Manager, Data)
**Date:** February 2024

## Overview

This document describes the customer-facing analytics pipeline from a product perspective.

## Data Flow (Simplified)

1. Customer sends events via our JavaScript SDK, REST API, or server-side SDKs
2. Events are ingested and appear in the analytics dashboard within **~60 seconds** (target SLA)
3. Historical data available for querying up to **13 months** (Starter plan) or **25 months** (Professional/Enterprise)

## Event Types

- **Track events**: Custom events sent by the customer (e.g., "button_clicked", "purchase_completed")
- **Page views**: Automatic via JS SDK
- **Identify events**: Associates anonymous user with known identity
- **Group events**: Associates user with company/account

## Query Capabilities

Customers can query their data through:
1. **Dashboard widgets** — pre-built and custom
2. **Query builder** — visual, no-code query interface
3. **SQL editor** — available on Professional+ plans, read-only access to their ClickHouse namespace
4. **API** — programmatic access to query results

## Retention and Limits

| Plan | Event Volume | Data Retention | Query Timeout |
|------|-------------|----------------|---------------|
| Starter | 1M events/month | 13 months | 30 seconds |
| Professional | 10M events/month | 25 months | 60 seconds |
| Enterprise | Custom | 25+ months | 120 seconds |

Overages are billed at $5 per additional million events.

## Known Limitations

- Events received out of order (>24 hours late) may not appear in historical aggregations correctly
- The SQL editor does not support JOINs across event types (ClickHouse limitation with our schema)
- Real-time dashboard refresh rate is 30 seconds; cannot be customized
