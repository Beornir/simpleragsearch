# ML Platform Guide

**Last Updated:** August 2024
**Author:** ML Infrastructure Team

## Overview

Meridian's ML platform supports model training, evaluation, and serving for our analytics products. We currently serve 3 production models.

## Production Models

| Model | Purpose | Framework | Serving | P95 Latency |
|-------|---------|-----------|---------|-------------|
| Churn Predictor | Predicts customer churn probability | XGBoost | ml-scoring (FastAPI) | 45ms |
| Event Classifier | Categorizes incoming events | Fine-tuned BERT | ml-scoring (FastAPI) | 120ms |
| Anomaly Detector | Detects unusual patterns in metrics | PyTorch (autoencoder) | Batch (Airflow) | N/A (batch) |

## Training Infrastructure

- **Compute**: AWS SageMaker for GPU training. Spot instances preferred (60% cost savings).
- **Experiment tracking**: MLflow (self-hosted on EKS). UI at https://mlflow.internal.meridian.tech
- **Feature store**: Feast, backed by Redis (online) and S3/Parquet (offline).
- **Data**: Training data lives in S3 under `s3://meridian-ml-data/`. Access via IAM roles.

## Model Serving

The `ml-scoring` service is a FastAPI application that loads models on startup:

```python
# Endpoint pattern
POST /v1/predict/{model_name}
{
  "features": {...}
}

# Response
{
  "prediction": ...,
  "model_version": "churn-v2.3.1",
  "latency_ms": 42
}
```

### Scaling

- Horizontal scaling via Kubernetes HPA. Min 2 replicas, max 10.
- CPU threshold: 70% average triggers scale-up.
- Memory: Each replica uses ~2GB (model weights loaded in memory).
- **No GPU required for inference** — all models are CPU-optimized for serving.

## Model Deployment Process

1. Train and evaluate in SageMaker/notebook
2. Register model in MLflow model registry with metrics
3. Promote to "Staging" in MLflow
4. Run automated evaluation suite (see `ml-eval/` repo)
5. If metrics pass, promote to "Production" in MLflow
6. `ml-scoring` service picks up new model version on next deploy (or manual refresh via `/admin/reload-models`)

## Retraining Schedule

| Model | Frequency | Trigger |
|-------|-----------|---------|
| Churn Predictor | Monthly | Scheduled (1st of month) |
| Event Classifier | Quarterly | Manual (after label review) |
| Anomaly Detector | Weekly | Scheduled (Sunday 2am PT) |

## Feature Store

We use **Feast** for feature management:

- **Online store** (Redis): For real-time serving. Features materialized from offline store daily at 4am PT.
- **Offline store** (S3/Parquet): For training. Contains full feature history.
- Feature definitions live in the `feature-store` repo.

## Monitoring

- Model performance metrics pushed to Datadog (`ml.model.*` namespace)
- Automated alerts if prediction distribution shifts significantly (PSI > 0.2)
- Weekly model health report auto-generated and posted to #ml-team Slack

## Access

- SageMaker: Request via IT ticket (Jira MLINFRA project)
- MLflow: SSO via Okta, any engineer can view, ML team can write
- Feature Store: Read access for all engineers, write access for ML team only
