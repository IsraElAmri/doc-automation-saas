"""
Centralized application settings loaded from environment variables / .env file.
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()


# ── Database ──────────────────────────────────────────────────────────
DATABASE_URL: str = os.getenv("DB_URL", "") or os.getenv("DATABASE_URL", "")
if not DATABASE_URL:
    # Allow fallback ONLY during pytest execution
    if "pytest" in sys.modules or os.getenv("TESTING") == "1":
        DATABASE_URL = "sqlite:///./test_doc_automation.db"
    else:
        raise RuntimeError("DB_URL environment variable is required and must be set.")

# ── JWT Authentication Secrets ─────────────────────────────────────────
SECRET_KEY: str = os.getenv("SECRET_KEY", "")
if not SECRET_KEY and "pytest" not in sys.modules and os.getenv("TESTING") != "1":
    raise RuntimeError("SECRET_KEY environment variable is required and must be set.")
elif not SECRET_KEY:
    SECRET_KEY = "pytest_secret_key_for_testing_only"

JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", str(60 * 24)))

# ── Admin & Observability ────────────────────────────────────────────
ADMIN_TOKEN: str = os.getenv("ADMIN_TOKEN", "")
if not ADMIN_TOKEN and "pytest" not in sys.modules and os.getenv("TESTING") != "1":
    raise RuntimeError("ADMIN_TOKEN environment variable is required and must be set.")
elif not ADMIN_TOKEN:
    ADMIN_TOKEN = "pytest_admin_token_for_testing_only"

# Known limitation: ADMIN_TOKEN is a static shared secret with no expiry or rotation.
# Treat it like a root password — store only in .env, never commit, rotate manually on breach.
LOG_FORMAT: str = os.getenv("LOG_FORMAT", "json")  # "json" (prod) | "pretty" (dev/test)

# ── CORS Settings ─────────────────────────────────────────────────────
_raw_cors = os.getenv("CORS_ALLOWED_ORIGINS", "*")
if _raw_cors.strip() == "*":
    CORS_ORIGINS: list[str] = ["*"]
else:
    CORS_ORIGINS: list[str] = [origin.strip() for origin in _raw_cors.split(",") if origin.strip()]

# ── Gemini API & Timeout ──────────────────────────────────────────────
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
GEMINI_TIMEOUT_SECONDS: float = float(os.getenv("GEMINI_TIMEOUT_SECONDS", "30.0"))
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

# ── File Upload & Validation Limits ───────────────────────────────────
UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
MAX_UPLOAD_SIZE_MB: float = float(os.getenv("MAX_UPLOAD_SIZE_MB", "10.0"))

# ── Tesseract OCR ─────────────────────────────────────────────────────
_TESSERACT_WIN_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if sys.platform == "win32" and os.path.exists(_TESSERACT_WIN_PATH):
    TESSERACT_CMD: str = _TESSERACT_WIN_PATH
else:
    TESSERACT_CMD: str = "tesseract"  # assumes it's on PATH (Linux/Docker)

# ── Chunking defaults ────────────────────────────────────────────────
CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "50"))

if not (0 <= CHUNK_OVERLAP < CHUNK_SIZE):
    raise RuntimeError(
        f"CHUNK_OVERLAP ({CHUNK_OVERLAP}) must satisfy 0 <= CHUNK_OVERLAP < CHUNK_SIZE ({CHUNK_SIZE}). "
        "Fix your environment variables (default: CHUNK_SIZE=500, CHUNK_OVERLAP=50)."
    )
