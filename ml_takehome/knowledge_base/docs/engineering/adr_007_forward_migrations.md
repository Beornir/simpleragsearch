# ADR-007: Forward-Only Database Migrations

**Date:** March 2024
**Status:** ACCEPTED
**Authors:** Sarah Chen (Staff Engineer)

## Context

We've had two incidents in the past year caused by failed rollback migrations. Rolling back schema changes is inherently risky because data written after the migration may not be compatible with the old schema.

## Decision

All database migrations at Meridian are **forward-only**. We do not write `down` migrations.

### How to Handle Mistakes

If a migration needs to be "undone," write a **new forward migration** that reverses the change:

```sql
-- Migration 042: Add column (oops, wrong name)
ALTER TABLE users ADD COLUMN emial VARCHAR(255);

-- Migration 043: Fix the typo (forward migration to fix)
ALTER TABLE users RENAME COLUMN emial TO email;
```

### Breaking Changes

For schema changes that are not backward-compatible:

1. Deploy the **new schema** alongside the old one (expand phase)
2. Deploy **application code** that writes to both old and new
3. **Backfill** old data into new schema
4. Deploy application code that reads from new schema only
5. **Clean up** old schema in a separate migration (contract phase)

## Consequences

- Slightly more migrations in the codebase (two instead of one for fixes)
- Need discipline around expand/contract pattern
- Tooling: We use Alembic for Python services and Flyway for Java services. Both support forward-only mode.
- All migrations must be reviewed by a CODEOWNER from the Platform team.
