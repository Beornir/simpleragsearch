# legacy-analytics (DEPRECATED)

⚠️ **This service is deprecated as of March 2024.** All functionality has been migrated to the event-processor + ClickHouse pipeline.

## What This Was

The original analytics backend, built on:
- Node.js
- MongoDB (for event storage)
- Custom aggregation pipeline

## Migration Status

- All event ingestion moved to event-processor (Kafka + ClickHouse)
- MongoDB data archived to S3 (s3://meridian-archive/legacy-analytics/)
- API endpoints redirected to new api-gateway

## Why Deprecated

- MongoDB couldn't handle the query patterns at scale (slow aggregations)
- No support for SQL-like queries that customers wanted
- Operational burden: the MongoDB cluster required constant attention

## Remaining Dependencies

~~The billing-service still reads from MongoDB for historical invoice data pre-March 2024.~~ UPDATE: billing-service migrated to PostgreSQL as of June 2024. No remaining dependencies.

## DO NOT

- Do not deploy this service
- Do not connect anything new to the MongoDB cluster
- The MongoDB cluster will be decommissioned in December 2024
