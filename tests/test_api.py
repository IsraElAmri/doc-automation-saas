"""
Integration and unit tests for FastAPI endpoints, authentication,
vector similarity search RAG, rate-limiting, and P2 security validations.
"""
import os
import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ["TESTING"] = "1"

from app.database import Base, get_db
from app.main import app
from app.llm_utils import cosine_similarity, retrieve_top_k_chunks
from app.rate_limiter import limiter


client = TestClient(app)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    """Register and log in a primary test user, returning Bearer auth header."""
    client.post("/auth/register", json={"email": "testuser@example.com", "password": "password123"})
    resp = client.post("/auth/login", json={"email": "testuser@example.com", "password": "password123"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_txt_file(tmp_path):
    """Create a sample .txt file for upload testing."""
    txt_file = tmp_path / "test_document.txt"
    txt_file.write_text(
        "This is a test document about machine learning.\n"
        "Machine learning is a subset of artificial intelligence.\n"
        "It involves training algorithms on data to make predictions.\n"
        "Deep learning uses neural networks with multiple layers.\n"
        "Common frameworks include TensorFlow, PyTorch, and scikit-learn.\n",
        encoding="utf-8",
    )
    return txt_file


# ── Vector Search & Math Unit Tests ───────────────────────────────────

class TestVectorMathAndRetrieval:
    def test_cosine_similarity_identical_vectors(self):
        vec_a = [1.0, 2.0, 3.0]
        vec_b = [1.0, 2.0, 3.0]
        sim = cosine_similarity(vec_a, vec_b)
        assert pytest.approx(sim, 0.0001) == 1.0

    def test_cosine_similarity_orthogonal_vectors(self):
        vec_a = [1.0, 0.0]
        vec_b = [0.0, 1.0]
        sim = cosine_similarity(vec_a, vec_b)
        assert pytest.approx(sim, 0.0001) == 0.0

    def test_cosine_similarity_zero_vector_guard(self):
        vec_a = [0.0, 0.0, 0.0]
        vec_b = [1.0, 2.0, 3.0]
        sim = cosine_similarity(vec_a, vec_b)
        assert sim == 0.0

    def test_retrieve_top_k_chunks_ordering(self):
        query_vec = [1.0, 0.0, 0.0]
        chunks = [
            ("Low relevance chunk", [0.0, 1.0, 0.0]),
            ("High relevance chunk", [0.9, 0.1, 0.0]),
            ("Medium relevance chunk", [0.5, 0.5, 0.0]),
        ]
        top_k = retrieve_top_k_chunks(chunks, query_vec, k=2)
        assert len(top_k) == 2
        assert top_k[0] == "High relevance chunk"
        assert top_k[1] == "Medium relevance chunk"


# ── P2 Upload Security & Content Validation Tests ────────────────────

class TestP2UploadValidations:
    @patch("app.main.MAX_UPLOAD_SIZE_MB", 0.001)  # 1 KB limit — patch the name in app.main's namespace
    def test_upload_exceeds_streaming_size_limit_returns_413(self, client, auth_headers, tmp_path):
        """Test streaming byte counter aborts oversized file and returns HTTP 413."""
        large_file = tmp_path / "oversized.txt"
        large_file.write_bytes(b"A" * 3000)  # 3 KB > 1 KB limit

        with open(large_file, "rb") as f:
            response = client.post(
                "/upload",
                files={"file": ("oversized.txt", f, "text/plain")},
                headers=auth_headers,
            )
        assert response.status_code == 413
        assert "exceeds maximum limit" in response.json()["detail"]

    def test_fake_pdf_header_validation_returns_400(self, client, auth_headers, tmp_path):
        """Test file with fake .pdf extension but invalid header returns HTTP 400."""
        fake_pdf = tmp_path / "malicious.pdf"
        fake_pdf.write_bytes(b"NOT A REAL PDF CONTENT")

        with open(fake_pdf, "rb") as f:
            response = client.post(
                "/upload",
                files={"file": ("malicious.pdf", f, "application/pdf")},
                headers=auth_headers,
            )
        assert response.status_code == 400
        assert "content does not match expected format" in response.json()["detail"]


# ── Root & Info Endpoints ─────────────────────────────────────────────

class TestRootEndpoint:
    def test_root_serves_html(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "DocAI" in response.text

    def test_api_info(self, client):
        response = client.get("/api")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "endpoints" in data


# ── Authentication Endpoints ──────────────────────────────────────────

class TestAuthEndpoints:
    def test_register_user_success(self, client):
        response = client.post(
            "/auth/register",
            json={"email": "newuser@example.com", "password": "securepassword"},
        )
        assert response.status_code in (200, 201)
        data = response.json()
        assert "access_token" in data
        assert data["email"] == "newuser@example.com"

    def test_login_user_invalid_credentials(self, client):
        client.post("/auth/register", json={"email": "loginuser@example.com", "password": "mypassword"})
        response = client.post("/auth/login", json={"email": "loginuser@example.com", "password": "wrongpassword"})
        assert response.status_code == 401
        assert "Incorrect email or password" in response.json()["detail"]


# ── Upload & RAG Endpoints ────────────────────────────────────────────

class TestUploadAndRAGEndpoints:
    @patch("app.main.generate_embedding")
    def test_upload_txt_file_success(self, mock_gen_emb, client, auth_headers, sample_txt_file):
        mock_gen_emb.return_value = [0.1] * 3072

        with open(sample_txt_file, "rb") as f:
            response = client.post(
                "/upload",
                files={"file": ("test_document.txt", f, "text/plain")},
                headers=auth_headers,
            )
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Document uploaded and processed successfully"

    @patch("app.main.answer_question_rag")
    @patch("app.main.generate_embedding")
    def test_ask_vector_rag_success(self, mock_gen_emb, mock_rag, client, auth_headers, sample_txt_file):
        mock_gen_emb.return_value = [0.2] * 3072
        mock_rag.return_value = "Mock RAG answer."

        with open(sample_txt_file, "rb") as f:
            upload_res = client.post("/upload", files={"file": ("test.txt", f, "text/plain")}, headers=auth_headers)
        doc_id = upload_res.json()["document_id"]

        response = client.post(
            f"/ask/{doc_id}",
            json={"question": "What is machine learning?"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["answer"] == "Mock RAG answer."


class TestAdminMetrics:
    def setup_method(self):
        from app.metrics import reset
        reset()

    def test_metrics_requires_auth(self, client):
        response = client.get("/admin/metrics")
        assert response.status_code == 401
        assert "admin token" in response.json()["detail"].lower()

    def test_metrics_wrong_token_returns_401(self, client):
        response = client.get("/admin/metrics", headers={"Authorization": "Bearer wrong_token"})
        assert response.status_code == 401
        assert "admin token" in response.json()["detail"].lower()

    def test_metrics_increments_after_real_request(self, client):
        from config.settings import ADMIN_TOKEN
        
        # 1. Make a real request (even a failing one counts towards 4xx)
        client.post("/auth/login", json={"email": "nobody@example.com", "password": "bad"})

        # 2. Fetch metrics
        response = client.get("/admin/metrics", headers={"Authorization": f"Bearer {ADMIN_TOKEN}"})
        assert response.status_code == 200
        data = response.json()

        # 3. Verify
        assert "POST /auth/login" in data["routes"]
        route_metrics = data["routes"]["POST /auth/login"]
        assert route_metrics["requests"] >= 1
        assert route_metrics["4xx"] >= 1
        assert data["totals"]["requests"] >= 1
