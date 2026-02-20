"""
Single shared config for all modules.
All values can be overridden via environment variables.
"""

import os
from pathlib import Path

# ─── Model endpoints ──────────────────────────────────────────────────────────

# TODO: set your LLM and embedding server URLs via environment variables
LLM_BASE_URL  = os.environ.get("LLM_BASE_URL",  "http://YOUR_LLM_HOST:PORT/v1")
LLM_MODEL     = os.environ.get("LLM_MODEL",     "YOUR_LLM_MODEL_NAME")
EMBED_BASE_URL = os.environ.get("EMBED_BASE_URL", "http://YOUR_EMBED_HOST:PORT/v1")
EMBED_MODEL   = os.environ.get("EMBED_MODEL",   "YOUR_EMBED_MODEL_NAME")

# ─── Data paths ───────────────────────────────────────────────────────────────

_HERE = Path(__file__).parent  # = rag/

# Knowledge base root — mounted as a volume in Docker
KB_PATH = Path(os.environ.get("KB_PATH", str(_HERE.parent / "ml_takehome" / "knowledge_base")))

# Metadata files live next to this config by default;
# override via env vars when running in Docker (mount ./rag to /data/rag)
METADATA_CSV     = Path(os.environ.get("METADATA_CSV",     str(_HERE / "metadata.csv")))
MASTER_TAGS_JSON = Path(os.environ.get("MASTER_TAGS_JSON", str(_HERE / "master_tags.json")))

MANIFEST_PATH = KB_PATH / "meta" / "document_manifest.csv"

# ─── Ingestion settings ───────────────────────────────────────────────────────

SKIP_FILES           = {"grandmas_lasagna_recipe.md", ".DS_Store"}
SUPPORTED_EXTENSIONS = {".md", ".json", ".txt", ".csv", ".pdf"}
MAX_CONTENT_CHARS    = 12000

# ─── Retrieval weights ────────────────────────────────────────────────────────

TOP_K                = 10
VECTOR_WEIGHT        = 0.55
TAG_WEIGHT           = 0.25
BM25_WEIGHT          = 0.20
MIN_SCORE            = 0.05
MIN_RETRIEVAL_SCORE  = 0.52
CONFIDENCE_THRESHOLD = 0.45
