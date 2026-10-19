"""Tests for ingestion's pure document and chunk helpers."""

from pathlib import Path
from uuid import UUID

import pytest

from src.ingest import Document, chunk_text, document_fingerprint, load_documents, point_id


def test_chunk_text_respects_chunk_size_and_makes_overlap() -> None:
    text = "First sentence. " * 100

    chunks = chunk_text(text, chunk_size=200, chunk_overlap=40)

    assert len(chunks) > 1
    assert all(len(chunk) <= 200 for chunk in chunks)
    assert chunks[0][-40:].strip() in chunks[1]


@pytest.mark.parametrize(
    ("chunk_size", "chunk_overlap"),
    [(0, 0), (10, -1), (10, 10)],
)
def test_chunk_text_rejects_invalid_settings(chunk_size: int, chunk_overlap: int) -> None:
    with pytest.raises(ValueError):
        chunk_text("some text", chunk_size, chunk_overlap)


def test_load_documents_reads_only_markdown_and_text(tmp_path: Path) -> None:
    (tmp_path / "notes.md").write_text("# Notes", encoding="utf-8")
    (tmp_path / "details.TXT").write_text("Details", encoding="utf-8")
    (tmp_path / "ignore.pdf").write_text("not loaded", encoding="utf-8")

    documents = load_documents(tmp_path)

    assert [(document.source_file, document.text) for document in documents] == [
        ("details.TXT", "Details"),
        ("notes.md", "# Notes"),
    ]


def test_point_id_is_a_stable_uuid() -> None:
    first = point_id("notes.md", 3)

    assert first == point_id("notes.md", 3)
    assert first != point_id("notes.md", 4)
    assert str(UUID(first)) == first


def test_fingerprint_changes_with_document_text() -> None:
    original = Document("notes.md", "same text")
    changed = Document("notes.md", "changed text")

    assert document_fingerprint(original) != document_fingerprint(changed)
