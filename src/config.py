"""Environment-based settings for ingestion and retrieval."""

import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

DOCS_DIR = Path(os.getenv("DOCS_DIR") or PROJECT_ROOT / "data" / "docs")
if not DOCS_DIR.is_absolute():
    DOCS_DIR = PROJECT_ROOT / DOCS_DIR

OLLAMA_URL = os.getenv("OLLAMA_URL") or "http://localhost:11434"
QDRANT_URL = os.getenv("QDRANT_URL") or "http://localhost:6333"
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL") or "nomic-embed-text"
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION") or "documents"
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE") or "1000")
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP") or "150")
