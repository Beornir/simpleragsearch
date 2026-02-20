# ADR-003: Database Migration Strategy

**Date:** January 2024
**Status:** ACCEPTED
**Authors:** Sarah Chen (Staff Engineer), Mike Torres (Principal Engineer)

## Context

We are migrating from our monolithic PostgreSQL database (single instance, 2TB) to a sharded architecture. The current database is a bottleneck — we're hitting connection limits during peak traffic and vertical scaling is maxed out.

## Decision

We will adopt a **phased horizontal sharding approach** using Citus (PostgreSQL extension):

1. **Phase 1 (Q1 2024)**: Shard the `events` table by `tenant_id`. This is our largest table (800GB) and most write-heavy.
2. **Phase 2 (Q2 2024)**: Shard `user_sessions` and `analytics` tables.
3. **Phase 3 (Q3 2024)**: Migrate remaining large tables. Keep small reference tables as non-sharded.

### Shard Key Selection

- **Primary shard key**: `tenant_id` for all multi-tenant tables.
- **Rationale**: Most queries are scoped to a single tenant. Cross-tenant queries are rare and can tolerate higher latency.

## Alternatives Considered

1. **Vitess (MySQL)** — Would require migrating from PostgreSQL. Too risky.
2. **CockroachDB** — Promising but we have deep PostgreSQL expertise and don't want to retrain.
3. **AWS Aurora with read replicas** — Doesn't solve write bottleneck.
4. **Application-level sharding** — Too much application code changes.

## Consequences

- Need to update all queries to include `tenant_id` in WHERE clauses.
- Cross-shard joins will need to be refactored into application-level joins.
- Estimated **3 months of migration work** per phase.
- Citus licensing cost: ~$50K/year for our cluster size.

## Migration Safety

- All migrations are **forward-only** (see ADR-007).
- Each phase will run in shadow mode for 2 weeks: dual-writing to old and new schemas, comparing results.
- Rollback plan: revert application to read from unsharded tables (data will still be there during transition period).
