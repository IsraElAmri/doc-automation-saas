"""
Unit tests for OCR text extraction and chunking utilities.
"""
import os
import tempfile
import pytest

from app.ocr_utils import (
    extract_text_from_txt,
    extract_text_from_file,
    chunk_text,
    detect_file_type,
)


# ── detect_file_type tests ────────────────────────────────────────────

class TestDetectFileType:
    def test_pdf(self):
        assert detect_file_type("document.pdf") == "pdf"
        assert detect_file_type("REPORT.PDF") == "pdf"

    def test_image_types(self):
        assert detect_file_type("photo.jpg") == "image"
        assert detect_file_type("scan.jpeg") == "image"
        assert detect_file_type("diagram.png") == "image"
        assert detect_file_type("scan.bmp") == "image"
        assert detect_file_type("scan.tiff") == "image"

    def test_text_types(self):
        assert detect_file_type("notes.txt") == "txt"
        assert detect_file_type("readme.md") == "txt"
        assert detect_file_type("data.csv") == "txt"

    def test_unknown(self):
        assert detect_file_type("archive.zip") == "unknown"
        assert detect_file_type("program.exe") == "unknown"
        assert detect_file_type("noextension") == "unknown"


# ── Text extraction tests ────────────────────────────────────────────

class TestTextExtraction:
    def test_extract_from_txt_file(self, tmp_path):
        """Test plain text file extraction."""
        txt_file = tmp_path / "test.txt"
        content = "Hello World!\nThis is a test document.\nLine three."
        txt_file.write_text(content, encoding="utf-8")

        result = extract_text_from_txt(str(txt_file))
        assert result == content.strip()

    def test_extract_from_file_dispatcher_txt(self, tmp_path):
        """Test that extract_text_from_file routes .txt correctly."""
        txt_file = tmp_path / "sample.txt"
        txt_file.write_text("Sample content here", encoding="utf-8")

        result = extract_text_from_file(str(txt_file))
        assert "Sample content here" in result

    def test_extract_from_file_unsupported(self, tmp_path):
        """Test unsupported file type returns empty string."""
        zip_file = tmp_path / "test.zip"
        zip_file.write_bytes(b"fake zip content")

        result = extract_text_from_file(str(zip_file))
        assert result == ""

    def test_extract_from_nonexistent_file(self):
        """Test extraction from a non-existent file returns empty string."""
        result = extract_text_from_txt("/nonexistent/path/file.txt")
        assert result == ""


# ── Chunking tests ────────────────────────────────────────────────────

class TestChunking:
    def test_chunk_text_basic(self):
        """Test basic chunking produces non-empty chunks."""
        text = "word " * 200  # 1000 chars
        chunks = chunk_text(text, chunk_size=100, chunk_overlap=10)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) > 0

    def test_chunk_text_empty(self):
        """Test empty text returns no chunks."""
        assert chunk_text("") == []
        assert chunk_text("   ") == []

    def test_chunk_text_short(self):
        """Test short text returns single chunk."""
        text = "Short text."
        chunks = chunk_text(text, chunk_size=500)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_chunk_text_preserves_content(self):
        """Test that all original words appear across chunks."""
        words = [f"word{i}" for i in range(100)]
        text = " ".join(words)
        chunks = chunk_text(text, chunk_size=100, chunk_overlap=20)

        # All words should appear in at least one chunk
        all_chunk_text = " ".join(chunks)
        for word in words:
            assert word in all_chunk_text

    def test_chunk_text_none(self):
        """Test None input."""
        assert chunk_text(None) == []
