# event-processor

Kafka consumer that processes, enriches, and stores incoming events.

## Tech Stack
- Python 3.11
- confluent-kafka
- ClickHouse (via clickhouse-driver)
- GeoIP2 (MaxMind)

## Architecture

```
Kafka (events.ingest) → event-processor → ClickHouse
                                        → Kafka (workflows.trigger) [if workflow match]
```

## Setup

```bash
git clone git@github.com:meridian-tech/event-processor.git
cd event-processor
pip install -r requirements.txt

# Requires local Kafka and ClickHouse
docker-compose up -d kafka clickhouse

python -m app.consumer
```

## Configuration

All configuration via environment variables:

- `KAFKA_BOOTSTRAP_SERVERS` — default: localhost:9092
- `KAFKA_CONSUMER_GROUP` — default: event-processor-v1
- `CLICKHOUSE_HOST` — default: localhost
- `CLICKHOUSE_DATABASE` — default: meridian
- `MAXMIND_DB_PATH` — path to GeoLite2 database file

## Event Schema

Events consumed from `events.ingest` topic:

```json
{
  "event_id": "uuid",
  "tenant_id": "uuid",
  "event_type": "track|page|identify|group",
  "event_name": "string",
  "properties": {},
  "user_id": "string (optional)",
  "anonymous_id": "string",
  "timestamp": "ISO 8601",
  "received_at": "ISO 8601"
}
```

## Enrichment Pipeline

1. Schema validation
2. Deduplication (Redis-based, 24-hour window)
3. GeoIP enrichment (from IP address)
4. User-agent parsing
5. Workflow trigger matching
6. Write to ClickHouse

## Known Issues

- The GeoIP database needs to be updated monthly. Currently manual process — download from MaxMind and restart the service. TODO: automate this.
- High-cardinality event names (>10,000 unique names per tenant) can cause slow ClickHouse queries. We have a TODO to add cardinality limits.
