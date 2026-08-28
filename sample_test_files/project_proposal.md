# ITGate Document Automation System — Architecture Proposal

## 1. Project Goal
Deploy an enterprise-grade document automation and RAG query portal for processing invoices, contracts, and internal documentation.

## 2. Core Features
- **File Ingestion**: Supports PDF, PNG, JPG, TXT, MD, CSV.
- **Security**: JWT authentication, bcrypt password hashing, magic byte file header verification.
- **AI Analytics**: Powered by Google Gemini 2.0 Flash and text-embedding-004.
- **Observability**: Live structured JSON logging and /admin/metrics endpoint.

## 3. SLA Targets
- Upload & Chunking Latency: < 1.5 seconds per file.
- AI Chat Response Time: < 3.0 seconds per query.
- API Uptime Commitment: 99.9%