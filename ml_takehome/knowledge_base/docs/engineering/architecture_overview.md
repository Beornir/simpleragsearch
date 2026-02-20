# Meridian Technologies — System Architecture

**Last Updated:** July 2024
**Author:** Platform Team

## Overview

Meridian is a B2B SaaS platform that provides analytics and workflow automation for mid-market companies. Our system serves approximately **2,000 active tenants** and processes **~50 million events per day**.

## High-Level Architecture

```
                          ┌──────────────┐
                          │  CloudFront  │
                          │    (CDN)     │
                          └──────┬───────┘
                                 │
                          ┌──────┴───────┐
                          │     ALB      │
                          │(Load Balancer)│
                          └──────┬───────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                  │
       ┌──────┴──────┐  ┌───────┴───────┐  ┌───────┴───────┐
       │  API Gateway │  │  Web App      │  │  Webhook      │
       │  (FastAPI)   │  │  (Next.js)    │  │  Processor    │
       └──────┬──────┘  └───────┬───────┘  └───────┬───────┘
              │                  │                  │
              └──────────────────┼──────────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                  │
       ┌──────┴──────┐  ┌───────┴───────┐  ┌───────┴───────┐
       │  PostgreSQL  │  │    Redis      │  │   Kafka       │
       │  (Primary DB)│  │   (Cache)     │  │  (Events)     │
       └─────────────┘  └───────────────┘  └───────┬───────┘
                                                    │
                                            ┌───────┴───────┐
                                            │   ClickHouse  │
                                            │  (Analytics)  │
                                            └───────────────┘
```

## Services

| Service | Language | Owner Team | Description |
|---------|----------|-----------|-------------|
| api-gateway | Python (FastAPI) | Platform | Main REST API, authentication, rate limiting |
| web-app | TypeScript (Next.js) | Frontend | Customer-facing dashboard |
| event-processor | Python | Data | Kafka consumer, event enrichment, writes to ClickHouse |
| workflow-engine | Python | Product | Executes customer-defined automation workflows |
| notification-service | Go | Platform | Email, Slack, webhook notifications |
| ml-scoring | Python (FastAPI) | ML Infra | Real-time ML model serving |
| data-privacy-service | Python | Platform | GDPR/CCPA deletion cascades |
| billing-service | Python | Payments | Stripe integration, usage metering |

## Infrastructure

- **Cloud**: AWS (us-west-2 primary, us-east-1 DR)
- **Orchestration**: Kubernetes (EKS)
- **CI/CD**: GitHub Actions → ArgoCD
- **Monitoring**: Datadog (metrics + traces), PagerDuty (alerting)
- **Logging**: ELK stack (Elasticsearch, Logstash, Kibana)
- **Feature flags**: LaunchDarkly

## Key Technical Decisions

- **PostgreSQL with Citus** for the events table (sharded by tenant_id). See ADR-003.
- **ClickHouse** for analytics queries. Ingests from Kafka with ~30 second delay.
- **Redis** for caching (session data, feature flags, rate limiting). TTL: 5 min for most keys.
- **Kafka** as the event bus. 3 brokers, retention: 7 days for most topics, 30 days for audit topics.

## Authentication

- **Customer-facing**: JWT tokens issued by api-gateway. Tokens expire after 1 hour. Refresh tokens valid for 30 days.
- **Service-to-service**: mTLS within the Kubernetes cluster. External services use API keys managed in Vault.
- **Admin panel**: Okta SSO with MFA required.

## Data Flow

1. Customer sends event via REST API or SDK
2. api-gateway validates, authenticates, rate-limits
3. Event published to Kafka topic `events.ingest`
4. event-processor consumes, enriches (geo-IP, user-agent parsing), writes to ClickHouse
5. If event matches a workflow trigger, publishes to `workflows.trigger` topic
6. workflow-engine consumes and executes the workflow
