# rag-chatbot

## Python environment

The project uses `uv` to manage its Python environment and dependencies. Sync the
environment from the project files with:

```powershell
python -m uv sync
```

The environment includes `qdrant-client` and the development dependency
`pytest`.

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
