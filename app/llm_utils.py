"""
Gemini API integration using the NEW google-genai SDK.
Provides document info extraction, vector embedding generation, and asymmetric RAG-style Q&A.
Falls back to Groq (llama-3.3-70b) when Gemini is unavailable.
"""
import os
import numpy as np
from google import genai
from google.genai import types

from app.logging_config import get_logger
from config.settings import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_TIMEOUT_SECONDS, GROQ_API_KEY

logger = get_logger(__name__)

# ── Gemini client ─────────────────────────────────────────────────────────────
client = genai.Client(api_key=GEMINI_API_KEY)

# ── Groq fallback client ──────────────────────────────────────────────────────
_groq_client = None
if GROQ_API_KEY:
    try:
        from groq import Groq as _Groq
        _groq_client = _Groq(api_key=GROQ_API_KEY)
        logger.info("Groq fallback client initialised (model: qwen/qwen3.8-27b)")
    except Exception as _groq_err:
        logger.warning("Groq client could not be initialised: %s", _groq_err)

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
    Falls back to Groq (qwen/qwen3.8-27b) immediately when Gemini returns 503 or fails.
    """
    import concurrent.futures as _futures

    config = _DEFAULT_CONFIG
    if max_tokens != 1024:
        config = types.GenerateContentConfig(
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            max_output_tokens=max_tokens,
            temperature=0.3,
        )

    def _do_gemini():
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=config,
        )
        return (response.text or "").strip()

    # Try Gemini with a configured timeout
    ex = _futures.ThreadPoolExecutor(max_workers=1)
    fut = ex.submit(_do_gemini)
    try:
        text = fut.result(timeout=GEMINI_TIMEOUT_SECONDS)
        if text:
            return text
    except _futures.TimeoutError:
        logger.warning("Gemini API call timed out after %ss", GEMINI_TIMEOUT_SECONDS)
        raise RuntimeError("Gemini API call timed out")
    except Exception as e:
        logger.warning("Gemini unavailable (%s), switching to Groq fallback...", e)
    finally:
        ex.shutdown(wait=False, cancel_futures=True)

    # ── Groq fallback (qwen/qwen3.8-27b) ──────────────────────────────────────
    if _groq_client:
        try:
            logger.info("Answering query via Groq fallback (qwen/qwen3.8-27b)...")
            chat = _groq_client.chat.completions.create(
                model="qwen/qwen3.8-27b",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.3,
            )
            ans = chat.choices[0].message.content or ""
            if ans.strip():
                return ans.strip()
        except Exception as groq_err:
            logger.warning("Groq fallback also failed: %s", groq_err)

    raise RuntimeError("Both Gemini and Groq are unavailable. Please try again later.")



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
    Extract structured key information from document text.
    Uses fast local analysis first, then optionally enhances with Gemini if available.
    Always returns instantly — never times out.
    """
    if not text or not text.strip():
        return "No text available for analysis."

    # ── Fast local analysis (always works instantly) ──────────────────────────
    import re as _re
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    words = text.split()
    word_count = len(words)
    char_count = len(text)

    # Detect document type using shared classify_document (Item H)
    from app.ocr_utils import classify_document
    base_category = classify_document(text, "")
    _display_map = {
        "Invoice & Receipt": "Invoice / Receipt",
        "Contract & Policy": "Contract / Legal Agreement",
        "Financial Report": "Financial Report / Quarterly Summary",
        "Technical Proposal": "Project Proposal / Technical Document",
        "Data Spreadsheet": "Data File / Spreadsheet",
        "General Document": "General Document",
    }
    doc_type = _display_map.get(base_category, base_category)

    # Extract key sentences (first meaningful lines)
    key_sentences = [l for l in lines if len(l) > 30][:6]

    # Extract numbers, dates, monetary amounts
    amounts = _re.findall(r'\$[\d,]+(?:\.\d+)?|\d+(?:\.\d+)?%|\d{1,3}(?:,\d{3})+', text)
    dates = _re.findall(r'\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}', text)
    # Extract capitalized proper nouns
    proper_nouns = list(dict.fromkeys(_re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)))[:10]

    # Build bullet points from key lines
    bullets = "\n".join(f"- {s}" for s in key_sentences[:5]) if key_sentences else "- No key lines detected."

    entities_out = ""
    if amounts:
        entities_out += f"\n- **Amounts/Percentages**: {', '.join(list(dict.fromkeys(amounts))[:8])}"
    if dates:
        entities_out += f"\n- **Dates**: {', '.join(list(dict.fromkeys(dates))[:6])}"
    if proper_nouns:
        entities_out += f"\n- **Organizations/Names**: {', '.join(proper_nouns[:8])}"
    if not entities_out:
        entities_out = "\n- None detected."

    summary = " ".join(words[:80])
    if len(words) > 80:
        summary += "..."

    local_result = f"""### 1. Document Type
{doc_type}

### 2. Main Topic
{key_sentences[0] if key_sentences else lines[0] if lines else 'Document content extracted.'}

### 3. Key Points
{bullets}

### 4. Named Entities & Figures
{entities_out.strip()}

### 5. Summary
{summary}

---
*Document stats: {word_count:,} words · {char_count:,} characters*"""

    return local_result


def answer_question_rag(context_chunks: list[str], question: str) -> str:
    """
    Answer a question using retrieved top-K document chunks as context (RAG pattern).
    Falls back to keyword search if Gemini API is unavailable.
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

    try:
        return _call_gemini(prompt)
    except Exception as api_err:
        logger.warning("Gemini RAG fallback triggered: %s", api_err)
        # ── Keyword-match fallback: surface the most relevant snippet ──────────
        stop_words = {
            "what", "where", "when", "who", "whom", "which", "whose", "why", "how",
            "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
            "do", "does", "did", "the", "a", "an", "and", "or", "but", "if", "then",
            "of", "at", "by", "for", "with", "about", "against", "between", "into",
            "through", "during", "before", "after", "above", "below", "to", "from",
            "in", "out", "on", "off", "over", "under", "again", "further", "then",
            "once", "here", "there", "when", "where", "why", "how", "all", "any",
            "both", "each", "few", "more", "most", "other", "some", "such", "no",
            "nor", "not", "only", "own", "same", "so", "than", "too", "very",
            "le", "la", "les", "du", "de", "des", "un", "une", "et", "ou", "qui",
            "que", "dans", "pour", "sur", "par", "avec", "dans", "sans", "sous"
        }

        words = [w.strip("?,.:;!\"'()[]{}/").lower() for w in question.split()]
        search_terms = [w for w in words if w and w not in stop_words and len(w) > 2]
        if not search_terms:
            search_terms = [w for w in words if w and len(w) > 2]

        sentences = []
        for chunk in context_chunks:
            for line in [l.strip() for l in chunk.splitlines() if l.strip()]:
                for part in [p.strip() for p in line.split(".") if p.strip()]:
                    if len(part) > 15:
                        sentences.append(part)

        scored = []
        for sentence in sentences:
            sl = sentence.lower()
            score = sum(
                1.0 + (0.5 if f" {t} " in f" {sl} " else 0.0)
                for t in search_terms if t in sl
            )
            if score > 0:
                scored.append((score * min(1.0, 100.0 / len(sentence)), sentence))

        scored.sort(key=lambda x: x[0], reverse=True)
        seen, top = set(), []
        for _, s in scored:
            if s.lower() not in seen:
                seen.add(s.lower())
                top.append(s)
            if len(top) >= 3:
                break

        notice = (
            "\n\n> ⚠️ *The AI assistant is temporarily unavailable (Gemini API overloaded). "
            "The excerpt above was matched directly from your document.*"
        )

        if top:
            quotes = "\n\n".join(f'> "... {s} ..."' for s in top)
            return f"**Most relevant passage from your document:**\n\n{quotes}{notice}"

        return (
            "⚠️ The AI assistant is temporarily unavailable (Gemini API overloaded). "
            "Please try again in a moment."
        )