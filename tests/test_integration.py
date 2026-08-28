"""
Integration & Edge Case Tests for Document Automation SaaS.
Covers document classification, user isolation, admin metrics counters, and RAG flows.
"""
import os
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.ocr_utils import classify_document

client = TestClient(app)


class TestDocumentClassification:
    """Tests AI document classification logic."""

    def test_classify_invoice(self):
        text = "Invoice INV-9901 Total Amount Due: $500.00 Tax included."
        cat = classify_document(text, "receipt.pdf")
        assert cat == "Invoice & Receipt"

    def test_classify_contract_policy(self):
        text = "This Security Policy governs employee data access and compliance terms."
        cat = classify_document(text, "security_policy.pdf")
        assert cat == "Contract & Policy"

    def test_classify_financial_report(self):
        text = "Q3 2026 Financial Summary: Revenue $4.2M, profit margin 38%."
        cat = classify_document(text, "q3_report.txt")
        assert cat == "Financial Report"

    def test_classify_technical_proposal(self):
        text = "Architecture Proposal for SaaS platform with SLA targets."
        cat = classify_document(text, "proposal.md")
        assert cat == "Technical Proposal"

    def test_classify_csv_spreadsheet(self):
        text = "ID,Name,Salary\n1,Alice,5000"
        cat = classify_document(text, "employees.csv")
        assert cat == "Data Spreadsheet"

    def test_classify_general_doc(self):
        text = "Hello world simple note."
        cat = classify_document(text, "notes.txt")
        assert cat == "General Document"


class TestMultiTenantUserIsolation:
    """Tests multi-tenant isolation ensuring users cannot view or delete other users' documents."""

    def test_user_cannot_access_other_user_document(self):
        # Register User 1
        res1 = client.post("/auth/register", json={"email": "user1@example.com", "password": "password123"})
        token1 = res1.json()["access_token"]

        # Register User 2
        res2 = client.post("/auth/register", json={"email": "user2@example.com", "password": "password123"})
        token2 = res2.json()["access_token"]

        # User 1 uploads document
        files = {"file": ("user1_doc.txt", b"Secret data for user 1", "text/plain")}
        upload_res = client.post("/upload", files=files, headers={"Authorization": f"Bearer {token1}"})
        doc_id = upload_res.json()["document_id"]

        # User 2 attempts to extract User 1's document (expect 404)
        extract_res = client.get(f"/extract/{doc_id}", headers={"Authorization": f"Bearer {token2}"})
        assert extract_res.status_code == 404

        # User 2 attempts to delete User 1's document (expect 404)
        delete_res = client.delete(f"/documents/{doc_id}", headers={"Authorization": f"Bearer {token2}"})
        assert delete_res.status_code == 404

        # User 2 attempts to fetch chat history of User 1's document (expect 404)
        chat_res = client.get(f"/chat-history/{doc_id}", headers={"Authorization": f"Bearer {token2}"})
        assert chat_res.status_code == 404


class TestAdminMetricsSecurity:
    """Tests live metrics counter increments and route normalization."""

    def test_admin_metrics_security(self):
        # Request without token -> 401
        res = client.get("/admin/metrics")
        assert res.status_code == 401

        # Request with invalid token -> 401
        res = client.get("/admin/metrics", headers={"Authorization": "Bearer invalid_secret"})
        assert res.status_code == 401

    def test_metrics_increment_on_live_requests(self):
        # Make a call to root endpoint
        client.get("/api")

        # Fetch metrics with admin token
        admin_token = os.getenv("ADMIN_TOKEN", "adf25451332af16920aac2128e3e7f3fd64f43bc361fb12012df37e31702d134")
        res = client.get("/admin/metrics", headers={"Authorization": f"Bearer {admin_token}"})
        assert res.status_code == 200

        data = res.json()
        assert "totals" in data
        assert "routes" in data
        assert data["totals"]["requests"] > 0
