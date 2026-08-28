"""
Gemini API integration using the NEW google-genai SDK.
Provides document info extraction, vector embedding generation, and asymmetric RAG-style Q&A.
"""
import numpy as np
from google import genai
from google.genai import types

from app.logging_config import get_logger
from config.settings import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_TIMEOUT_SECONDS

logger = get_logger(__name__)

# ── Gemini client — authenticated with API key from Google AI Studio ────────
client = genai.Client(
    api_key=GEMINI_API_KEY,
    http_options=types.HttpOptions(timeout=int(GEMINI_TIMEOUT_SECONDS * 1000)),
)

# Disable AFC (automatic function calling) — it adds latency per request
_DEFAULT_CONFIG = types.GenerateContentConfig(
    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    max_output_tokens=1024,
    temperature=0.3,
)

EMBEDDING_MODEL = "gemini-embedding-001"


def _call_gemini(prompt: str, max_tokens: int = 1024) -> str:
    """
    Send a prompt to the Gemini API and return the text response.
    Handles errors gracefully with logging.
    """
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


def generate_embedding(text: str, is_query: bool = False) -> list[float]:
    """
    Generate 3072-dimensional vector embedding using Gemini API.
    Asymmetric task types:
    - RETRIEVAL_DOCUMENT when embedding document chunks during upload/backfill.
    - RETRIEVAL_QUERY when embedding user questions at query time.
    """
    if not text or not text.strip():
        return []

    task_type = "RETRIEVAL_QUERY" if is_query else "RETRIEVAL_DOCUMENT"
    try:
        res = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text[:4000],
            config=types.EmbedContentConfig(task_type=task_type),
        )
        if res and res.embeddings and len(res.embeddings) > 0:
            return res.embeddings[0].values
        return []
    except Exception as e:
        logger.error("Gemini embedding generation failed (task_type=%s): %s", task_type, e)
        return []


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """
    Compute normalized L2 dot-product cosine similarity between two float vectors.
    Zero-norm guard handles zero vectors cleanly without distorting non-zero margins.
    """
    if not vec_a or not vec_b:
        return 0.0
    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def retrieve_top_k_chunks(
    chunks_with_embeddings: list[tuple[str, list[float]]],
    question_embedding: list[float],
    k: int = 3,
) -> list[str]:
    """
    Perform vector similarity retrieval against candidate document chunks.
    Ranks chunks by normalized cosine similarity and selects Top-K context chunks.
    """
    if not chunks_with_embeddings:
        return []

    # If no valid question embedding, fallback to taking first K chunks
    if not question_embedding:
        return [chunk_text for chunk_text, _ in chunks_with_embeddings[:k]]

    scored_chunks = []
    for chunk_text, emb in chunks_with_embeddings:
        sim = cosine_similarity(question_embedding, emb) if emb else 0.0
        scored_chunks.append((sim, chunk_text))

    # Sort descending by similarity score
    scored_chunks.sort(key=lambda x: x[0], reverse=True)
    return [chunk_text for _, chunk_text in scored_chunks[:k]]


def extract_document_info(text: str) -> str:
    """
    Use Gemini to extract structured key information from document text.
    Returns a formatted analysis string.
    """
    if not text or not text.strip():
        return "No text available for analysis."

    truncated = text[:4000]

    prompt = f"""You are a document analysis assistant. Analyze the following document text and provide a structured extraction:

## Instructions
Extract the following information and format your response clearly:

1. **Document Type**: (e.g., contract, invoice, report, letter, resume, etc.)
2. **Main Topic**: A one-sentence summary of what this document is about.
3. **Key Points**: 3-5 bullet points of the most important information.
4. **Named Entities**: List any people, organizations, dates, amounts, or locations mentioned.
5. **Summary**: A 2-3 sentence summary of the document.

## Document Text:
{truncated}
"""
    return _call_gemini(prompt)


def answer_question_rag(context_chunks: list[str], question: str) -> str:
    """
    Answer a question using retrieved top-K document chunks as context (RAG pattern).
    The model is instructed to answer based ONLY on the provided context.
    """
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