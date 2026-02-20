# API Rate Limiting

**Last Updated:** May 2024
**Owner:** Platform Team

## Overview

All Meridian API endpoints are rate-limited per tenant. Rate limits are enforced at the API Gateway level using Redis-backed sliding window counters.

## Default Limits

| Plan | Requests/minute | Requests/hour | Burst |
|------|----------------|---------------|-------|
| Starter | 60 | 1,000 | 10 |
| Professional | 300 | 10,000 | 50 |
| Enterprise | 1,000 | 50,000 | 200 |
| Custom | Negotiated | Negotiated | Negotiated |

## Rate Limit Headers

Every API response includes rate limit headers:

```
X-RateLimit-Limit: 300
X-RateLimit-Remaining: 247
X-RateLimit-Reset: 1709654400
```

When rate limited, the API returns `429 Too Many Requests` with a `Retry-After` header.

## Exemptions

- Health check endpoints (`/health`, `/ready`) are not rate limited
- Internal service-to-service calls bypass rate limiting (identified by mTLS)
- Webhook delivery endpoints have separate, higher limits (5,000/min)

## Configuration

Rate limits are configured in LaunchDarkly under the `rate-limits` feature flag group. Changes take effect within 30 seconds (Redis cache TTL).

## Monitoring

- Dashboard: Grafana → "API Rate Limiting" dashboard
- Alert: Fires when any single tenant exceeds 80% of their limit for 5+ consecutive minutes
- Metric: `api.rate_limit.rejected` in Datadog
