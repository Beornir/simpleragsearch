# ml-scoring

Real-time ML model serving service.

## Tech Stack
- Python 3.10 (migration to 3.12 planned for Q4 2024)
- FastAPI
- MLflow (model registry)
- XGBoost, PyTorch, Transformers

## Models Served

- `churn-predictor` — XGBoost, predicts customer churn probability
- `event-classifier` — Fine-tuned BERT, categorizes events

## API

```
POST /v1/predict/{model_name}
Content-Type: application/json

{
  "features": {
    "account_age_days": 365,
    "monthly_active_users": 50,
    "support_tickets_last_30d": 3,
    "login_frequency_trend": -0.15
  }
}

Response:
{
  "prediction": 0.73,
  "model_version": "churn-v2.3.1",
  "latency_ms": 42
}
```

## Setup

```bash
git clone git@github.com:meridian-tech/ml-scoring.git
cd ml-scoring
pip install -r requirements.txt

# Set MLflow tracking URI
export MLFLOW_TRACKING_URI=http://localhost:5000

# Run
uvicorn app.main:app --port 8001
```

## Model Loading

Models are loaded from MLflow on startup. To refresh without restart:

```
POST /admin/reload-models
```

## Monitoring

Metrics exposed at `/metrics` (Prometheus format):
- `ml_prediction_latency_seconds` — histogram
- `ml_prediction_count` — counter by model and version
- `ml_model_version` — gauge showing current model version

## Deprecated Endpoints

~~`GET /v1/models` — Lists available models. Use MLflow UI instead.~~
~~`POST /v1/batch-predict` — Batch prediction. Removed in v2.0. Use the batch pipeline (Airflow) for batch scoring.~~
