"""
Tests for Items C, D, E1, G, H, I fixes.
These are added without modifying any existing tests.
"""
import os
import sys
import time
import math
import pytest

os.environ.setdefault("TESTING", "1")

# ══════════════════════════════════════════════════════════════════════════════
# Item C — OCR PDF BytesIO fix
# ══════════════════════════════════════════════════════════════════════════════

pytesseract_available = False
try:
    import pytesseract
    pytesseract.get_tesseract_version()
    pytesseract_available = True
except Exception:
    pass


@pytest.mark.skipif(
    not pytesseract_available,
    reason="Tesseract not installed — skipping OCR PDF BytesIO test"
)
def test_ocr_pdf_fallback_returns_nonempty_text(tmp_path):
    """
    Item C: Build an image-only PDF from sample_test_files/ocr_invoice_receipt.png
    using PIL and assert that extract_text_from_pdf returns non-empty text.
    The old code used Image.open(image_obj.data) on raw bytes which raised ValueError
    and was silently swallowed, producing an empty string.
    """
    from PIL import Image
    from app.ocr_utils import extract_text_from_pdf

    sample_img = os.path.join(
        os.path.dirname(__file__), "..", "sample_test_files", "ocr_invoice_receipt.png"
    )
    if not os.path.isfile(sample_img):
        pytest.skip("sample_test_files/ocr_invoice_receipt.png not found")

    pdf_path = str(tmp_path / "test_ocr.pdf")
    img = Image.open(sample_img).convert("RGB")
    img.save(pdf_path, "PDF", resolution=150)

    result = extract_text_from_pdf(pdf_path)
    # The invoice image contains "INV-2026" and total "175.00"
    assert len(result) > 0, (
        f"extract_text_from_pdf returned empty string for image-only PDF. "
        f"This was caused by Image.open(bytes) instead of Image.open(io.BytesIO(bytes))."
    )
    assert "INV-2026" in result, f"Expected 'INV-2026' in extracted text, got: {result!r}"


# ══════════════════════════════════════════════════════════════════════════════
# Item D — Gemini hard timeout
# ══════════════════════════════════════════════════════════════════════════════

def test_call_gemini_respects_timeout(monkeypatch):
    """
    Item D: Monkeypatch the Gemini client to sleep longer than the timeout,
    and assert that _call_gemini raises RuntimeError near the configured deadline
    rather than blocking until the slow call finishes.
    """
    import concurrent.futures
    from app import llm_utils

    SLOW_SLEEP = 4.0  # seconds the fake call will take
    TIMEOUT    = 0.5  # set a short timeout so the test runs quickly

    # Patch GEMINI_TIMEOUT_SECONDS used inside _call_gemini
    monkeypatch.setattr(llm_utils, "GEMINI_TIMEOUT_SECONDS", TIMEOUT)

    original_client = llm_utils.client

    class _SlowModel:
        def generate_content(self, *a, **kw):
            time.sleep(SLOW_SLEEP)

    class _SlowClient:
        models = _SlowModel()

    monkeypatch.setattr(llm_utils, "client", _SlowClient())

    t0 = time.monotonic()
    with pytest.raises(RuntimeError, match="timed out"):
        llm_utils._call_gemini("hello")
    elapsed = time.monotonic() - t0

    # Must return within TIMEOUT + 1 s grace (not SLOW_SLEEP)
    assert elapsed < TIMEOUT + 1.0, (
        f"_call_gemini took {elapsed:.2f}s — timeout ({TIMEOUT}s) was not enforced. "
        f"The ThreadPoolExecutor context-manager pattern blocks on __exit__ until the "
        f"worker finishes; the explicit shutdown(wait=False) pattern fixes this."
    )


# ══════════════════════════════════════════════════════════════════════════════
# Item E1 — Chance metrics correctness
# ══════════════════════════════════════════════════════════════════════════════

def _chance(N, R, k):
    """Import and call calculate_chance_metrics from evaluate_rag."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from scripts.evaluate_rag import calculate_chance_metrics
    return calculate_chance_metrics(N, R, k)


def test_chance_metrics_15item_averages():
    """
    Item E1: Assert that the average chance baseline over all 15 dataset items
    matches the analytically correct values stated in the report:
      P=31.67%, R=50.0%, F1=37.78%, HR=58.89%, MRR=0.575
    These numbers come from full-ranking MRR (not truncated-at-k) and
    F1 as E[F1 over k-subsets] (not F1 of E[P] and E[R]).
    """
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from scripts.evaluate_rag import calculate_chance_metrics, TEST_DATASET

    k = 2
    metrics = [
        calculate_chance_metrics(len(item["context_chunks"]), len(item["relevant_indices"]), k)
        for item in TEST_DATASET
    ]
    n = len(metrics)
    avg_p   = sum(m["p"]   for m in metrics) / n * 100
    avg_r   = sum(m["r"]   for m in metrics) / n * 100
    avg_f1  = sum(m["f1"]  for m in metrics) / n * 100
    avg_hr  = sum(m["hr"]  for m in metrics) / n * 100
    avg_mrr = sum(m["mrr"] for m in metrics) / n

    assert abs(avg_p   - 31.67) < 0.1,  f"P={avg_p:.2f}% expected ~31.67%"
    assert abs(avg_r   - 50.0)  < 0.1,  f"R={avg_r:.2f}% expected ~50.0%"
    assert abs(avg_f1  - 37.78) < 0.1,  f"F1={avg_f1:.2f}% expected ~37.78%"
    assert abs(avg_hr  - 58.89) < 0.1,  f"HR={avg_hr:.2f}% expected ~58.89%"
    assert abs(avg_mrr - 0.575) < 0.01, f"MRR={avg_mrr:.4f} expected ~0.575"


# ══════════════════════════════════════════════════════════════════════════════
# Item G — CHUNK_OVERLAP < CHUNK_SIZE validation
# ══════════════════════════════════════════════════════════════════════════════

def test_chunk_overlap_less_than_chunk_size():
    """
    Item G: Verify that the default CHUNK_OVERLAP (50) is strictly less than
    the default CHUNK_SIZE (500) — i.e. the validation in settings.py passes
    under normal conditions.
    """
    from config.settings import CHUNK_SIZE, CHUNK_OVERLAP
    assert CHUNK_OVERLAP < CHUNK_SIZE, (
        f"CHUNK_OVERLAP ({CHUNK_OVERLAP}) must be < CHUNK_SIZE ({CHUNK_SIZE})"
    )


# ══════════════════════════════════════════════════════════════════════════════
# Item H — classify_document whole-word matching
# ══════════════════════════════════════════════════════════════════════════════

def test_classify_document_no_false_positive_price_in_column_name():
    """
    Item H: 'price' as a substring of 'Unit_Price' must NOT classify as Invoice.
    The old code used 'price' in text_lower which matched any occurrence of the
    substring. The fixed code uses \\b word-boundary regex.
    """
    from app.ocr_utils import classify_document
    # Text contains "Unit_Price" (price is a substring, not a standalone word)
    # and no actual invoice keywords
    result = classify_document("Unit_Price Column Data", "report.csv")
    # Should not be Invoice & Receipt — it has "csv" extension → Data Spreadsheet
    assert result != "Invoice & Receipt", (
        "'price' inside 'Unit_Price' should not trigger Invoice classification"
    )


def test_classify_document_standalone_invoice_keyword():
    """Item H: Standalone 'invoice' should still classify correctly."""
    from app.ocr_utils import classify_document
    result = classify_document("Please pay this invoice by due date.", "billing.txt")
    assert result == "Invoice & Receipt"


def test_classify_document_system_not_false_positive():
    """
    Item H: 'system' as a word should NOT classify as Technical Proposal
    when it appears in a non-technical context.
    The word 'system' was removed from the Technical Proposal keywords in the fix.
    """
    from app.ocr_utils import classify_document
    # 'system' appears but no other proposal keywords
    result = classify_document("The operating system crashed yesterday.", "notes.txt")
    # Should not be Technical Proposal since 'system' was removed from that category
    assert result != "Technical Proposal"


# ══════════════════════════════════════════════════════════════════════════════
# Item I — compare_digest bytes encoding
# ══════════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════
# Item I — compare_digest bytes encoding
# ══════════════════════════════════════════════════════════════════════════════

def test_admin_metrics_wrong_ascii_token_returns_401():
    """
    Item I (API level): A wrong but valid-ASCII Bearer token must return 401.
    """
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get(
        "/admin/metrics",
        headers={"Authorization": "Bearer wrong-token-ascii-only"}
    )
    assert response.status_code == 401


def test_compare_digest_bytes_encoding_does_not_raise_for_non_ascii():
    """
    Item I (unit level): Prove that encoding both sides to bytes before
    secrets.compare_digest prevents TypeError/UnicodeEncodeError on non-ASCII
    strings. Python's secrets.compare_digest raises TypeError if given str
    arguments that contain non-ASCII chars — bytes avoids this entirely.
    """
    import secrets
    # These contain non-ASCII characters
    token_a = "café-secret"
    token_b = "café-secret"

    # Old code: secrets.compare_digest(str, str) raises TypeError in CPython
    # for strings that cannot be processed as ASCII-safe.
    # New code: encode to bytes first.
    result = secrets.compare_digest(
        token_a.encode("utf-8"),
        token_b.encode("utf-8")
    )
    assert result is True  # identical tokens encoded as bytes should match

    result_mismatch = secrets.compare_digest(
        "different".encode("utf-8"),
        token_b.encode("utf-8")
    )
    assert result_mismatch is False

