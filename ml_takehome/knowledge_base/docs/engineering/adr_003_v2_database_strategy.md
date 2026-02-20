# ADR-003: Database Strategy Update

**Date:** June 2024
**Status:** ACCEPTED
**Authors:** Priya Patel (VP Engineering)

## Context

After completing Phase 1 of the Citus migration (ADR-003), we've encountered significant operational complexity. The Citus coordinator node has become a single point of failure, and our team has spent ~40% of the last quarter on migration-related issues rather than feature work.

## Decision

We are **pausing the Citus migration** after Phase 1 and pivoting to a different strategy:

1. **Keep the `events` table on Citus** (already migrated, working well enough).
2. **Move remaining tables to Amazon Aurora PostgreSQL** with read replicas instead of continuing with sharding.
3. **Implement a read/write splitting layer** at the application level using PgBouncer.
4. **Defer full sharding** to 2025 when we evaluate CockroachDB or PlanetScale more seriously.

## Rationale

- Aurora handles our write volume for all tables except `events` (which is already sharded).
- The operational burden of Citus is not justified for tables under 200GB.
- Read replicas solve the read scaling problem at much lower complexity.
- Cost difference: Aurora ~$30K/year vs Citus ~$50K/year for the full sharding plan.

## Impact

- Phase 2 and Phase 3 of the original ADR-003 are **cancelled**.
- The Platform team will set up Aurora in Q3 2024.
- Existing Citus sharding for `events` table remains in place.
- Need to update monitoring and alerting for the Aurora setup.

## Migration Plan

1. Provision Aurora cluster (us-west-2, db.r6g.2xlarge primary + 2 read replicas)
2. Set up logical replication from current PostgreSQL to Aurora
3. Run in parallel for 2 weeks with automated comparison
4. Cut over during maintenance window (Saturday 2am PT)
