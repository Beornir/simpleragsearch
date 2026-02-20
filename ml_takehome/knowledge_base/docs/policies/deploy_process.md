# Deployment Process

**Effective Date:** June 2024
**Department:** Engineering
**Status:** Active

## Overview

Meridian uses a continuous deployment model with mandatory code review and staged rollouts.

## Pipeline

All services deploy through the following pipeline:

1. **PR Merged to main** → triggers CI (GitHub Actions)
2. **CI passes** → auto-deploys to **staging** environment
3. **Staging soak** → minimum 30 minutes, automated smoke tests run
4. **Canary deploy** → 5% of production traffic for 15 minutes
5. **Full rollout** → if canary metrics are green, deploy to 100%

## Requirements Before Merge

- At least **2 approving reviews** (1 must be from a CODEOWNER)
- All CI checks green (unit tests, integration tests, linting)
- No P1/P2 incidents currently active (deploy freeze during incidents)
- Feature flags for any user-facing changes

## Rollback Procedure

- **Automatic**: If error rate exceeds 1% during canary, the deploy is auto-rolled back.
- **Manual**: Run `meridian deploy rollback <service> --to <sha>` from the CLI. Requires on-call or team lead permissions.
- **Database migrations**: Cannot be auto-rolled back. See ADR-007 for the forward-migration-only policy.

## Deploy Freeze Schedule

| Period | Scope | Exceptions |
|--------|-------|------------|
| Dec 15 - Jan 2 | All services | P1 hotfixes only |
| Last day of each quarter | All services | None |
| During P1 incidents | Affected service | The fix itself |

## Monitoring After Deploy

After every deploy, check the following dashboards in Grafana:
- `service-health/<service-name>` — error rates, latency p50/p95/p99
- `business-metrics/revenue` — if payments-related
- `alerts/active` — any new alerts firing

## Ownership

Deploy tooling is owned by the **Platform team**. For issues, file a ticket in Jira under `PLAT` project or ask in #platform-support.

## Emergency Deploys

For P1 hotfixes during code freeze or outside business hours:
1. Get verbal approval from an Engineering Manager or Director
2. Tag the PR with `hotfix` label
3. CI still runs but staging soak is reduced to 10 minutes
4. Canary stage is skipped — direct to 100% rollout
5. Post-mortem required within 24 hours
