# api-gateway

The main REST API for Meridian Technologies.

## Tech Stack
- Python 3.12
- FastAPI
- SQLAlchemy (async)
- Redis (rate limiting, sessions)
- PostgreSQL

## Setup

```bash
# Clone and install
git clone git@github.com:meridian-tech/api-gateway.git
cd api-gateway
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Environment variables
cp .env.example .env
# Edit .env with your local database credentials

# Run
uvicorn app.main:app --reload --port 8000
```

## Environment Variables

| Variable | Description | Default |
|----------|------------|---------|
| DATABASE_URL | PostgreSQL connection string | postgresql://localhost/meridian |
| REDIS_URL | Redis connection string | redis://localhost:6379 |
| JWT_SECRET | Secret for JWT signing | (required) |
| LAUNCHDARKLY_SDK_KEY | Feature flag SDK key | (required) |
| SENTRY_DSN | Error tracking | (optional) |

## API Documentation

Interactive docs available at `http://localhost:8000/docs` (Swagger UI).

## Testing

```bash
# Unit tests
pytest tests/unit

# Integration tests (requires local DB and Redis)
pytest tests/integration

# Coverage
pytest --cov=app --cov-report=html
```

## Deployment

Deployed via GitHub Actions → ArgoCD. See the deploy process doc for details.

PRs require 2 approving reviews. All CI checks must pass.
