"""
Text extraction from PDF, images (Tesseract OCR), and plain text files.
Also provides text chunking for RAG retrieval.
"""
import os
import magic
from app.logging_config import get_logger

import pytesseract
from PIL import Image
import pypdf

from config.settings import TESSERACT_CMD, CHUNK_SIZE, CHUNK_OVERLAP

logger = get_logger(__name__)

# Configure Tesseract binary path
pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

# ── Supported extensions ──────────────────────────────────────────────
PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}
TEXT_EXTENSIONS = {".txt", ".md", ".csv"}


def classify_document(text: str, filename: str) -> str:
    """
    Intelligently classify a document into a category based on content keywords and filename.
    """
    text_lower = (text or "").lower()
    fn_lower = (filename or "").lower()

    if any(k in text_lower or k in fn_lower for k in ["invoice", "receipt", "paid", "total amount", "tax", "price", "bill"]):
        return "Invoice & Receipt"
    elif any(k in text_lower or k in fn_lower for k in ["policy", "contract", "agreement", "terms", "compliance", "clause"]):
        return "Contract & Policy"
    elif any(k in text_lower or k in fn_lower for k in ["revenue", "financial", "q1", "q2", "q3", "q4", "profit", "balance"]):
        return "Financial Report"
    elif any(k in text_lower or k in fn_lower for k in ["proposal", "architecture", "sla", "technical", "system"]):
        return "Technical Proposal"
    elif fn_lower.endswith(".csv") or any(k in text_lower for k in ["transaction", "csv", "row", "column"]):
        return "Data Spreadsheet"
    else:
        return "General Document"


def validate_file_header(file_path: str, file_type: str) -> bool:
    """
    Validate magic-bytes / file structure to prevent disguised or corrupt files.
    - PDF: Verifies %PDF- header in first 4 bytes.
    - Image: Uses an isolated throwaway PIL Image instance with img.verify().
    - Text: Verifies valid UTF-8/ASCII decoding on initial bytes.
    """
    if not os.path.isfile(file_path):
        return False

    try:
        if file_type == "pdf":
            with open(file_path, "rb") as f:
                header = f.read(4)
                return header == b"%PDF"

        elif file_type == "image":
            with Image.open(file_path) as img:
                img.verify()
            return True

        elif file_type == "txt":
            with open(file_path, "rb") as f:
                sample = f.read(2048)
                sample.decode("utf-8")
            return True

        return False
    except Exception as e:
        logger.warning("File header validation failed for '%s' (%s): %s", file_path, file_type, e)
        return False



def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract text from a PDF file.
    First attempts digital text extraction via pypdf.
    Falls back to OCR (page-by-page image rendering) if digital text is empty.
    """
    text = ""
    try:
        with open(pdf_path, "rb") as f:
            reader = pypdf.PdfReader(f)
            for page in reader.pages:
                page_text = page.extract_text() or ""
                text += page_text + "\n"
    except Exception as e:
        logger.error("Error reading PDF '%s': %s", pdf_path, e)

    # If digital text extraction yielded nothing, the PDF is likely scanned
    if not text.strip():
        logger.info("No digital text in PDF '%s', attempting OCR fallback.", pdf_path)
        text = _ocr_pdf_fallback(pdf_path)

    return text.strip()


def _ocr_pdf_fallback(pdf_path: str) -> str:
    """
    Convert each PDF page to an image and run Tesseract OCR.
    Requires pypdf page images — works for simple scanned PDFs.
    """
    try:
        from pypdf import PdfReader
        reader = PdfReader(pdf_path)
        ocr_texts = []
        for page_num, page in enumerate(reader.pages):
            # pypdf can sometimes extract images; process each one
            for image_obj in page.images:
                try:
                    img = Image.open(image_obj.data)
                    ocr_texts.append(pytesseract.image_to_string(img))
                except Exception:
                    pass
        return "\n".join(ocr_texts)
    except Exception as e:
        logger.error("OCR fallback failed for PDF '%s': %s", pdf_path, e)
        return ""


def extract_text_from_image(image_path: str) -> str:
    """Extract text from an image file using Tesseract OCR."""
    try:
        image = Image.open(image_path)
        text = pytesseract.image_to_string(image)
        return text.strip()
    except Exception as e:
        logger.error("Error reading image '%s': %s", image_path, e)
        return ""


def extract_text_from_txt(file_path: str) -> str:
    """Read plain text file."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read().strip()
    except Exception as e:
        logger.error("Error reading text file '%s': %s", file_path, e)
        return ""


def extract_text_from_file(file_path: str) -> str:
    """
    Detect file type by extension and dispatch to the appropriate extractor.
    Returns extracted text or empty string.
    """
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()

    if ext in PDF_EXTENSIONS:
        return extract_text_from_pdf(file_path)
    elif ext in IMAGE_EXTENSIONS:
        return extract_text_from_image(file_path)
    elif ext in TEXT_EXTENSIONS:
        return extract_text_from_txt(file_path)
    else:
        logger.warning("Unsupported file type: '%s'", ext)
        return ""


def detect_file_type(filename: str) -> str:
    """Return a human-readable file type string."""
    _, ext = os.path.splitext(filename)
    ext = ext.lower()
    if ext in PDF_EXTENSIONS:
        return "pdf"
    elif ext in IMAGE_EXTENSIONS:
        return "image"
    elif ext in TEXT_EXTENSIONS:
        return "txt"
    return "unknown"


# ── Chunking ──────────────────────────────────────────────────────────

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Split text into overlapping chunks for RAG retrieval.
    Uses LangChain RecursiveCharacterTextSplitter when available,
    with a simple fallback otherwise.
    """
    if not text or not text.strip():
        return []

    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        return splitter.split_text(text)
    except ImportError:
        logger.warning("langchain_text_splitters not available; using simple chunking.")
        return _simple_chunk(text, chunk_size)


def _simple_chunk(text: str, chunk_size: int) -> list[str]:
    """Fallback word-boundary chunker."""
    words = text.split()
    chunks: list[str] = []
    current: list[str] = []

    for word in words:
        current.append(word)
        if len(" ".join(current)) >= chunk_size:
            chunks.append(" ".join(current))
            current = []

    if current:
        chunks.append(" ".join(current))

    return chunks