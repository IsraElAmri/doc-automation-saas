# Production Deployment & Operations Guide

This guide covers productionizing the Document Automation SaaS, including security, monitoring, database backups, and scaling.

---

## 1. Environment & Secrets Management

Before deploying, ensure you configure the environment variables correctly. 
Copy `.env.example` to `.env` on your production server:

```bash
cp .env.example .env
```

### Critical Secrets
- `SECRET_KEY`: Must be a long, cryptographically secure random string used to sign JWT tokens. Do not reuse test keys.
- `ADMIN_TOKEN`: A secure token string used to authorize access to the `/admin/metrics` endpoint.
- `GEMINI_API_KEY`: Your live Google Gemini AI project key.

---

## 2. Docker Swarm / Compose Deployment

The application is containerized for seamless Linux deployment.

```bash
# Build and start services in detached mode
docker-compose up --build -d

# Check live container logs
docker-compose logs -f
```

The stack includes:
- **FastAPI App Container**: Runs the Python web server on port `8000`.
- **PostgreSQL Container**: Runs the primary database engine mapped to port `5432`.

---

## 3. Database Backup Strategy

Data persistence relies on the PostgreSQL volume `pgdata`. Implement automated backups using `pg_dump` via a cron job on your host server.

**Automated Daily Backup Script (`backup.sh`)**:
```bash
#!/bin/bash
TIMESTAMP=$(date +%F)
BACKUP_DIR="/var/backups/doc_automation"

mkdir -p $BACKUP_DIR
docker exec -t doc_automation_db pg_dumpall -c -U postgres > "$BACKUP_DIR/db_dump_$TIMESTAMP.sql"
```

*Recommendation*: Store backups in AWS S3 or Google Cloud Storage using automated lifecycle policies.

---

## 4. Security Audit & Configuration

### A. JWT Expiration
By default, access tokens expire according to `ACCESS_TOKEN_EXPIRE_MINUTES` in the `.env` file (default: 60 minutes). Adjust this based on your compliance requirements.

### B. CORS Configuration
In `app/main.py`, the `CORSMiddleware` is configured to allow all origins (`allow_origins=["*"]`) for development. 
**Before Production:** Restrict this to your actual front-end domain:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-production-domain.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
```

### C. Rate Limiting
Rate limiting is enforced globally (e.g., `5/minute` on `/auth/register` and `20/minute` on `/upload`). These prevent brute-force attacks and control API costs. Adjust limits in `app/main.py` using `@limiter.limit()`.

---

## 5. Health Monitoring & Error Tracking

### A. Sentry Integration
To capture unhandled exceptions and performance bottlenecks, install the Sentry SDK:
```bash
pip install sentry-sdk
```

Add the following to `app/main.py` directly under your imports:
```python
import sentry_sdk

sentry_sdk.init(
    dsn=os.environ.get("SENTRY_DSN"),
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
)
```
Ensure `SENTRY_DSN` is populated in your `.env`.

### B. Load & Stress Testing
We recommend using **Locust** or **k6** to simulate user traffic against the API before a major release. Ensure the threadpool efficiently handles blocking OCR and Gemini requests under concurrent load without exhausting the ASGI event loop.

---

## 6. CI/CD Pipeline
A GitHub Actions workflow is provided in `.github/workflows/ci.yml`. It runs automatically on pull requests and commits to `main`, validating:
- Dependencies.
- Pytest integration coverage (`tests/`).
- Docker build stability.
