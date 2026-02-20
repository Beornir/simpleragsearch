FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Shared config sits at /app/config.py
COPY rag/config.py .

# Source modules
COPY rag/01_ingestion/ ./01_ingestion/
COPY rag/02_search/ ./02_search/
COPY rag/03_eval/ ./03_eval/
