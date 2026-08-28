# Document Automation SaaS — Enterprise AI Portal

> **Smart AI Agent for Document Automation & RAG Querying**
> Built for ITGate Group — Powered by FastAPI, PostgreSQL, Tesseract OCR, and Google Gemini AI.

---

## 📌 Project Overview

This application is an enterprise-grade **Document Automation SaaS** that enables users to upload, process, classify, analyze, and query documents using AI-driven RAG (Retrieval-Augmented Generation).

### 🌟 Key Capabilities
- **Multi-Format Processing**: Supports `.pdf`, `.png`, `.jpg`, `.bmp`, `.tiff`, `.txt`, `.md`, `.csv`.
- **Intelligent OCR**: Uses Tesseract OCR for text extraction from images and scanned files.
- **AI Document Classification**: Automatically categorizes files into *Invoice & Receipt*, *Contract & Policy*, *Financial Report*, *Technical Proposal*, or *Data Spreadsheet*.
- **Vector RAG Engine**: Generates embeddings via Google Gemini `text-embedding-004` and performs normalized cosine similarity search to drive context-grounded AI answers (`gemini-2.0-flash`).
- **Enterprise Observability**: Emits structured JSON logs via `structlog` and collects live, route-normalized metrics at a protected `/admin/metrics` endpoint.
- **High-Aesthetic UI**: ITGate brand visual design (`#0044EB` primary blue, `#D5E0EB` surface background, Inter font) featuring a drag-and-drop paper tray, paper cards with page-fold details, and global status interceptors.

---

## 🚀 Quick Start Guide

### Prerequisites
- **Python**: `3.11`
- **PostgreSQL**: `15+` (or Docker)
- **Tesseract OCR**: Installed on host system (or via Docker container)

### 1. Local Setup

```powershell
# 1. Clone the repository and navigate into it
cd C:\Users\Isra\doc-automation-saas

# 2. Activate virtual environment
.\venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy environment template and configure secrets
cp .env.example .env
```

Edit `.env` to configure your `DATABASE_URL`, `GEMINI_API_KEY`, and `ADMIN_TOKEN`.

### 2. Launching the Application

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open your browser at **[http://localhost:8000](http://localhost:8000)** to access the web application.

---

## 🐳 Docker Deployment

To launch the full production stack (FastAPI web server + PostgreSQL database):

```bash
docker-compose up --build
```

The container automatically installs system dependencies (`tesseract-ocr`, `libpq-dev`, `libmagic1`) and exposes the web app at `http://localhost:8000`.

---

## 📚 Interactive API Documentation

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 📊 Core API Endpoints Summary

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :---: |
| `POST` | `/auth/register` | Register a new user account | ❌ No |
| `POST` | `/auth/login` | Login and receive Bearer JWT access token | ❌ No |
| `GET` | `/auth/me` | Return authenticated user details | ✅ Bearer JWT |
| `POST` | `/upload` | Upload & classify document (bounded 10MB limit) | ✅ Bearer JWT |
| `GET` | `/documents` | List user's documents & categories | ✅ Bearer JWT |
| `GET` | `/extract/{doc_id}` | Extract structured AI summary | ✅ Bearer JWT |
| `POST` | `/ask/{doc_id}` | Ask AI question using vector RAG | ✅ Bearer JWT |
| `GET` | `/chat-history/{doc_id}` | Retrieve Q&A history per document | ✅ Bearer JWT |
| `DELETE` | `/documents/{doc_id}` | Delete document and associated chunks | ✅ Bearer JWT |
| `GET` | `/admin/metrics` | Retrieve live JSON route latency & error metrics | 🔒 Admin Token |

---

## 🧪 Automated Testing

Run the test suite (37 unit & integration tests):

```powershell
python -m pytest tests/ --verbose
```

---

## 🛡️ Security & Operational Governance
- **JWT & Passwords**: Passwords hashed with `bcrypt`. JWT tokens expire according to `ACCESS_TOKEN_EXPIRE_MINUTES`.
- **Input Validation**: Bounded 64KB streaming size limit (max 10MB) and magic-byte file header verification.
- **Schema Safety**: Operational rules defined in `.agents/AGENTS.md`.
