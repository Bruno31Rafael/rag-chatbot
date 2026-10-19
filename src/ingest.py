"""Load local Markdown and text documents into Qdrant."""

import argparse
import hashlib
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import ollama
from qdrant_client import QdrantClient, models

from src import config


LOGGER = logging.getLogger(__name__)
SUPPORTED_SUFFIXES = {".md", ".txt"}
EMBED_BATCH_SIZE = 32


@dataclass(frozen=True)
class Document:
    """A source file and its extracted text."""

    source_file: str
    text: str


def load_documents(docs_dir: Path) -> list[Document]:
    """Read supported Markdown and text files beneath ``docs_dir``."""
    if not docs_dir.is_dir():
        raise FileNotFoundError(f"Documents directory does not exist: {docs_dir}")

    documents: list[Document] = []
    paths = sorted(
        path
        for path in docs_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    )
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as error:
            LOGGER.warning("Could not read %s: %s", path.name, error)
            continue
        documents.append(
            Document(source_file=path.relative_to(docs_dir).as_posix(), text=text)
        )
    return documents


def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Split text into overlapping character chunks near natural boundaries."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be between zero and chunk_size - 1")

    text = text.strip()
    if not text:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            earliest_boundary = start + chunk_size // 2
            for separator in ("\n\n", "\n", " "):
                boundary = text.rfind(separator, earliest_boundary, end)
                if boundary >= earliest_boundary:
                    end = boundary
                    break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(text):
            break
        start = max(start + 1, end - chunk_overlap)
    return chunks


def document_fingerprint(document: Document) -> str:
    """Hash content and embedding/chunk settings to detect unchanged files."""
    fingerprint_data = {
        "text": document.text,
        "embedding_model": config.EMBEDDING_MODEL,
        "chunk_size": config.CHUNK_SIZE,
        "chunk_overlap": config.CHUNK_OVERLAP,
    }
    encoded = json.dumps(fingerprint_data, sort_keys=True, ensure_ascii=False).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def point_id(source_file: str, chunk_index: int) -> str:
    """Return a stable UUID for a document path and chunk index."""
    return str(uuid5(NAMESPACE_URL, f"ask-my-documents:{source_file}:{chunk_index}"))


def _source_filter(source_file: str) -> models.Filter:
    """Build a Qdrant filter for all points belonging to one source file."""
    return models.Filter(
        must=[
            models.FieldCondition(
                key="source_file", match=models.MatchValue(value=source_file)
            )
        ]
    )


def _existing_source_points(
    client: QdrantClient, source_file: str
) -> list[models.Record]:
    """Read all existing Qdrant points for a source file."""
    points: list[models.Record] = []
    offset = None
    while True:
        page, offset = client.scroll(
            collection_name=config.QDRANT_COLLECTION,
            scroll_filter=_source_filter(source_file),
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        points.extend(page)
        if offset is None:
            return points


def _ensure_collection(client: QdrantClient, vector_size: int) -> None:
    """Create the collection or check its configured vector size."""
    if not client.collection_exists(config.QDRANT_COLLECTION):
        client.create_collection(
            collection_name=config.QDRANT_COLLECTION,
            vectors_config=models.VectorParams(
                size=vector_size, distance=models.Distance.COSINE
            ),
        )
        return

    collection = client.get_collection(config.QDRANT_COLLECTION)
    vectors = collection.config.params.vectors
    existing_size = getattr(vectors, "size", None)
    if existing_size != vector_size:
        raise ValueError(
            f"Collection {config.QDRANT_COLLECTION!r} has vector size "
            f"{existing_size}, but model {config.EMBEDDING_MODEL!r} returned "
            f"vectors of size {vector_size}. Use a new collection or recreate "
            "the existing one."
        )


def _embed_chunks(client: ollama.Client, chunks: list[str]) -> list[list[float]]:
    """Embed chunks in small batches using the required document prefix."""
    vectors: list[list[float]] = []
    for batch_start in range(0, len(chunks), EMBED_BATCH_SIZE):
        batch = chunks[batch_start : batch_start + EMBED_BATCH_SIZE]
        response = client.embed(
            model=config.EMBEDDING_MODEL,
            input=[f"search_document: {chunk}" for chunk in batch],
        )
        vectors.extend(response.embeddings)
    return vectors


def _delete_points(client: QdrantClient, point_ids: list[str]) -> None:
    """Delete points by their existing UUIDs when there are any."""
    if point_ids:
        client.delete(
            collection_name=config.QDRANT_COLLECTION,
            points_selector=models.PointIdsList(points=point_ids),
            wait=True,
        )


def ingest_document(
    document: Document, qdrant: QdrantClient, embedder: ollama.Client
) -> tuple[int, bool]:
    """Embed and upsert one document, removing obsolete trailing chunks."""
    existing = (
        _existing_source_points(qdrant, document.source_file)
        if qdrant.collection_exists(config.QDRANT_COLLECTION)
        else []
    )
    chunks = chunk_text(document.text, config.CHUNK_SIZE, config.CHUNK_OVERLAP)

    if not chunks:
        if existing:
            _delete_points(qdrant, [str(point.id) for point in existing])
        LOGGER.warning("Skipping empty document: %s", document.source_file)
        return 0, False

    fingerprint = document_fingerprint(document)
    if existing and len(existing) == len(chunks) and all(
        (point.payload or {}).get("document_fingerprint") == fingerprint
        for point in existing
    ):
        LOGGER.info("Unchanged; skipping %s", document.source_file)
        return len(chunks), True

    vectors = _embed_chunks(embedder, chunks)
    if len(vectors) != len(chunks):
        raise RuntimeError(
            f"Ollama returned {len(vectors)} embeddings for {len(chunks)} chunks "
            f"from {document.source_file}."
        )
    _ensure_collection(qdrant, len(vectors[0]))

    points = [
        models.PointStruct(
            id=point_id(document.source_file, index),
            vector=vector,
            payload={
                "text": chunk,
                "source_file": document.source_file,
                "chunk_index": index,
                "document_fingerprint": fingerprint,
                "embedding_model": config.EMBEDDING_MODEL,
            },
        )
        for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True))
    ]
    qdrant.upsert(
        collection_name=config.QDRANT_COLLECTION,
        points=points,
        wait=True,
    )

    current_ids = {point.id for point in points}
    stale_ids = [str(point.id) for point in existing if str(point.id) not in current_ids]
    _delete_points(qdrant, stale_ids)
    return len(chunks), False


def run_ingestion(dry_run: bool = False) -> int:
    """Load supported files and optionally embed and store their chunks."""
    documents = load_documents(config.DOCS_DIR)
    planned = [
        (document, chunk_text(document.text, config.CHUNK_SIZE, config.CHUNK_OVERLAP))
        for document in documents
    ]
    total_chunks = sum(len(chunks) for _, chunks in planned)
    LOGGER.info(
        "Found %d Markdown/text files and %d non-empty chunks in %s.",
        len(documents),
        total_chunks,
        config.DOCS_DIR,
    )
    for document, chunks in planned:
        LOGGER.info("%s: %d chunks", document.source_file, len(chunks))

    if dry_run:
        LOGGER.info("Dry run: no Ollama or Qdrant requests were made.")
        return 0
    if not documents:
        LOGGER.info("No supported documents to ingest.")
        return 0

    try:
        qdrant = QdrantClient(url=config.QDRANT_URL, timeout=10)
        qdrant.get_collections()
    except Exception as error:
        LOGGER.error("Could not connect to Qdrant at %s: %s", config.QDRANT_URL, error)
        return 1

    embedder = ollama.Client(host=config.OLLAMA_URL, timeout=120)
    for document, chunks in planned:
        try:
            count, skipped = ingest_document(document, qdrant, embedder)
        except Exception as error:
            LOGGER.error("Could not ingest %s: %s", document.source_file, error)
            return 1
        if not skipped:
            LOGGER.info("Stored %d chunks from %s", count, document.source_file)
    return 0


def main() -> int:
    """Parse command-line options and run ingestion."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="count files and chunks without connecting to Ollama or Qdrant",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        return run_ingestion(dry_run=args.dry_run)
    except (FileNotFoundError, ValueError) as error:
        LOGGER.error("%s", error)
        return 1


if __name__ == "__main__":
    sys.exit(main())
