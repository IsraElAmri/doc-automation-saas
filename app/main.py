"""
Document Automation SaaS — FastAPI Application
Endpoints: /auth/register, /auth/login, /auth/me, /upload, /extract, /ask, /documents, /chat-history
Includes vector-similarity search RAG, rate-limiting, streaming size limits, magic-byte validation, and threadpool concurrency.
"""
import os
import shutil
import uuid
import json
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from app.database import engine, get_db, Base
from app.models import User, Document, DocumentChunk, ChatHistory
from app.ocr_utils import extract_text_from_file, chunk_text, detect_file_type, validate_file_header, classify_document
from app.llm_utils import (
    extract_document_info,
    answer_question_rag,
    generate_embedding,
    retrieve_top_k_chunks,
)
from app.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
)
from app.rate_limiter import limiter
from app.logging_config import configure_logging, get_logger
from app import metrics
from config.settings import UPLOAD_DIR, CORS_ORIGINS, MAX_UPLOAD_SIZE_MB, ADMIN_TOKEN

# ── Logging ───────────────────────────────────────────────────────────
configure_logging()
logger = get_logger(__name__)

# ── Create tables (idempotent) ────────────────────────────────────────
Base.metadata.create_all(bind=engine)

# ── FastAPI app ───────────────────────────────────────────────────────
app = FastAPI(
    title="Document Automation SaaS",
    description="Upload documents, extract key info with Gemini AI, and chat about your documents using Vector RAG.",
    version="1.0.0",
)

# Rate limiter setup
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware with explicit configured origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start_time) * 1000

    # Extract route path if possible (to avoid cardinality explosion on IDs)
    route_path = request.url.path
    if request.scope.get("route"):
        route_path = request.scope["route"].path

    metrics.record(request.method, route_path, response.status_code, duration_ms)
    
    # Try to grab user ID from auth middleware state if present, else None
    user_id = getattr(request.state, "user_id", None)
    
    logger.info(
        "request",
        route=route_path,
        method=request.method,
        status=response.status_code,
        duration_ms=round(duration_ms, 2),
        user_id=user_id
    )
    return response

# ── Static files & frontend ───────────────────────────────────────────
_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if _STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


# ── Pydantic Schemas ──────────────────────────────────────────────────

class UserRegister(BaseModel):
    email: str
    password: str


class UserLogin(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    email: str


class UserOut(BaseModel):
    id: int
    email: str
    created_at: datetime


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    document_id: int
    question: str
    answer: str


class DocumentOut(BaseModel):
    id: int
    filename: str
    file_type: str | None
    category: str | None = "General Document"
    text_length: int
    chunks_count: int
    created_at: datetime


class UploadResponse(BaseModel):
    message: str
    document_id: int
    filename: str
    file_type: str
    category: str | None = "General Document"
    text_length: int
    chunks_created: int


class ExtractResponse(BaseModel):
    document_id: int
    filename: str
    extracted_info: str


class ChatEntry(BaseModel):
    id: int
    question: str
    answer: str
    timestamp: datetime


class ChatHistoryResponse(BaseModel):
    document_id: int
    chat_count: int
    chats: list[ChatEntry]


# ── Admin Endpoints ──────────────────────────────────────────────────

@app.get("/admin/metrics")
def get_metrics(request: Request):
    """Return application metrics. Secured via ADMIN_TOKEN in Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    
    token = auth_header.split(" ")[1]
    # Use constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(token, ADMIN_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid admin token")
        
    return metrics.snapshot()


# ── Auth Endpoints ───────────────────────────────────────────────────

@app.post("/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def register_user(request: Request, body: UserRegister, db: Session = Depends(get_db)):
    """Register a new user account (rate-limited by IP)."""
    clean_email = body.email.strip().lower()
    if not clean_email or "@" not in clean_email:
        raise HTTPException(status_code=400, detail="Invalid email address")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    existing_user = db.query(User).filter(User.email == clean_email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_pwd = hash_password(body.password)
    new_user = User(email=clean_email, hashed_password=hashed_pwd)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    access_token = create_access_token(data={"sub": str(new_user.id)})
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=new_user.id,
        email=new_user.email,
    )


@app.post("/auth/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def login_user(request: Request, body: UserLogin, db: Session = Depends(get_db)):
    """Authenticate email and password, returning JWT access token (rate-limited by IP)."""
    clean_email = body.email.strip().lower()
    user = db.query(User).filter(User.email == clean_email).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    access_token = create_access_token(data={"sub": str(user.id)})
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        email=user.email,
    )


@app.get("/auth/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    """Return profile of the current authenticated user."""
    return UserOut(
        id=current_user.id,
        email=current_user.email,
        created_at=current_user.created_at,
    )


# ── Frontend & Info Endpoints ─────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def read_root():
    """Serve the frontend UI."""
    index_path = _STATIC_DIR / "index.html"
    if index_path.is_file():
        return HTMLResponse(content=index_path.read_text(encoding="utf-8"), status_code=200)
    return HTMLResponse(
        content="<h1>DocAI API is running</h1><p>Visit <a href='/docs'>/docs</a> for Swagger UI.</p>",
        status_code=200,
    )


@app.get("/api")
def api_info():
    """API landing page with endpoint directory."""
    return {
        "message": "📄 Document Automation SaaS API",
        "version": "1.0.0",
        "endpoints": {
            "POST /auth/register": "Register a new user account",
            "POST /auth/login": "Authenticate user and get JWT token",
            "GET /auth/me": "Get current user profile",
            "POST /upload": "Upload a document with streaming size limit & magic-byte validation",
            "GET /extract/{document_id}": "Extract key info using Gemini AI",
            "POST /ask/{document_id}": "Ask a question using vector similarity search RAG",
            "GET /documents": "List uploaded documents for current user",
            "GET /chat-history/{document_id}": "View chat history for a document",
        },
    }


# ── Protected Document Endpoints ──────────────────────────────────────

@app.post("/upload", response_model=UploadResponse)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a document with:
    1. Early streaming chunk byte-counter size limit enforcement (MAX_UPLOAD_SIZE_MB).
    2. Isolated throwaway magic-byte content validation.
    3. Threadpool non-blocking text extraction and vector embedding generation.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    safe_filename = os.path.basename(file.filename)
    file_type = detect_file_type(safe_filename)
    if file_type == "unknown":
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Supported: PDF, images (jpg/png/bmp/tiff/webp), text (txt/md/csv)",
        )

    max_bytes = int(MAX_UPLOAD_SIZE_MB * 1024 * 1024)

    # Pre-check Content-Length header if present
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File size exceeds maximum limit of {MAX_UPLOAD_SIZE_MB}MB",
        )

    unique_filename = f"{uuid.uuid4().hex}_{safe_filename}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)

    try:
        # Stream file in 64KB chunks with running byte counter
        bytes_read = 0
        with open(file_path, "wb") as buffer:
            while True:
                chunk_bytes = await file.read(64 * 1024)
                if not chunk_bytes:
                    break
                bytes_read += len(chunk_bytes)
                if bytes_read > max_bytes:
                    buffer.close()
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=f"File size exceeds maximum limit of {MAX_UPLOAD_SIZE_MB}MB",
                    )
                buffer.write(chunk_bytes)

        # Safe to validate after write: streaming abort above already bounds the file to
        # ≤ MAX_UPLOAD_SIZE_MB on disk, so this is a content-format check, not a size check.
        valid_header = await run_in_threadpool(validate_file_header, file_path, file_type)
        if not valid_header:
            if os.path.exists(file_path):
                os.remove(file_path)
            raise HTTPException(
                status_code=400,
                detail="File content does not match expected format or is corrupt.",
            )

        logger.info("File saved and validated: %s (%d bytes) for user #%d", file_path, bytes_read, current_user.id)

        # Offload blocking text extraction to threadpool
        extracted_text = await run_in_threadpool(extract_text_from_file, file_path)
        logger.info("Extracted %d characters from '%s'", len(extracted_text), safe_filename)

        category = classify_document(extracted_text, safe_filename)

        db_document = Document(
            user_id=current_user.id,
            filename=safe_filename,
            file_path=file_path,
            file_type=file_type,
            category=category,
            extracted_text=extracted_text,
        )
        db.add(db_document)
        db.commit()
        db.refresh(db_document)

        chunks = chunk_text(extracted_text)
        for idx, chunk in enumerate(chunks):
            # Offload vector embedding call to threadpool
            emb = await run_in_threadpool(generate_embedding, chunk, False)
            db_chunk = DocumentChunk(
                document_id=db_document.id,
                chunk_text=chunk,
                chunk_index=idx,
                embedding_data=json.dumps(emb) if emb else None,
            )
            db.add(db_chunk)
        db.commit()
        logger.info("Created %d chunks with vector embeddings for document #%d (%s)", len(chunks), db_document.id, category)

        return UploadResponse(
            message="Document uploaded and processed successfully",
            document_id=db_document.id,
            filename=file.filename,
            file_type=file_type,
            category=category,
            text_length=len(extracted_text),
            chunks_created=len(chunks),
        )

    except HTTPException:
        if os.path.exists(file_path) and not os.path.isdir(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass
        db.rollback()
        raise
    except Exception as e:
        if os.path.exists(file_path) and not os.path.isdir(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass
        db.rollback()
        logger.exception("Upload failed for '%s'", file.filename)
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")


@app.get("/extract/{document_id}", response_model=ExtractResponse)
@limiter.limit("10/minute")
async def extract_info(
    request: Request,
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Extract key information using Gemini AI with 30s timeout and threadpool concurrency.
    Rate-limited by user_id.
    """
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == current_user.id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if not document.extracted_text or not document.extracted_text.strip():
        raise HTTPException(status_code=400, detail="Document has no extracted text to analyze")

    try:
        extracted_info = await run_in_threadpool(extract_document_info, document.extracted_text)
        return ExtractResponse(
            document_id=document_id,
            filename=document.filename,
            extracted_info=extracted_info,
        )
    except TimeoutError as e:
        db.rollback()
        raise HTTPException(status_code=504, detail=f"Gemini extraction timed out: {e}")
    except RuntimeError as e:
        db.rollback()
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/ask/{document_id}", response_model=AskResponse)
@limiter.limit("10/minute")
async def ask_question(
    request: Request,
    document_id: int,
    body: AskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Ask a question about a document using vector similarity search RAG.
    Offloads heavy calls to threadpool, handles 30s timeouts with HTTP 504 & db.rollback().
    """
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == current_user.id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if not document.extracted_text or not document.extracted_text.strip():
        raise HTTPException(status_code=400, detail="Document has no content to query")

    try:
        chunks = (
            db.query(DocumentChunk)
            .filter(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
            .all()
        )

        candidate_chunks = []
        dirty_backfill = False

        for chunk in chunks:
            emb = None
            if chunk.embedding_data:
                try:
                    emb = json.loads(chunk.embedding_data)
                except Exception:
                    emb = None

            # On-the-fly backfill for legacy/missing embeddings
            if not emb:
                logger.info("On-the-fly embedding backfill generated for chunk #%d", chunk.id)
                emb = await run_in_threadpool(generate_embedding, chunk.chunk_text, False)
                if emb:
                    chunk.embedding_data = json.dumps(emb)
                    dirty_backfill = True
                else:
                    logger.warning("Failed on-the-fly embedding backfill for chunk #%d", chunk.id)

            candidate_chunks.append((chunk.chunk_text, emb))

        # Commit #1: Backfilled chunk embeddings saved BEFORE calling Gemini API
        if dirty_backfill:
            db.commit()

        # Generate RETRIEVAL_QUERY vector embedding for user question
        question_embedding = await run_in_threadpool(generate_embedding, body.question, True)

        # Retrieve Top-3 relevant chunks using normalized cosine similarity
        top_chunks = retrieve_top_k_chunks(candidate_chunks, question_embedding, k=3)

        # Offload Gemini RAG answer generation to threadpool with 30s timeout
        answer = await run_in_threadpool(answer_question_rag, top_chunks, body.question)

        # Commit #2: Save ChatHistory ONLY AFTER Gemini successfully returns
        chat = ChatHistory(
            document_id=document_id,
            user_question=body.question,
            ai_response=answer,
        )
        db.add(chat)
        db.commit()

        return AskResponse(
            document_id=document_id,
            question=body.question,
            answer=answer,
        )

    except TimeoutError as e:
        db.rollback()
        raise HTTPException(status_code=504, detail=f"Gemini API request timed out: {e}")
    except RuntimeError as e:
        db.rollback()
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.exception("Ask failed for document #%d", document_id)
        raise HTTPException(status_code=500, detail=f"Failed to generate answer: {e}")


@app.get("/documents")
def list_documents(
    skip: int = Query(0, ge=0, description="Number of documents to skip"),
    limit: int = Query(50, ge=1, le=200, description="Max documents to return"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all uploaded documents belonging to the authenticated user."""
    query = db.query(Document).filter(Document.user_id == current_user.id)
    total = query.count()
    documents = query.order_by(Document.created_at.desc()).offset(skip).limit(limit).all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "documents": [
            DocumentOut(
                id=doc.id,
                filename=doc.filename,
                file_type=doc.file_type,
                category=doc.category or "General Document",
                text_length=len(doc.extracted_text) if doc.extracted_text else 0,
                chunks_count=len(doc.chunks),
                created_at=doc.created_at,
            ).model_dump()
            for doc in documents
        ],
    }


@app.get("/chat-history/{document_id}", response_model=ChatHistoryResponse)
def get_chat_history(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve all chat Q&A history for a specific document owned by the user."""
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == current_user.id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    chats = (
        db.query(ChatHistory)
        .filter(ChatHistory.document_id == document_id)
        .order_by(ChatHistory.created_at.asc())
        .all()
    )

    return ChatHistoryResponse(
        document_id=document_id,
        chat_count=len(chats),
        chats=[
            ChatEntry(
                id=chat.id,
                question=chat.user_question,
                answer=chat.ai_response,
                timestamp=chat.created_at,
            )
            for chat in chats
        ],
    )


@app.delete("/documents/{document_id}")
def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a document and all its chunks and chat history (owner only)."""
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == current_user.id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if document.file_path and os.path.exists(document.file_path):
        try:
            os.remove(document.file_path)
        except OSError:
            pass

    db.delete(document)
    db.commit()

    return {"message": f"Document '{document.filename}' deleted successfully"}


# ── Run with uvicorn ──────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)