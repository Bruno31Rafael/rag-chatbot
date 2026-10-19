# rag-chatbot

## Python environment

The project uses `uv` to manage its Python environment and dependencies. Sync the
environment from the project files with:

```powershell
python -m uv sync
```

The environment includes `qdrant-client`, `ollama`, and `python-dotenv`, plus
the development dependency `pytest`.

Copy `.env.example` to `.env` to override the defaults. The ingestion settings
include `EMBEDDING_MODEL`, `QDRANT_COLLECTION`, `CHUNK_SIZE` (default 1000
characters), and `CHUNK_OVERLAP` (default 150 characters).

## Step 1: Start Qdrant

Docker Compose runs Qdrant locally and stores its data in the persistent
`qdrant_storage` volume.

```powershell
docker compose up -d
python -m uv run python scripts/check_qdrant.py
```

The connection check uses `http://localhost:6333` by default. Set `QDRANT_URL`
to check a different Qdrant URL. Stop Qdrant with `docker compose down`; the
persistent volume remains available for the next start.

## Step 2: Ingest documents

Place `.md` and `.txt` files in `data/docs/`. Preview how many chunks ingestion
will create without contacting Ollama or Qdrant:

```powershell
python -m uv run python -m src.ingest --dry-run
```

After reviewing the dry-run count and ensuring Qdrant is running and Ollama has
the configured embedding model, ingest the documents with:

```powershell
python -m uv run python -m src.ingest
```
