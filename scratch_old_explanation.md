# Document Automation SaaS — Complete Code & Architecture Explanation

> This document explains **every single concept, every file, and every line of code** in this project from the ground up, as if the reader has zero prior knowledge.

---

## Table of Contents
1. [What This Project Is](#1-what-this-project-is)
2. [Key Concepts Explained](#2-key-concepts-explained)
3. [Project Architecture](#3-project-architecture)
4. [File-by-File Code Walkthrough](#4-file-by-file-code-walkthrough)
5. [How All Parts Connect](#5-how-all-parts-connect)
6. [Complete Flow Examples](#6-complete-flow-examples)
7. [Detailed Summary For Your Agent](#7-detailed-summary-for-your-agent)

---

# 1. What This Project Is

This is a **Document Automation SaaS** (Software as a Service) backend. It does 5 things:

1. **Accepts file uploads** (PDFs, images, text files) via a web API
2. **Extracts text** from those files using OCR (for images) or PDF parsing
3. **Splits the text into chunks** for later retrieval
4. **Uses Google's Gemini AI** to analyze documents and answer questions
5. **Stores everything in a PostgreSQL database** (documents, chunks, chat history)

Users interact with it through a **web browser UI** or by sending HTTP requests to the API.

---

# 2. Key Concepts Explained

### What is an API?
An **API** (Application Programming Interface) is a set of URLs (called "endpoints") that a program exposes so other programs (or browsers) can send it data and get responses. Think of it like a restaurant menu: you pick an item (endpoint), send your order (request), and get food back (response).

Example: Sending a file to `POST /upload` → the server processes it → sends back `{"document_id": 5}`.

### What is FastAPI?
**FastAPI** is a Python framework (a pre-built toolkit) for building APIs. It handles:
- Receiving HTTP requests (GET, POST, DELETE)
- Routing them to the right Python function
- Validating input data
- Returning JSON responses
- Auto-generating interactive API docs at `/docs`

### What is an ORM (SQLAlchemy)?
An **ORM** (Object-Relational Mapper) lets you interact with a database using Python classes instead of writing raw SQL. **SQLAlchemy** is Python's most popular ORM.

Instead of writing `INSERT INTO documents (filename) VALUES ('report.pdf')`, you write:
```python
doc = Document(filename="report.pdf")
db.add(doc)
db.commit()
```

### What is PostgreSQL?
**PostgreSQL** is a database — a structured storage system for data. Data is organized into **tables** (like spreadsheets). Each table has **columns** (fields) and **rows** (records). This project has 3 tables:
- `documents` — stores uploaded file metadata and extracted text
- `document_chunks` — stores pieces of each document's text
- `chat_history` — stores user questions and AI answers

### What is OCR (Tesseract)?
**OCR** (Optical Character Recognition) is technology that reads text from images. **Tesseract** is an open-source OCR engine by Google. You give it a photo of text → it returns the actual text characters.

### What is an LLM (Gemini)?
An **LLM** (Large Language Model) is an AI that understands and generates text. **Gemini** is Google's LLM. We send it text (a "prompt") and it sends back intelligent responses — like analyzing a document or answering a question.

### What is RAG?
**RAG** (Retrieval-Augmented Generation) is a technique where:
1. You **split** a document into small pieces ("chunks")
2. When a user asks a question, you **retrieve** the relevant chunks
3. You send those chunks + the question to the LLM
4. The LLM **generates** an answer using ONLY the provided chunks

This prevents the LLM from hallucinating (making things up) because it can only use document content.

### What is Docker?
**Docker** packages your application + all its dependencies into a portable "container" that runs identically on any machine. Like a shipping container for software.

### What is an `.env` File?
A `.env` file stores **secret configuration** (API keys, passwords) outside your code. This way, secrets never get committed to version control.

---

# 3. Project Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      USER (Browser)                         │
│                 http://localhost:8000                        │
└──────────────────────┬──────────────────────────────────────┘
                       │  HTTP Requests
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Server                            │
│                    (app/main.py)                             │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐  │
│  │ /upload  │  │ /extract │  │  /ask    │  │ /documents │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └─────┬──────┘  │
│       │              │             │              │         │
│       ▼              ▼             ▼              ▼         │
│  ┌─────────┐   ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │OCR Utils│   │LLM Utils │  │LLM Utils │  │ Database │   │
│  │(extract)│   │(extract) │  │(RAG Q&A) │  │ (query)  │   │
│  └────┬────┘   └────┬─────┘  └────┬─────┘  └─────┬────┘   │
└───────┼──────────────┼─────────────┼──────────────┼────────┘
        │              │             │              │
        ▼              ▼             ▼              ▼
┌──────────────┐ ┌──────────────┐  ┌──────────────────────┐
│  Tesseract   │ │  Gemini API  │  │  PostgreSQL Database  │
│  OCR Engine  │ │ (Google AI)  │  │  ┌─────────────────┐  │
│  (local)     │ │ (cloud)      │  │  │ documents       │  │
└──────────────┘ └──────────────┘  │  │ document_chunks │  │
                                   │  │ chat_history    │  │
                                   │  └─────────────────┘  │
                                   └──────────────────────┘
```

### Data Flow Summary:
1. **Upload**: File → Save to disk → Extract text (OCR/PDF) → Split into chunks → Store in PostgreSQL
2. **Extract**: Fetch document from DB → Send text to Gemini → Return structured analysis
3. **Ask**: Fetch chunks from DB → Send chunks + question to Gemini → Save Q&A → Return answer
4. **Documents**: Query PostgreSQL → Return list
5. **Chat History**: Query PostgreSQL → Return past Q&A pairs

---

# 4. File-by-File Code Walkthrough

---

## 4.1 `.env` — Environment Variables

```env
GEMINI_API_KEY=AQ.Ab8RN6J...
DB_URL=postgresql://postgres:israPOSTGRESQL@localhost/doc_automation
```

**Line 1**: `GEMINI_API_KEY` — your secret key to authenticate with Google's Gemini AI service. Without this, the API would reject your requests. It starts with `AQ.` because it's an API Studio key.

**Line 2**: `DB_URL` — the "connection string" for PostgreSQL. Let's break it apart:
- `postgresql://` — the database type (protocol)
- `postgres` — the database username
- `israPOSTGRESQL` — the password for that user
- `@localhost` — the database server is running on this same machine
- `/doc_automation` — the name of the specific database to connect to

---

## 4.2 `config/settings.py` — Centralized Configuration

This file loads ALL configuration from the `.env` file and makes it available to the rest of the application as Python variables.

```python
"""
Centralized application settings loaded from environment variables / .env file.
"""
```
**Lines 1-3**: A "docstring" — a description of what this file does. Purely for documentation.

```python
import os
import sys
from dotenv import load_dotenv
```
**Line 4**: `import os` — Python's built-in module for interacting with the operating system (reading environment variables, checking file paths, etc.).

**Line 5**: `import sys` — Python's module for system-specific parameters. We use `sys.platform` to detect if we're on Windows vs Linux.

**Line 6**: `from dotenv import load_dotenv` — imports the `load_dotenv` function from the `python-dotenv` package. This function reads the `.env` file and loads its contents into environment variables.

```python
load_dotenv()
```
**Line 8**: Actually executes the loading. After this line, `os.getenv("GEMINI_API_KEY")` will return the value from the `.env` file.

```python
DATABASE_URL: str = os.getenv(
    "DB_URL",
    "postgresql://postgres:israPOSTGRESQL@localhost:5432/doc_automation",
)
```
**Lines 12-15**: Reads the `DB_URL` environment variable. The `: str` is a **type hint** — it tells developers (and tools) this variable holds a string. `os.getenv("DB_URL", "fallback_value")` means: "get `DB_URL` from environment, but if it doesn't exist, use the fallback value instead."

```python
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
```
**Line 18**: Loads the Gemini API key. Defaults to empty string if not set.

**Line 19**: Loads which Gemini model to use. Defaults to `gemini-3.6-flash` — Google's latest fast model.

```python
UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
```
**Line 22**: Where uploaded files will be saved on disk. Defaults to a folder called `uploads`.

**Line 23**: `os.makedirs` creates that folder. `exist_ok=True` means "don't crash if the folder already exists."

```python
_TESSERACT_WIN_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if sys.platform == "win32" and os.path.exists(_TESSERACT_WIN_PATH):
    TESSERACT_CMD: str = _TESSERACT_WIN_PATH
else:
    TESSERACT_CMD: str = "tesseract"
```
**Lines 27-31**: Tesseract OCR needs to know where its executable binary is.
- On **Windows**, it's typically installed at `C:\Program Files\Tesseract-OCR\tesseract.exe`
- On **Linux/Docker**, it's just `tesseract` on the system PATH
- `sys.platform == "win32"` checks if we're on Windows
- `os.path.exists(...)` checks if the file actually exists at that path
- The `r"..."` prefix means "raw string" — backslashes are treated literally, not as escape characters

```python
CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "50"))
```
**Lines 34-35**: Configuration for text chunking.
- `CHUNK_SIZE = 500` — each chunk will be ~500 characters
- `CHUNK_OVERLAP = 50` — consecutive chunks share 50 characters of overlap so no information is lost at chunk boundaries

---

## 4.3 `app/database.py` — Database Connection

This file creates the connection to PostgreSQL and defines how the app gets database sessions.

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config.settings import DATABASE_URL
```
**Line 4**: `create_engine` — a SQLAlchemy function that creates a database connection manager (the "engine"). Think of it as opening a channel to the database.

**Line 5**: `sessionmaker` — a factory that creates database **sessions**. A session is like a "workspace" where you read/write data, then commit (save) or rollback (undo). `declarative_base` — creates a base class that all our database models (tables) will inherit from.

**Line 6**: Imports the database URL string from our settings file.

```python
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)
```
**Lines 8-13**: Creates the database engine with connection pooling:
- `DATABASE_URL` — where to connect (postgres://...)
- `pool_pre_ping=True` — before giving a connection to the app, ping the database to make sure the connection is still alive. This prevents "connection closed" errors.
- `pool_size=5` — keep 5 connections open and ready to reuse (avoids the overhead of opening a new connection every request)
- `max_overflow=10` — if all 5 are busy, allow up to 10 extra temporary connections

```python
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
```
**Line 15**: Creates a session factory.
- `autocommit=False` — changes aren't saved automatically; you must call `db.commit()` explicitly
- `autoflush=False` — pending changes aren't sent to the database until you explicitly request it
- `bind=engine` — these sessions use our engine (our PostgreSQL connection)

```python
Base = declarative_base()
```
**Line 17**: Creates the **base class** for all database models. Every table class will inherit from `Base`. SQLAlchemy uses this to track all models and create tables.

```python
def get_db():
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```
**Lines 20-26**: A **FastAPI dependency** — a special function that FastAPI calls automatically before each request.
- `db = SessionLocal()` — creates a new database session
- `yield db` — gives that session to the endpoint function (the `yield` keyword makes this a "generator" — it pauses here, lets the endpoint run, then continues)
- `finally: db.close()` — after the endpoint finishes (or crashes), **always** close the session to return the connection to the pool. `finally` runs no matter what, even if an error occurred.

**Why `yield` instead of `return`?** Because `yield` lets us run cleanup code (`db.close()`) AFTER the endpoint function finishes using the session.

---

## 4.4 `app/models.py` — Database Table Definitions

This file defines the structure of our 3 database tables as Python classes.

```python
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, LargeBinary
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base
```
**Line 4**: Imports column types from SQLAlchemy:
- `Column` — defines a column in a table
- `Integer` — whole numbers (1, 2, 3...)
- `String(255)` — text with a max length
- `Text` — unlimited-length text
- `DateTime` — date and time values
- `ForeignKey` — a reference to another table's column
- `LargeBinary` — binary data (for future embeddings)

**Line 5**: `relationship` — defines how tables are linked to each other in Python (so you can do `document.chunks` to get all chunks belonging to a document).

**Line 6**: Python's datetime module for timestamps.

**Line 7**: Imports `Base` so our models can inherit from it.

### Document Model (the `documents` table)

```python
class Document(Base):
    __tablename__ = "documents"
```
**Lines 10-11**: Defines a Python class `Document` that maps to a database table called `documents`. `__tablename__` tells SQLAlchemy what to name the table in PostgreSQL.

```python
    id = Column(Integer, primary_key=True, index=True)
```
**Line 13**: The **primary key** — a unique identifier for each row. `primary_key=True` means this column uniquely identifies each document. `index=True` creates a database index for faster lookups. Auto-increments (1, 2, 3...).

```python
    filename = Column(String(255), nullable=False)
```
**Line 14**: Stores the original filename (e.g., "report.pdf"). `String(255)` limits it to 255 characters. `nullable=False` means this field is required — you can't save a document without a filename.

```python
    file_path = Column(String(500), nullable=False)
```
**Line 15**: The actual path on disk where the file was saved (e.g., "uploads/abc123_report.pdf").

```python
    file_type = Column(String(20), nullable=True)
```
**Line 16**: The type of file: "pdf", "image", or "txt". `nullable=True` means this field is optional.

```python
    extracted_text = Column(Text, nullable=True)
```
**Line 17**: The full text extracted from the document via OCR or PDF parsing. `Text` type has no length limit.

```python
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
```
**Line 18**: Timestamp of when the document was uploaded. `default=lambda: datetime.now(timezone.utc)` means "if no value is provided, use the current UTC time." The `lambda:` creates a function that's called each time a new row is created (so each row gets its own timestamp, not the same one).

```python
    chunks = relationship(
        "DocumentChunk", back_populates="document", cascade="all, delete-orphan"
    )
```
**Lines 20-22**: Defines a **relationship** — this isn't a database column, it's a Python convenience. `document.chunks` will return a list of all `DocumentChunk` objects belonging to this document.
- `back_populates="document"` — the reverse link: `chunk.document` returns the parent Document
- `cascade="all, delete-orphan"` — if you delete a Document, automatically delete all its chunks too

```python
    chat_history = relationship(
        "ChatHistory", back_populates="document", cascade="all, delete-orphan"
    )
```
**Lines 23-25**: Same pattern — `document.chat_history` returns all chat Q&A entries for this document.

### DocumentChunk Model (the `document_chunks` table)

```python
class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
```
**Line 32**: `ForeignKey("documents.id")` — this column references the `id` column of the `documents` table. This creates a **parent-child relationship**: each chunk belongs to exactly one document. `ondelete="CASCADE"` — if the parent document is deleted from the database, automatically delete all its chunks too (database-level enforcement).

```python
    chunk_text = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    embedding = Column(LargeBinary, nullable=True)
```
**Line 33**: The actual text content of this chunk.

**Line 34**: The position of this chunk in the document (0, 1, 2, 3...) — used to maintain order.

**Line 35**: Reserved for future use — would store vector embeddings for semantic search.

### ChatHistory Model (the `chat_history` table)

```python
class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    user_question = Column(Text, nullable=False)
    ai_response = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
```
**Lines 41-48**: Stores every question a user asks and every answer the AI gives. `user_question` stores what the user typed. `ai_response` stores what Gemini returned.

---

## 4.5 `app/ocr_utils.py` — Text Extraction & Chunking

This file handles reading text from different file types and splitting it into chunks.

```python
import pytesseract
from PIL import Image
import pypdf
```
**Line 8**: `pytesseract` — Python wrapper for the Tesseract OCR engine.

**Line 9**: `PIL` (Pillow) — Python Imaging Library. Opens and manipulates images.

**Line 10**: `pypdf` — reads and extracts text from PDF files.

```python
from config.settings import TESSERACT_CMD, CHUNK_SIZE, CHUNK_OVERLAP

pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
```
**Line 12**: Imports configuration values.

**Line 17**: Tells pytesseract where the Tesseract executable is located on this system.

```python
PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}
TEXT_EXTENSIONS = {".txt", ".md", ".csv"}
```
**Lines 20-22**: **Sets** of file extensions. Sets are used instead of lists because checking `".pdf" in {".pdf"}` is faster than `".pdf" in [".pdf"]`. These define which file types the system accepts.

### PDF Text Extraction

```python
def extract_text_from_pdf(pdf_path: str) -> str:
    text = ""
    try:
        with open(pdf_path, "rb") as f:
            reader = pypdf.PdfReader(f)
            for page in reader.pages:
                page_text = page.extract_text() or ""
                text += page_text + "\n"
    except Exception as e:
        logger.error("Error reading PDF '%s': %s", pdf_path, e)
```
**Line 25**: Function signature. Takes a file path string, returns a string. `-> str` is a return type hint.

**Line 33**: Opens the PDF file in **binary read mode** (`"rb"`). PDFs are binary files (not plain text), so we must use `"rb"`.

**Line 34**: Creates a PDF reader object that understands the PDF format.

**Line 35-36**: Loops through every page in the PDF. `reader.pages` is a list of page objects. `page.extract_text()` pulls out digital text if the PDF has it (i.e., it was created digitally, not scanned). `or ""` handles the case where `extract_text()` returns `None`.

```python
    if not text.strip():
        logger.info("No digital text in PDF '%s', attempting OCR fallback.", pdf_path)
        text = _ocr_pdf_fallback(pdf_path)
```
**Lines 42-44**: If the PDF had no extractable digital text (likely a scanned document), fall back to OCR. `text.strip()` removes whitespace — if the result is empty, the `if not` condition is True.

### OCR Fallback for Scanned PDFs

```python
def _ocr_pdf_fallback(pdf_path: str) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(pdf_path)
        ocr_texts = []
        for page_num, page in enumerate(reader.pages):
            for image_obj in page.images:
                try:
                    img = Image.open(image_obj.data)
                    ocr_texts.append(pytesseract.image_to_string(img))
                except Exception:
                    pass
        return "\n".join(ocr_texts)
```
**Lines 49-66**: The underscore prefix `_ocr_pdf_fallback` indicates this is a "private" function (internal use only).
- Iterates through each page's embedded images
- Opens each image with Pillow
- Runs Tesseract OCR on each image to extract text
- `pytesseract.image_to_string(img)` is the core OCR call — it sends the image to Tesseract and returns the recognized text

### Image Text Extraction

```python
def extract_text_from_image(image_path: str) -> str:
    try:
        image = Image.open(image_path)
        text = pytesseract.image_to_string(image)
        return text.strip()
```
**Lines 72-77**: Simple OCR: open the image file → run Tesseract → return text.

### File Type Router

```python
def extract_text_from_file(file_path: str) -> str:
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()

    if ext in PDF_EXTENSIONS:
        return extract_text_from_pdf(file_path)
    elif ext in IMAGE_EXTENSIONS:
        return extract_text_from_image(file_path)
    elif ext in TEXT_EXTENSIONS:
        return extract_text_from_txt(file_path)
    else:
        return ""
```
**Lines 93-109**: The **dispatcher** — determines the file type from its extension and calls the right extraction function.

`os.path.splitext("report.pdf")` returns `("report", ".pdf")`. The `_` means "ignore the first value" (the filename without extension).

### Text Chunking (for RAG)

```python
def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP) -> list[str]:
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
```
**Lines 127-144**: Splits text into overlapping chunks for RAG.

`RecursiveCharacterTextSplitter` is from **LangChain** — it's smart about splitting:
- First tries to split on `\n\n` (paragraph breaks)
- Then `\n` (line breaks)
- Then `. ` (sentences)
- Then ` ` (words)
- Finally `""` (individual characters)

This keeps chunks semantically meaningful. `chunk_overlap=50` means the last 50 characters of chunk N also appear at the start of chunk N+1, so no context is lost at boundaries.

---

## 4.6 `app/llm_utils.py` — Gemini AI Integration

This file handles all communication with Google's Gemini AI.

```python
from google import genai
from google.genai import types
from config.settings import GEMINI_API_KEY, GEMINI_MODEL
```
**Line 6**: `genai` — Google's new SDK for the Gemini API (package: `google-genai`).

**Line 7**: `types` — configuration objects for controlling API behavior.

```python
client = genai.Client(api_key=GEMINI_API_KEY)
```
**Line 13**: Creates a **client** — an authenticated connection to Google's servers. The `api_key` proves you're allowed to use the API.

```python
_DEFAULT_CONFIG = types.GenerateContentConfig(
    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    max_output_tokens=1024,
    temperature=0.3,
)
```
**Lines 16-20**: Configuration for every Gemini API call:
- `automatic_function_calling...disable=True` — **critical for performance**. By default, the SDK enables "AFC" which adds ~10 seconds latency per call. Disabling it removes that overhead.
- `max_output_tokens=1024` — limits the response to ~1024 tokens (~750 words). Prevents endlessly long responses.
- `temperature=0.3` — controls randomness. 0.0 = deterministic (same input → same output). 1.0 = very creative/random. 0.3 = focused and consistent but not robotic.

### The Core API Call

```python
def _call_gemini(prompt: str, max_tokens: int = 1024) -> str:
    config = _DEFAULT_CONFIG
    if max_tokens != 1024:
        config = types.GenerateContentConfig(
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            max_output_tokens=max_tokens,
            temperature=0.3,
        )
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=config,
        )
        return response.text or ""
    except Exception as e:
        logger.error("Gemini API error: %s", e)
        raise RuntimeError(f"Gemini API call failed: {e}") from e
```
**Lines 23-44**: The private helper that all other functions use.

- `client.models.generate_content(...)` — sends the prompt to Gemini and waits for the response
- `model=GEMINI_MODEL` — which model to use ("gemini-3.6-flash")
- `contents=prompt` — the text prompt to send
- `config=config` — the configuration object
- `response.text` — the model's text response
- `raise RuntimeError(...)` — if anything goes wrong, re-raise the error with a clear message. `from e` chains the original exception for debugging.

### Document Info Extraction

```python
def extract_document_info(text: str) -> str:
    if not text or not text.strip():
        return "No text available for analysis."

    truncated = text[:4000]

    prompt = f"""You are a document analysis assistant. Analyze the following document text..."""
    return _call_gemini(prompt)
```
**Lines 47-72**: Creates a carefully crafted prompt that instructs Gemini to:
1. Identify the document type
2. Summarize the main topic
3. Extract 3-5 key points
4. Find named entities (people, dates, organizations)
5. Write a 2-3 sentence summary

`text[:4000]` truncates to 4000 characters to avoid exceeding the model's input token limit.

The `f"""..."""` syntax is a Python **f-string** (formatted string literal) that allows embedding variables like `{truncated}` inside the string.

### RAG Question Answering

```python
def answer_question_rag(context_chunks: list[str], question: str) -> str:
    if not context_chunks:
        return "No document content available to answer this question."

    context = "\n\n---\n\n".join(context_chunks)

    if len(context) > 6000:
        context = context[:6000]

    prompt = f"""You are a helpful document assistant. Answer the user's question based ONLY on the provided document context.

## Rules:
- Answer ONLY from the document context below.
- If the answer is not in the context, say "This information is not available in the document."
- Be concise and accurate.
- Quote relevant parts of the document when helpful.

## Document Context:
{context}

## User Question:
{question}

## Answer:"""

    return _call_gemini(prompt)
```
**Lines 75-106**: The **RAG function**. This is the core of the chatbot.

- `context_chunks` — the list of text chunks retrieved from the database
- `"\n\n---\n\n".join(context_chunks)` — joins chunks with a separator so the model can distinguish between them
- The prompt explicitly tells the model to **ONLY use the provided context** — this is what makes RAG work. Without this instruction, the model would use its own training knowledge and might hallucinate.

---

## 4.7 `app/main.py` — The FastAPI Application (All Endpoints)

This is the main file. It ties everything together and defines the HTTP endpoints.

### Setup & Initialization

```python
import os
import shutil
import logging
from datetime import datetime, timezone
from pathlib import Path
```
**Lines 5-10**: Standard library imports:
- `os` — file system operations
- `shutil` — high-level file operations (copying files)
- `logging` — Python's logging framework
- `datetime` — timestamps
- `Path` — object-oriented file path handling

```python
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
```
**Line 12**: FastAPI imports:
- `FastAPI` — the main application class
- `UploadFile` — represents an uploaded file
- `File(...)` — marks a parameter as a file upload (`...` means "required")
- `Depends` — dependency injection (automatically calls `get_db()` before the endpoint)
- `HTTPException` — raises HTTP error responses (404, 400, 500, etc.)
- `Query` — defines query parameter validation

**Line 13**: `CORSMiddleware` — Cross-Origin Resource Sharing. Allows the frontend (browser) to make API calls to the backend. Without CORS, browsers block requests between different origins.

**Line 14**: `StaticFiles` — serves CSS/JS/images from a directory.

**Line 15**: `HTMLResponse` — returns HTML instead of JSON.

**Line 16**: `BaseModel` — Pydantic class for data validation. Defines the shape of request/response data.

**Line 17**: `Session` — SQLAlchemy database session type.

```python
from app.database import engine, get_db, Base
from app.models import Document, DocumentChunk, ChatHistory
from app.ocr_utils import extract_text_from_file, chunk_text, detect_file_type
from app.llm_utils import extract_document_info, answer_question_rag
from config.settings import UPLOAD_DIR
```
**Lines 19-23**: Imports from our own modules — connecting all the pieces together.

```python
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)
```
**Lines 26-27**: Sets up logging so we can see what's happening in the server console. `__name__` is automatically set to the current module name (`app.main`).

```python
Base.metadata.create_all(bind=engine)
```
**Line 30**: **Creates all database tables** defined by our models (Document, DocumentChunk, ChatHistory) if they don't already exist. `create_all` is idempotent — running it multiple times is safe; it won't recreate existing tables.

```python
app = FastAPI(
    title="Document Automation SaaS",
    description="Upload documents, extract key info with Gemini AI, and chat about your documents.",
    version="1.0.0",
)
```
**Lines 33-37**: Creates the FastAPI application instance. The `title` and `description` appear in the auto-generated docs at `/docs`.

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```
**Lines 40-46**: Adds CORS middleware:
- `allow_origins=["*"]` — accept requests from any website/origin (permissive for development)
- `allow_methods=["*"]` — allow all HTTP methods (GET, POST, DELETE, etc.)
- `allow_headers=["*"]` — allow all HTTP headers

```python
_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if _STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
```
**Lines 50-52**: Serves the frontend files:
- `Path(__file__).resolve().parent.parent` — navigates from `app/main.py` up two levels to the project root
- `/ "static"` — appends the `static` folder
- `app.mount("/static", ...)` — any request to `/static/style.css` will serve the file `static/style.css`

### Pydantic Schemas (Data Validation)

```python
class AskRequest(BaseModel):
    question: str

class AskResponse(BaseModel):
    document_id: int
    question: str
    answer: str

class UploadResponse(BaseModel):
    message: str
    document_id: int
    filename: str
    file_type: str
    text_length: int
    chunks_created: int
```
**Lines 57-101**: **Pydantic models** define the exact shape of request and response data. FastAPI uses these to:
1. **Validate** incoming data (reject requests with wrong types)
2. **Serialize** outgoing data (convert Python objects to JSON)
3. **Document** the API (shown in `/docs`)

For example, `AskRequest` requires a `question` field that must be a string. If someone sends `{"question": 123}`, FastAPI will reject it automatically.

### Endpoint: Serve Frontend (`GET /`)

```python
@app.get("/", response_class=HTMLResponse)
def read_root():
    index_path = _STATIC_DIR / "index.html"
    if index_path.is_file():
        return HTMLResponse(content=index_path.read_text(encoding="utf-8"), status_code=200)
    return HTMLResponse(
        content="<h1>DocAI API is running</h1>...",
        status_code=200,
    )
```
**Lines 108-118**: The `@app.get("/")` **decorator** tells FastAPI: "when someone visits the root URL (`/`), call this function."
- Reads the `index.html` file and sends it as an HTML response
- If the file doesn't exist, sends a simple fallback HTML page

### Endpoint: Upload Document (`POST /upload`)

```python
@app.post("/upload", response_model=UploadResponse)
def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
```
**Lines 137-138**: 
- `@app.post("/upload")` — this endpoint responds to POST requests at `/upload`
- `response_model=UploadResponse` — the response will be validated against `UploadResponse`
- `file: UploadFile = File(...)` — FastAPI automatically parses the uploaded file from the request. `File(...)` means it's required.
- `db: Session = Depends(get_db)` — **dependency injection**. FastAPI automatically calls `get_db()`, gets a database session, and passes it as `db`. After the endpoint returns, the session is automatically closed.

```python
    safe_filename = os.path.basename(file.filename)
    file_type = detect_file_type(safe_filename)
    if file_type == "unknown":
        raise HTTPException(status_code=400, detail="Unsupported file type...")
```
**Lines 147-153**: Security and validation:
- `os.path.basename("../../etc/passwd")` → `"passwd"` — strips path components to prevent **path traversal attacks** (a hacker trying to write files outside the uploads folder)
- Checks if the file type is supported; if not, returns HTTP 400 (Bad Request)

```python
    unique_filename = f"{uuid.uuid4().hex}_{safe_filename}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
```
**Lines 157-160**:
- `uuid.uuid4().hex` generates a random 32-character string (e.g., `"a1b2c3d4..."`) to prevent filename collisions
- `os.path.join("uploads", "a1b2c3d4_report.pdf")` → `"uploads/a1b2c3d4_report.pdf"`
- Opens a new file in **write binary** mode and copies the uploaded file's contents into it
- `shutil.copyfileobj` efficiently copies data in chunks (doesn't load the entire file into memory)

```python
    extracted_text = extract_text_from_file(file_path)
```
**Line 164**: Calls the OCR module to extract text. This is where Tesseract/pypdf does its work.

```python
    db_document = Document(
        filename=safe_filename,
        file_path=file_path,
        file_type=file_type,
        extracted_text=extracted_text,
    )
    db.add(db_document)
    db.commit()
    db.refresh(db_document)
```
**Lines 168-176**: Saves to PostgreSQL:
- Creates a new `Document` object with all the metadata
- `db.add()` — stages it for insertion
- `db.commit()` — actually writes it to the database
- `db.refresh()` — reloads the object from the database to get the auto-generated `id`

```python
    chunks = chunk_text(extracted_text)
    for idx, chunk in enumerate(chunks):
        db_chunk = DocumentChunk(
            document_id=db_document.id,
            chunk_text=chunk,
            chunk_index=idx,
        )
        db.add(db_chunk)
    db.commit()
```
**Lines 179-187**: Splits the text into chunks and saves each one:
- `enumerate(chunks)` gives both the index (0, 1, 2...) and the chunk text
- Each chunk references its parent document via `document_id`
- All chunks are committed in one batch for efficiency

### Endpoint: Extract Info (`GET /extract/{document_id}`)

```python
@app.get("/extract/{document_id}", response_model=ExtractResponse)
def extract_info(document_id: int, db: Session = Depends(get_db)):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    extracted_info = extract_document_info(document.extracted_text)
```
**Lines 206-220**:
- `{document_id}` in the URL is a **path parameter** — `/extract/5` sets `document_id = 5`
- `db.query(Document).filter(Document.id == document_id).first()` — SQL query: `SELECT * FROM documents WHERE id = 5 LIMIT 1`
- If no document exists with that ID, returns HTTP 404 (Not Found)
- Sends the document's text to Gemini for structured analysis

### Endpoint: Ask Question (`POST /ask/{document_id}`)

```python
@app.post("/ask/{document_id}", response_model=AskResponse)
def ask_question(document_id: int, body: AskRequest, db: Session = Depends(get_db)):
```
**Lines 230-231**:
- `body: AskRequest` — FastAPI automatically parses the JSON body `{"question": "..."}` into an `AskRequest` object

```python
    chunks = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
        .all()
    )
    chunk_texts = [c.chunk_text for c in chunks] if chunks else [document.extracted_text]
    answer = answer_question_rag(chunk_texts, body.question)
```
**Lines 245-256**: The **RAG pipeline**:
1. Fetch all chunks for this document from PostgreSQL, ordered by position
2. Extract just the text from each chunk object (list comprehension)
3. Send chunks + question to Gemini for answer generation

```python
    chat = ChatHistory(
        document_id=document_id,
        user_question=body.question,
        ai_response=answer,
    )
    db.add(chat)
    db.commit()
```
**Lines 259-265**: Saves the Q&A pair to the `chat_history` table for future reference.

### Endpoint: List Documents (`GET /documents`)

```python
@app.get("/documents")
def list_documents(
    skip: int = Query(0, ge=0, description="Number of documents to skip"),
    limit: int = Query(50, ge=1, le=200, description="Max documents to return"),
    db: Session = Depends(get_db),
):
    total = db.query(Document).count()
    documents = (
        db.query(Document)
        .order_by(Document.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
```
**Lines 280-294**: **Pagination** — returns documents in pages:
- `Query(0, ge=0)` — `ge` means "greater than or equal to" (validates the parameter)
- `offset(skip)` — skip the first N results
- `limit(limit)` — return at most N results
- `order_by(Document.created_at.desc())` — newest first

### Endpoint: Chat History (`GET /chat-history/{document_id}`)

```python
@app.get("/chat-history/{document_id}", response_model=ChatHistoryResponse)
def get_chat_history(document_id: int, db: Session = Depends(get_db)):
    chats = (
        db.query(ChatHistory)
        .filter(ChatHistory.document_id == document_id)
        .order_by(ChatHistory.created_at.asc())
        .all()
    )
```
**Lines 314-327**: Fetches all Q&A pairs for a specific document, ordered chronologically.

### Endpoint: Delete Document (`DELETE /documents/{document_id}`)

```python
@app.delete("/documents/{document_id}")
def delete_document(document_id: int, db: Session = Depends(get_db)):
    if document.file_path and os.path.exists(document.file_path):
        try:
            os.remove(document.file_path)
        except OSError:
            pass
    db.delete(document)
    db.commit()
```
**Lines 344-361**: Deletes a document:
1. Removes the physical file from disk (`os.remove`)
2. Deletes the database record — cascade rules automatically delete chunks and chat history

---

# 5. How All Parts Connect

```mermaid
graph TD
    A[".env file"] -->|loads| B["config/settings.py"]
    B -->|DATABASE_URL| C["app/database.py"]
    B -->|GEMINI_API_KEY, MODEL| D["app/llm_utils.py"]
    B -->|TESSERACT_CMD, CHUNK_SIZE| E["app/ocr_utils.py"]
    C -->|Base class| F["app/models.py"]
    C -->|get_db dependency| G["app/main.py"]
    D -->|extract, answer functions| G
    E -->|extract, chunk functions| G
    F -->|Document, Chunk, Chat models| G
    G -->|serves| H["static/ (Frontend)"]
    G -->|reads/writes| I["PostgreSQL"]
    D -->|API calls| J["Google Gemini Cloud"]
    E -->|OCR calls| K["Tesseract Binary"]
```

### The Import Chain:
1. `.env` → loaded by `config/settings.py`
2. `config/settings.py` → imported by `database.py`, `ocr_utils.py`, `llm_utils.py`
3. `database.py` → imported by `models.py` (for `Base`) and `main.py` (for `get_db`)
4. `models.py` → imported by `main.py` (for `Document`, `DocumentChunk`, `ChatHistory`)
5. `ocr_utils.py` → imported by `main.py` (for `extract_text_from_file`, `chunk_text`)
6. `llm_utils.py` → imported by `main.py` (for `extract_document_info`, `answer_question_rag`)
7. `main.py` → the entry point that FastAPI + uvicorn runs

---

# 6. Complete Flow Examples

### Flow 1: User uploads a PDF

```
1. Browser sends POST /upload with file data
2. FastAPI receives the request, calls get_db() to get a DB session
3. main.py validates the filename and file type
4. File is saved to disk: uploads/abc123_report.pdf
5. ocr_utils.extract_text_from_file("uploads/abc123_report.pdf") is called
6. ocr_utils detects .pdf extension → calls extract_text_from_pdf()
7. pypdf opens the PDF and extracts digital text from each page
8. If no text found (scanned PDF) → runs Tesseract OCR on embedded images
9. Returns the extracted text string
10. chunk_text() splits it into ~500-char overlapping chunks using LangChain
11. Document record saved to PostgreSQL (documents table)
12. Each chunk saved to PostgreSQL (document_chunks table)
13. JSON response returned: {document_id: 12, chunks_created: 6}
14. DB session automatically closed by get_db() finally block
```

### Flow 2: User asks "Who wrote this document?"

```
1. Browser sends POST /ask/12 with body {"question": "Who wrote this document?"}
2. FastAPI parses the body into AskRequest(question="Who wrote this document?")
3. main.py queries PostgreSQL: SELECT * FROM documents WHERE id = 12
4. main.py queries all chunks: SELECT * FROM document_chunks WHERE document_id = 12 ORDER BY chunk_index
5. Chunk texts extracted: ["Machine learning is...", "Author: Dr. Sarah...", ...]
6. llm_utils.answer_question_rag(chunks, question) is called
7. Chunks are joined with "---" separators into a context string
8. A prompt is constructed: "Answer based ONLY on this context: {context}. Question: {question}"
9. google-genai sends the prompt to Gemini 3.6 Flash via HTTPS
10. Gemini processes the prompt and returns: "The author is Dr. Sarah Johnson..."
11. The Q&A pair is saved to PostgreSQL (chat_history table)
12. JSON response returned: {answer: "The author is Dr. Sarah Johnson..."}
```

---

# 7. Detailed Summary For Your Agent

## PROJECT OVERVIEW

**Project Name**: Document Automation SaaS MVP
**Location**: `C:\Users\Isra\doc-automation-saas`
**Tech Stack**: Python 3.11, FastAPI, PostgreSQL 18, google-genai SDK (Gemini 3.6 Flash), Tesseract OCR, LangChain, Docker

## WHAT WAS BUILT

A complete backend API + frontend UI for document automation. The system accepts file uploads (PDF, images, text), extracts text using OCR (Tesseract) or PDF parsing (pypdf), stores documents and text chunks in PostgreSQL, uses Google Gemini AI to analyze documents and answer questions via RAG (Retrieval-Augmented Generation), and persists all chat Q&A history.

## ARCHITECTURE

The project follows a **layered architecture**:

1. **Configuration Layer** (`config/settings.py`): Loads all environment variables (API keys, DB URL, Tesseract path, chunking params) from a `.env` file using python-dotenv. Auto-detects Windows vs Linux for Tesseract binary path.

2. **Database Layer** (`app/database.py` + `app/models.py`): SQLAlchemy ORM with connection pooling (5 connections, 10 overflow). Three tables: `documents` (file metadata + extracted text), `document_chunks` (text split into ~500-char overlapping pieces), `chat_history` (user questions + AI responses). All tables use cascade deletes.

3. **Processing Layer** (`app/ocr_utils.py`): Handles text extraction from 3 file types:
   - PDF: digital text via pypdf with Tesseract OCR fallback for scanned documents
   - Images: direct Tesseract OCR
   - Text: UTF-8 file read
   - Also handles text chunking via LangChain's RecursiveCharacterTextSplitter (splits on paragraph → sentence → word boundaries with configurable overlap)

4. **AI Layer** (`app/llm_utils.py`): Google Gemini integration via `google-genai` SDK:
   - Uses `gemini-3.6-flash` model (latest available; `gemini-2.0-flash` and `gemini-2.5-flash` are deprecated)
   - AFC (Automatic Function Calling) disabled for ~3x speed improvement
   - `extract_document_info()`: structured extraction (type, topic, key points, entities, summary)
   - `answer_question_rag()`: RAG-pattern Q&A where the model is constrained to answer ONLY from provided document chunks

5. **API Layer** (`app/main.py`): FastAPI application with 7 endpoints:
   - `GET /` → serves frontend HTML UI
   - `GET /api` → JSON API info
   - `POST /upload` → upload + OCR + chunk + store (with UUID filename sanitization)
   - `GET /extract/{id}` → Gemini structured analysis
   - `POST /ask/{id}` → RAG chatbot Q&A (retrieves chunks → sends to Gemini → stores history)
   - `GET /documents` → paginated document list
   - `GET /chat-history/{id}` → Q&A history for a document
   - `DELETE /documents/{id}` → delete document + file + cascade delete chunks/history

6. **Frontend Layer** (`static/`): Single-page dark-mode UI with:
   - Drag-and-drop file upload with progress indicators
   - Document grid with AI Extract / Chat / Delete actions
   - Real-time chat interface with typing animation
   - Glassmorphism design, Inter font, gradient accents, micro-animations

7. **Infrastructure Layer**: Dockerfile (Python 3.11-slim + Tesseract), docker-compose.yml (PostgreSQL 16 + FastAPI), requirements.txt (pinned versions)

## KEY TECHNICAL DECISIONS

| Decision | Rationale |
|---|---|
| `google-genai` not `google-generativeai` | Old package deprecated; new SDK is the official replacement |
| `gemini-3.6-flash` not `gemini-2.0-flash` | 2.0 and 2.5 return 404 errors; 3.6 is the current recommended model |
| AFC disabled | Default AFC adds ~10-15s latency per request; disabling it gives ~5s responses |
| `temperature=0.3` | Low temperature for factual, consistent document analysis |
| `max_output_tokens=1024` | Prevents runaway long responses while allowing detailed answers |
| UUID filenames | Prevents filename collisions and path traversal attacks |
| Sync endpoints (not async) | All I/O is synchronous (SQLAlchemy, google-genai); async would provide no benefit |
| LangChain text splitter | Smart chunking that respects paragraph/sentence boundaries |
| `cascade="all, delete-orphan"` | Deleting a document auto-deletes all its chunks and chat history |
| `pool_pre_ping=True` | Prevents stale PostgreSQL connection errors |

## FILES AND LINE COUNTS

| File | Lines | Purpose |
|---|---|---|
| `.env` | 2 | API key + database URL |
| `config/settings.py` | 36 | Centralized configuration |
| `app/database.py` | 26 | DB engine + session factory |
| `app/models.py` | 50 | 3 SQLAlchemy table models |
| `app/ocr_utils.py` | 165 | OCR extraction + chunking |
| `app/llm_utils.py` | 128 | Gemini API integration |
| `app/main.py` | 367 | FastAPI endpoints + schemas |
| `static/index.html` | 136 | Frontend HTML structure |
| `static/style.css` | 700+ | Dark-mode CSS design |
| `static/app.js` | 350+ | Frontend JavaScript logic |
| `tests/test_ocr.py` | 90 | 13 OCR unit tests |
| `tests/test_api.py` | 185 | 14 API integration tests |
| `Dockerfile` | 33 | Container definition |
| `docker-compose.yml` | 38 | Multi-service compose |
| `requirements.txt` | 15 | Pinned Python dependencies |

## TEST RESULTS

**27/27 tests passing** covering: file type detection, text extraction, chunking edge cases, all API endpoints (upload, extract, ask, documents, chat-history, delete), error handling (404s, 400s), and frontend HTML serving.

## HOW TO RUN

```powershell
# Local development
cd C:\Users\Isra\doc-automation-saas
venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Run tests
venv\Scripts\python.exe -m pytest tests/ -v

# Docker
docker-compose up --build
```

**Frontend**: http://localhost:8000
**API Docs**: http://localhost:8000/docs
**API Info**: http://localhost:8000/api

---
# 8. POST-AUDIT UPDATES (Added August 26)

This project went through an enterprise security and DevOps audit, resulting in several major upgrades:

## A. CI/CD & DevOps
- **GitHub Actions**: Added .github/workflows/ci.yml which stands up a PostgreSQL service container, installs system dependencies (	esseract-ocr, libpq-dev, libmagic1), runs all pytest suites, and builds the Docker container automatically on push.
- **Enterprise Documentation**: Generated DEPLOYMENT.md detailing backups via pg_dumpall, Sentry exception tracking, load testing, and security hardening.

## B. Expanded Test Suite (37 Tests)
- Increased from 27 to **37 tests**, all passing.
- **	ests/test_integration.py**: Added deep integration tests covering AI classification detection, admin /admin/metrics endpoint security, and live metric increments.
- **Multi-Tenant Isolation Test**: Ensures User A cannot fetch, delete, or query User B's documents (enforced via database query filters).
- **	ests/conftest.py**: Unified testing environment with a centralized TestSession and limiter.reset() to fix flaky rate-limit tests.

## C. AI Document Classification
- Documents are now automatically classified during upload using keyword heuristics and AI.
- The documents table schema was updated to include category.
- Categories include: *Invoice & Receipt*, *Contract & Policy*, *Financial Report*, *Technical Proposal*, *Spreadsheet Data*.
- The UI sidebar now displays color-coded category badges for each uploaded file.

## D. Security & Hardening
- **Magic Bytes Validation**: pp/ocr_utils.py uses python-magic to inspect file headers, blocking malicious payload uploads disguised with fake extensions.
- **CORS Config**: Replaced hardcoded ["*"] origins with a dynamic CORS_ALLOWED_ORIGINS environment variable for tight production domain locking.
- **Rate Limiting**: Integrated slowapi to limit abuse on the /upload endpoint (e.g. max 20 per minute per IP).
- **Secrets Management**: Eradicated the .env file from the final delivery archive, supplying a safe .env.example to prevent compromised tokens.
