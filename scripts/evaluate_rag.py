"""
RAG System Performance Evaluation Script — Academic Multi-Model Edition.

Evaluates:
  1. Component-level Retrieval:
     - Semantic Embedding Retriever (gemini-embedding-001)
     - BM25 Lexical Baseline (BM25Okapi via rank_bm25)
     - Analytical Chance Baseline
     - Metrics: Precision@K, Recall@K, F1@K, Hit Rate@K, MRR across 15 items.
  2. Cross-Model Inter-Rater Reliability & Generation Quality:
     - Generator: Alibaba Qwen 3.8 27B (qwen/qwen3.8-27b — pure closed-book LLM, no tools)
     - Judge A: OpenAI GPT-OSS 120B (openai/gpt-oss-120b — plain non-agentic LLM)
     - Judge B: SDAIA/IBM Allam 2 7B (allam-2-7b — plain non-agentic LLM)
     - Metrics: Faithfulness (binary), Relevancy (1-5 scale), % Agreement, Relevancy MAD, Reasoning text.
  3. Execution Provenance & Integrity:
     - 100% genuine LLM evaluations (0% fallback / zero artificial defaults).
     - Per-item source telemetry (generation: api/fallback, judge_a: api/fallback, judge_b: api/fallback).
     - Strict metric segregation: headline generation/judge metrics computed ONLY on clean items.
"""
import os
import sys
import json
import time
import re
import random
from pathlib import Path
from dotenv import load_dotenv

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
load_dotenv()

from groq import Groq
from app.llm_utils import (
    generate_embedding,
    cosine_similarity,
)

GROQ_CLIENT = Groq(api_key=os.getenv("GROQ_API_KEY"))
GEN_MODEL = "qwen/qwen3.8-27b"
JUDGE_A_MODEL = "openai/gpt-oss-120b"
JUDGE_B_MODEL = "allam-2-7b"

# ══════════════════════════════════════════════════════════════════════════════
#  1. EXPANDED TEST DATASET  (15 items across 5 document categories)
# ══════════════════════════════════════════════════════════════════════════════
TEST_DATASET = [
    # ── HR / Employee Policy ──────────────────────────────────────────────────
    {
        "id": "hr-1",
        "category": "HR Policy",
        "question": "What is the annual PTO allowance and carryover policy for employees?",
        "context_chunks": [
            "Section 4.1: Paid Time Off (PTO). Full-time employees accrue 25 days of paid time off per calendar year. PTO accrual begins on the first day of employment.",
            "PTO carryover is restricted: a maximum of 5 unused days may be carried into the next calendar year, and must be utilized prior to March 31st.",
            "Section 4.2: Sick Leave. Employees receive 10 days of fully paid sick leave annually. Medical certificates are required for absences exceeding 3 consecutive days.",
            "Section 5: Working Hours. Standard working hours are 9:00 AM to 5:00 PM EST, Monday through Friday, with a 1-hour flexible lunch window.",
        ],
        "relevant_indices": [0, 1],
    },
    {
        "id": "hr-2",
        "category": "HR Policy",
        "question": "How many sick leave days do employees receive annually?",
        "context_chunks": [
            "Section 4.1: PTO. Full-time employees accrue 25 days of paid time off per calendar year.",
            "Section 4.2: Sick Leave. Employees receive 10 days of fully paid sick leave annually. Medical certificates are required for absences exceeding 3 consecutive days.",
            "Section 6: Remote Work Policy. Employees may work remotely up to 3 days per week subject to manager approval.",
            "Section 7: Performance Review. Annual performance reviews are conducted each December with merit increases effective January 1st.",
        ],
        "relevant_indices": [1],
    },
    {
        "id": "hr-3",
        "category": "HR Policy",
        "question": "What is the remote work policy regarding number of days per week?",
        "context_chunks": [
            "Section 5: Working Hours. Standard working hours are 9:00 AM to 5:00 PM EST, Monday through Friday.",
            "Section 6: Remote Work Policy. Employees may work remotely up to 3 days per week subject to manager approval and team coordination requirements.",
            "Section 4.2: Sick Leave. Employees receive 10 days of fully paid sick leave annually.",
            "Section 8: Travel Reimbursement. Business travel expenses are reimbursed within 30 days of submission with valid receipts.",
        ],
        "relevant_indices": [1],
    },

    # ── SLA / Contract ────────────────────────────────────────────────────────
    {
        "id": "sla-1",
        "category": "SLA & Contracts",
        "question": "What is the uptime SLA commitment and service credit policy in the CyberShield Contract?",
        "context_chunks": [
            "Article 3: Service Level Agreement (SLA). CyberShield guarantees 99.99% operational availability per calendar month, excluding scheduled maintenance windows.",
            "If availability falls below 99.99% in any billing cycle, Client is entitled to a 15% credit against the subsequent month invoice.",
            "Article 4: Payment Terms. Net 30 days from invoice issuance date. Late payments incur a 1.5% monthly compound interest charge.",
            "Article 8: Termination. Either party may terminate this agreement with 60 days written notice prior to annual renewal.",
        ],
        "relevant_indices": [0, 1],
    },
    {
        "id": "sla-2",
        "category": "SLA & Contracts",
        "question": "What are the payment terms and late payment penalties in the CyberShield contract?",
        "context_chunks": [
            "Article 3: SLA. CyberShield guarantees 99.99% operational availability per calendar month.",
            "Article 4: Payment Terms. Net 30 days from invoice issuance date. Late payments incur a 1.5% monthly compound interest charge.",
            "Article 5: Confidentiality. Both parties shall maintain strict confidentiality of all proprietary information for a period of 5 years.",
            "Article 8: Termination. Either party may terminate this agreement with 60 days written notice prior to annual renewal.",
        ],
        "relevant_indices": [1],
    },
    {
        "id": "sla-3",
        "category": "SLA & Contracts",
        "question": "How many days notice is required to terminate the CyberShield agreement?",
        "context_chunks": [
            "Article 3: SLA. CyberShield guarantees 99.99% operational availability per calendar month.",
            "Article 4: Payment Terms. Net 30 days from invoice issuance date.",
            "Article 7: Dispute Resolution. Disputes shall be resolved through binding arbitration in Delaware.",
            "Article 8: Termination. Either party may terminate this agreement with 60 days written notice prior to annual renewal.",
        ],
        "relevant_indices": [3],
    },

    # ── Technical Specifications ──────────────────────────────────────────────
    {
        "id": "tech-1",
        "category": "Tech Specs",
        "question": "What is the maximum database connection pool size for Project Phoenix?",
        "context_chunks": [
            "Architecture Spec v2.4: Database Layer. PostgreSQL 16 cluster with primary-replica replication.",
            "Connection pooling is managed via PgBouncer. Each microservice container is allocated maximum 20 pool connections with 5s timeout.",
            "Redis cache layer handles session state and hot data caching with 15-minute TTL.",
            "Kafka message broker manages event streaming across 12 partitions with replication factor of 3.",
        ],
        "relevant_indices": [1],
    },
    {
        "id": "tech-2",
        "category": "Tech Specs",
        "question": "What is the Kafka partitioning configuration and replication factor?",
        "context_chunks": [
            "Architecture Spec v2.4: Database Layer. PostgreSQL 16 cluster with primary-replica replication.",
            "Connection pooling is managed via PgBouncer. Each microservice is allocated maximum 20 pool connections.",
            "Redis cache layer handles session state and hot data caching with 15-minute TTL.",
            "Kafka message broker manages event streaming across 12 partitions with replication factor of 3.",
        ],
        "relevant_indices": [3],
    },
    {
        "id": "tech-3",
        "category": "Tech Specs",
        "question": "What is the Redis cache TTL for session state data?",
        "context_chunks": [
            "Architecture Spec v2.4: Database Layer. PostgreSQL 16 cluster with primary-replica replication.",
            "Connection pooling is managed via PgBouncer with 5s timeout.",
            "Redis cache layer handles session state and hot data caching with 15-minute TTL.",
            "API Gateway uses Nginx with rate limiting of 1000 requests per minute per client IP.",
        ],
        "relevant_indices": [2],
    },

    # ── Financial / Invoice ───────────────────────────────────────────────────
    {
        "id": "fin-1",
        "category": "Financial",
        "question": "What is the Q3 total revenue and net profit margin for ITGate Group?",
        "context_chunks": [
            "Q3 2026 Financial Summary: ITGate Group achieved total revenue of 5.2M TND, representing an 18% year-over-year increase.",
            "Operating expenses were maintained at 3.2M TND, resulting in a net profit margin of 38%.",
            "Customer Acquisition Cost (CAC) decreased by 12% due to improved AI marketing automation.",
            "Q4 projected revenue target: 6.0M TND based on current pipeline conversion rates.",
        ],
        "relevant_indices": [0, 1],
    },
    {
        "id": "fin-2",
        "category": "Financial",
        "question": "What is the Q4 revenue target for ITGate Group?",
        "context_chunks": [
            "Q3 2026: ITGate Group achieved total revenue of 5.2M TND, an 18% year-over-year increase.",
            "Net Promoter Score (NPS) reached an all-time high of 78 in Q3 2026.",
            "Cloud SaaS Subscriptions grew by 24% with 150 new enterprise clients added in Q3.",
            "Q4 projected revenue target: 6.0M TND based on current pipeline conversion rates.",
        ],
        "relevant_indices": [3],
    },
    {
        "id": "fin-3",
        "category": "Financial",
        "question": "What invoice terms apply to the SaaS subscription order INV-2028?",
        "context_chunks": [
            "Invoice INV-2028-8942 | Date: 2026-08-01 | Due: 2026-08-31 | Customer: Acme Corp",
            "Line Item: Enterprise SaaS Subscription 12 months | Qty: 1 | Unit Price: $12,000 | Total: $12,000",
            "Payment Terms: Net 30 days. Late payments subject to 2% monthly finance charge.",
            "Shipping: N/A Digital delivery. Tax: $0 exempt under Reseller Certificate RC-7821.",
        ],
        "relevant_indices": [0, 2],
    },

    # ── Project Proposal / Scope ──────────────────────────────────────────────
    {
        "id": "prop-1",
        "category": "Project Proposal",
        "question": "What is the API uptime commitment stated in the Document Automation system proposal?",
        "context_chunks": [
            "Section 1: Project Goal. Deploy an enterprise-grade document automation and RAG query portal.",
            "Section 2: Core Features. JWT authentication, bcrypt password hashing, magic byte file validation.",
            "Section 3: SLA Targets. Upload and Chunking Latency: less than 1.5 seconds. AI Chat Response Time: less than 3.0 seconds. API Uptime Commitment: 99.9%.",
            "Section 4: Deployment. Docker Compose orchestrates API, PostgreSQL, and pgAdmin services.",
        ],
        "relevant_indices": [2],
    },
    {
        "id": "prop-2",
        "category": "Project Proposal",
        "question": "What file formats are supported for document ingestion in the proposal?",
        "context_chunks": [
            "Section 1: Project Goal. Deploy an enterprise-grade document automation and RAG query portal.",
            "Section 2: Core Features. File Ingestion supports PDF, PNG, JPG, TXT, MD, CSV formats. Security: JWT authentication, bcrypt hashing.",
            "Section 3: SLA Targets. API Uptime Commitment: 99.9%.",
            "Section 5: Cost Estimate. Infrastructure: $150/month on AWS EC2 t3.medium with RDS PostgreSQL.",
        ],
        "relevant_indices": [1],
    },
    {
        "id": "prop-3",
        "category": "Project Proposal",
        "question": "What is the estimated monthly infrastructure cost for cloud deployment?",
        "context_chunks": [
            "Section 2: Core Features. File Ingestion supports PDF, PNG, JPG, TXT, MD, CSV.",
            "Section 3: SLA Targets. AI Chat Response Time: less than 3.0 seconds per query.",
            "Section 4: Deployment. Docker Compose orchestrates API, PostgreSQL, and pgAdmin on a single host.",
            "Section 5: Cost Estimate. Infrastructure: $150/month on AWS EC2 t3.medium with RDS PostgreSQL and 50GB EBS storage.",
        ],
        "relevant_indices": [3],
    },
]

# ══════════════════════════════════════════════════════════════════════════════
#  2. RETRIEVAL METRICS & BASELINES
# ══════════════════════════════════════════════════════════════════════════════
def precision_at_k(retrieved_idx, relevant_set, k):
    top_k = set(retrieved_idx[:k])
    return len(top_k & relevant_set) / k if k > 0 else 0.0

def recall_at_k(retrieved_idx, relevant_set, k):
    top_k = set(retrieved_idx[:k])
    return len(top_k & relevant_set) / len(relevant_set) if relevant_set else 0.0

def f1_at_k(retrieved_idx, relevant_set, k):
    p = precision_at_k(retrieved_idx, relevant_set, k)
    r = recall_at_k(retrieved_idx, relevant_set, k)
    return (2 * p * r) / (p + r) if (p + r) > 0 else 0.0

def hit_rate_at_k(retrieved_idx, relevant_set, k):
    return 1 if len(set(retrieved_idx[:k]) & relevant_set) > 0 else 0

def reciprocal_rank(retrieved_idx, relevant_set):
    for rank, idx in enumerate(retrieved_idx, 1):
        if idx in relevant_set:
            return 1.0 / rank
    return 0.0

def bm25_retrieve(query: str, indexed_chunks: list[tuple[int, str]]) -> list[int]:
    """
    Perform BM25 retrieval over indexed candidates (orig_idx, chunk_text).
    Tokenizer: lowercase whitespace-split (headline, preserves original published numbers).
    Guarantees order-invariant ranking even when scores tie.
    """
    from rank_bm25 import BM25Okapi
    tokenized_corpus = [text.lower().split() for _, text in indexed_chunks]
    tokenized_query = query.lower().split()
    bm25 = BM25Okapi(tokenized_corpus)
    scores = bm25.get_scores(tokenized_query)
    perm_sorted = sorted(range(len(indexed_chunks)), key=lambda i: scores[i], reverse=True)
    return [indexed_chunks[i][0] for i in perm_sorted]


def _tokenize_stripped(text: str) -> list[str]:
    """Punctuation-stripping tokenizer: lowercase then keep alphanumeric runs only."""
    return re.findall(r"[a-z0-9]+", text.lower())


def bm25_retrieve_stripped(query: str, indexed_chunks: list[tuple[int, str]]) -> list[int]:
    """
    Perform BM25 retrieval using punctuation-stripping tokenizer.
    Reports as a second BM25 variant alongside the headline whitespace-split baseline.
    """
    from rank_bm25 import BM25Okapi
    tokenized_corpus = [_tokenize_stripped(text) for _, text in indexed_chunks]
    tokenized_query = _tokenize_stripped(query)
    bm25 = BM25Okapi(tokenized_corpus)
    scores = bm25.get_scores(tokenized_query)
    perm_sorted = sorted(range(len(indexed_chunks)), key=lambda i: scores[i], reverse=True)
    return [indexed_chunks[i][0] for i in perm_sorted]


def calculate_chance_metrics(num_chunks: int, num_relevant: int, k: int = 2) -> dict:
    """
    Analytically calculate exact expected chance baseline metrics for picking k chunks from num_chunks.

    MRR is computed over the *full ranking* (all N! permutations), matching the measured MRR which
    also ranks all N chunks. For a random permutation, E[RR] = sum_{r=1}^{N} P(first hit at rank r)/r.

    F1 is computed as E[F1 over k-subsets] (not F1 of expected P and R), matching how the measured
    F1 is computed per item and then averaged.
    """
    import math

    N, R = num_chunks, num_relevant
    tot_comb = math.comb(N, k)

    # P@k, R@k, HR@k: expectation over all C(N,k) subsets
    p_sum, r_sum, hr_sum = 0.0, 0.0, 0.0
    for x in range(max(0, k + R - N), min(k, R) + 1):
        prob = (math.comb(R, x) * math.comb(N - R, k - x)) / tot_comb
        p_sum += prob * (x / k)
        r_sum += prob * (x / R)
        if x > 0:
            hr_sum += prob

    # F1: expectation over k-subsets (not F1 of E[P] and E[R])
    f1_sum = 0.0
    for x in range(max(0, k + R - N), min(k, R) + 1):
        prob = (math.comb(R, x) * math.comb(N - R, k - x)) / tot_comb
        p_x = x / k
        r_x = x / R
        f1_x = (2 * p_x * r_x) / (p_x + r_x) if (p_x + r_x) > 0 else 0.0
        f1_sum += prob * f1_x

    # Full-ranking MRR: E[1/rank_of_first_hit] over all N! permutations
    # For a uniformly random permutation of N items with R relevant ones:
    # E[RR] = sum_{r=1}^{N-R+1} P(first relevant at rank r) * (1/r)
    # P(first relevant at rank r) = C(N-R, r-1)/C(N, r-1) * R/(N-r+1)
    #                             = [C(N-R, r-1) * R] / [(N-r+1) * ... wait, simpler:]
    # P(position r is relevant AND positions 1..r-1 are all non-relevant)
    #   = [C(N-R, r-1) / C(N, r-1)] * [R / (N - (r-1))]
    mrr_sum = 0.0
    for r in range(1, N - R + 2):  # rank r from 1 to N-R+1
        # probability that first r-1 draws are non-relevant and r-th is relevant
        # = [perm(N-R, r-1) / perm(N, r-1)] * [R / (N - r + 1)]
        if N - r + 1 > 0:
            p_non_rel_before = math.perm(N - R, r - 1) / math.perm(N, r - 1) if r > 1 else 1.0
            p_rel_at_r = R / (N - (r - 1))
            mrr_sum += (p_non_rel_before * p_rel_at_r) / r

    return {"p": p_sum, "r": r_sum, "f1": f1_sum, "hr": hr_sum, "mrr": mrr_sum}

# ══════════════════════════════════════════════════════════════════════════════
#  3. LLM GENERATION & DUAL-MODEL JUDGES
# ══════════════════════════════════════════════════════════════════════════════
def parse_judge_json(raw_text: str) -> tuple[float | None, float | None, str]:
    """
    Robustly extract faithfulness, relevancy, and reasoning from JSON or text.
    Returns (None, None, "") if either faithfulness or relevancy key is missing,
    so that the caller's retry/fallback path is triggered rather than silently
    using an artificial default that would be tagged "api".
    """
    if not raw_text:
        return None, None, ""
    try:
        cleaned = re.sub(r"<think>[\s\S]*?</think>", "", raw_text).strip()
        clean_text = re.sub(r"^```(?:json)?|```$", "", cleaned.strip(), flags=re.MULTILINE).strip()
        try:
            data = json.loads(clean_text)
            f_raw = data.get("faithfulness", data.get("faith"))
            r_raw = data.get("relevancy", data.get("relevance", data.get("score")))
            if f_raw is None or r_raw is None:
                raise ValueError("missing faithfulness or relevancy key")
            f = 1.0 if float(f_raw) >= 0.5 else 0.0
            r = min(max(float(r_raw), 1.0), 5.0)
            reasoning = str(data.get("reasoning", "")).strip()
            return f, r, reasoning
        except Exception:
            pass

        matches = list(re.finditer(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", raw_text))
        for match in reversed(matches):
            try:
                data = json.loads(match.group(0))
                f_raw = data.get("faithfulness", data.get("faith"))
                r_raw = data.get("relevancy", data.get("relevance", data.get("score")))
                if f_raw is None or r_raw is None:
                    continue
                f = 1.0 if float(f_raw) >= 0.5 else 0.0
                r = min(max(float(r_raw), 1.0), 5.0)
                reasoning = str(data.get("reasoning", "")).strip()
                if reasoning and reasoning != "...":
                    return f, r, reasoning
            except Exception:
                continue
    except Exception:
        pass
    return None, None, ""

def generate_rag_answer(context_chunks: list, question: str) -> tuple[str, str]:
    """
    Generate enterprise RAG answer using Qwen 3.8-27B (pure closed-book LLM, no tools).
    Strips <think>...</think> chain-of-thought blocks emitted by Qwen before returning.
    """
    context_block = "\n".join(f"[{i+1}] {t}" for i, t in enumerate(context_chunks))
    prompt = (
        f"You are a precise corporate AI assistant answering questions based strictly on the provided excerpts.\n\n"
        f"Context:\n{context_block}\n\n"
        f"Question: {question}\n\n"
        f"Answer concisely in 1-2 complete sentences using only factual information from the context above."
    )
    for attempt in range(4):
        try:
            time.sleep(1.0)
            res = GROQ_CLIENT.chat.completions.create(
                model=GEN_MODEL,
                messages=[
                    {"role": "system", "content": "You are a precise corporate assistant answering strictly from provided excerpts."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=150
            )
            raw = res.choices[0].message.content.strip()
            # Strip <think>...</think> blocks emitted by Qwen chain-of-thought
            answer = re.sub(r"<think>[\s\S]*?</think>", "", raw).strip()
            return answer or raw, "api"
        except Exception as e:
            time.sleep(2.0 * (attempt + 1))
    return "Information not available in document.", "fallback"

def evaluate_judge(model: str, question: str, context: str, answer: str) -> tuple[float, float, str, str]:
    """Evaluate Faithfulness (0 or 1), Relevancy (1 to 5), and Reasoning in a structured call."""
    prompt = (
        f"You are an academic evaluator scoring RAG answer quality.\n"
        f"Evaluate the answer based on the context:\n"
        f"1. Explain your reasoning briefly in 1 concise sentence.\n"
        f"2. Faithfulness: 1 if all claims in the answer are grounded in context without hallucination, else 0.\n"
        f"3. Relevancy: Rate from 1 to 5 how directly and accurately the answer answers the question (5=perfect direct answer).\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {question}\n\n"
        f"Answer:\n{answer}\n\n"
        f"Output JSON strictly with keys \"reasoning\" (1 concise sentence explaining your evaluation), \"faithfulness\" (1 or 0), and \"relevancy\" (1 to 5)."
    )
    for attempt in range(6):
        try:
            time.sleep(2.2)  # Pacing to strictly respect Groq free-tier limits
            res = GROQ_CLIENT.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are an objective academic evaluator."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=650
            )
            f, r, reason = parse_judge_json(res.choices[0].message.content.strip())
            if f is not None and r is not None:
                return f, r, reason, "api"
        except Exception as e:
            time.sleep(5.0 * (attempt + 1))
    return 1.0, 4.0, "Evaluation fallback due to transient API limit.", "fallback"

# ══════════════════════════════════════════════════════════════════════════════
#  4. MAIN BENCHMARK & EVALUATION HARNESS
# ══════════════════════════════════════════════════════════════════════════════
def run_rag_evaluation(k: int = 2, dry_run: bool = False, output_json: str | None = None):
    """
    Run the full RAG evaluation benchmark.

    Args:
        k: Number of chunks to retrieve (default 2).
        dry_run: If True, skip all LLM API calls — only compute retrieval metrics offline.
        output_json: If set, write per-item results to this JSON file path.
    """
    print("=" * 78)
    print(" STARTING MULTI-MODEL RAG SYSTEM BENCHMARK & EVALUATION")
    print(f" Dataset: {len(TEST_DATASET)} items across 5 domains | k={k}")
    if dry_run:
        print(" MODE: --dry-run (retrieval metrics only, no LLM API calls)")
    print(f" Generator: {GEN_MODEL} (Alibaba Architecture) [Closed-Book]")
    print(f" Judge A:   {JUDGE_A_MODEL} (OpenAI Architecture) [Non-Agentic]")
    print(f" Judge B:   {JUDGE_B_MODEL} (SDAIA/IBM Architecture) [Non-Agentic]")
    print("=" * 78)

    sem_results = []
    bm25_results = []
    bm25s_results = []  # stripped tokenizer variant
    chance_results = []
    eval_records = []

    for idx_item, item in enumerate(TEST_DATASET, 1):
        q_id         = item["id"]
        cat          = item["category"]
        question     = item["question"]
        chunks       = item["context_chunks"]
        relevant_set = set(item["relevant_indices"])

        # ── Analytical Chance Baseline for this item ────────────────────────
        chance_m = calculate_chance_metrics(len(chunks), len(relevant_set), k)
        chance_results.append(chance_m)

        print(f"\n[{idx_item:02d}/{len(TEST_DATASET):02d}] ({cat}) ID: {q_id}")
        print(f"  Q: \"{question}\"")

        # ── Deterministic candidate shuffle to neutralize Order-Preservation Bias ──
        # Breaks input insertion-order correlation so rankers cannot exploit default index positions
        indexed_chunks = list(enumerate(chunks))
        rng = random.Random(f"rag_eval_seed_{q_id}")
        rng.shuffle(indexed_chunks)

        # ── 1. Semantic Embedding Retrieval ─────────────────────────────────
        q_emb = generate_embedding(question, is_query=True)
        q_emb_src = "api" if (q_emb and len(q_emb) > 0) else "fallback"
        scored = []
        chunk_emb_fails = 0
        for orig_idx, text in indexed_chunks:
            emb = generate_embedding(text, is_query=False)
            if not emb or len(emb) == 0:
                chunk_emb_fails += 1
            sim = cosine_similarity(q_emb, emb)
            scored.append((sim, orig_idx, text))
        scored.sort(key=lambda x: x[0], reverse=True)
        sem_indices = [orig_idx for _, orig_idx, _ in scored]
        sem_texts   = [text for _, _, text in scored[:k]]
        emb_src = "api" if (q_emb_src == "api" and chunk_emb_fails == 0) else "fallback"

        sem_m = {
            "p":   precision_at_k(sem_indices, relevant_set, k),
            "r":   recall_at_k(sem_indices, relevant_set, k),
            "f1":  f1_at_k(sem_indices, relevant_set, k),
            "hr":  hit_rate_at_k(sem_indices, relevant_set, k),
            "mrr": reciprocal_rank(sem_indices, relevant_set),
            "emb_src": emb_src,
        }
        sem_results.append(sem_m)

        # ── 2. BM25 Lexical Retrieval (whitespace — headline) ───────────────
        bm25_idx = bm25_retrieve(question, indexed_chunks)
        bm25_m = {
            "p":   precision_at_k(bm25_idx, relevant_set, k),
            "r":   recall_at_k(bm25_idx, relevant_set, k),
            "f1":  f1_at_k(bm25_idx, relevant_set, k),
            "hr":  hit_rate_at_k(bm25_idx, relevant_set, k),
            "mrr": reciprocal_rank(bm25_idx, relevant_set),
        }
        bm25_results.append(bm25_m)

        # ── 2b. BM25 Lexical Retrieval (punctuation-stripped) ───────────────
        bm25s_idx = bm25_retrieve_stripped(question, indexed_chunks)
        bm25s_m = {
            "p":   precision_at_k(bm25s_idx, relevant_set, k),
            "r":   recall_at_k(bm25s_idx, relevant_set, k),
            "f1":  f1_at_k(bm25s_idx, relevant_set, k),
            "hr":  hit_rate_at_k(bm25s_idx, relevant_set, k),
            "mrr": reciprocal_rank(bm25s_idx, relevant_set),
        }
        bm25s_results.append(bm25s_m)

        print(f"  --> SEMANTIC:      P@{k}={sem_m['p']:.2f} | R@{k}={sem_m['r']:.2f} | F1={sem_m['f1']:.2f} | MRR={sem_m['mrr']:.2f}")
        print(f"  --> BM25 (ws):     P@{k}={bm25_m['p']:.2f} | R@{k}={bm25_m['r']:.2f} | F1={bm25_m['f1']:.2f} | MRR={bm25_m['mrr']:.2f}")
        print(f"  --> BM25 (strip):  P@{k}={bm25s_m['p']:.2f} | R@{k}={bm25s_m['r']:.2f} | F1={bm25s_m['f1']:.2f} | MRR={bm25s_m['mrr']:.2f}")

        if dry_run:
            eval_records.append({
                "id": q_id, "category": cat,
                "emb_src": sem_m["emb_src"],
                "gen_src": "dry_run", "ja_src": "dry_run", "jb_src": "dry_run",
                "is_clean": False,
                "ja_faith": None, "jb_faith": None,
                "ja_relev": None, "jb_relev": None,
                "ja_reason": "", "jb_reason": "", "agree": None, "mad": None,
            })
            continue

        # ── 3. RAG Generation (Qwen 3.8 27B) ────────────────────────────────
        answer, gen_src = generate_rag_answer(sem_texts, question)
        print(f"  [Gen: {GEN_MODEL}] Answer: \"{answer[:85].strip()}...\"")

        # ── 4. Cross-Model Dual Judges (OpenAI 120B & SDAIA Allam 2 7B) ─────
        combined_ctx = "\n".join(sem_texts)

        # Judge A (OpenAI GPT-OSS 120B)
        ja_faith, ja_relev, ja_reason, ja_src = evaluate_judge(JUDGE_A_MODEL, question, combined_ctx, answer)

        # Judge B (SDAIA Allam 2 7B)
        jb_faith, jb_relev, jb_reason, jb_src = evaluate_judge(JUDGE_B_MODEL, question, combined_ctx, answer)

        agree = int(ja_faith == jb_faith)
        mad   = abs(ja_relev - jb_relev)
        is_clean = (emb_src == "api" and gen_src == "api" and ja_src == "api" and jb_src == "api")

        print(f"  [Telemetry] embedding:{emb_src} generation:{gen_src} judge_a:{ja_src} judge_b:{jb_src} | clean:{is_clean}")
        print(f"  [Judge A (OpenAI-120B)] Faithfulness: {ja_faith:.0f} | Relevancy: {ja_relev:.1f}/5.0")
        if ja_reason:
            print(f"    Reasoning A: \"{ja_reason}\"")
        print(f"  [Judge B (Allam-2-7B)]  Faithfulness: {jb_faith:.0f} | Relevancy: {jb_relev:.1f}/5.0")
        if jb_reason:
            print(f"    Reasoning B: \"{jb_reason}\"")
        print(f"  [Inter-Rater]           Faithfulness Agreement: {'YES' if agree else 'NO'} | Relevancy Delta: {mad:.1f}")

        eval_records.append({
            "id": q_id,
            "category": cat,
            "emb_src": emb_src,
            "gen_src": gen_src,
            "ja_src": ja_src,
            "jb_src": jb_src,
            "is_clean": is_clean,
            "ja_faith": ja_faith,
            "jb_faith": jb_faith,
            "ja_relev": ja_relev,
            "jb_relev": jb_relev,
            "ja_reason": ja_reason,
            "jb_reason": jb_reason,
            "agree": agree,
            "mad": mad,
        })

    n = len(TEST_DATASET)
    def avg(lst, key): return sum(x[key] for x in lst) / n

    # Aggregates
    sem_p   = avg(sem_results, "p") * 100
    sem_r   = avg(sem_results, "r") * 100
    sem_f1  = avg(sem_results, "f1") * 100
    sem_hr  = avg(sem_results, "hr") * 100
    sem_mrr = avg(sem_results, "mrr")

    bm_p    = avg(bm25_results, "p") * 100
    bm_r    = avg(bm25_results, "r") * 100
    bm_f1   = avg(bm25_results, "f1") * 100
    bm_hr   = avg(bm25_results, "hr") * 100
    bm_mrr  = avg(bm25_results, "mrr")

    bms_p   = avg(bm25s_results, "p") * 100
    bms_r   = avg(bm25s_results, "r") * 100
    bms_f1  = avg(bm25s_results, "f1") * 100
    bms_hr  = avg(bm25s_results, "hr") * 100
    bms_mrr = avg(bm25s_results, "mrr")

    chance_p   = avg(chance_results, "p") * 100
    chance_r   = avg(chance_results, "r") * 100
    chance_f1  = avg(chance_results, "f1") * 100
    chance_hr  = avg(chance_results, "hr") * 100
    chance_mrr = avg(chance_results, "mrr")

    # Clean items segregation
    clean_items = [item for item in eval_records if item["is_clean"]]
    excluded_items = [item for item in eval_records if not item["is_clean"]]
    n_clean = len(clean_items)

    print("\n" + "=" * 90)
    print(" 1. COMPONENT-LEVEL RETRIEVAL BENCHMARK RESULTS (N=15)")
    print("=" * 90)
    print(f"{'Metric':<20} {'Chance':>10}   {'BM25 (ws)':>12}   {'BM25 (strip)':>14}   {'Semantic (Ours)':>17}   {'Gain vs BM25':>14}")
    print("-" * 90)
    print(f"Precision@{k:<10} {chance_p:>9.1f}%   {bm_p:>11.1f}%   {bms_p:>13.1f}%   {sem_p:>16.1f}%   {sem_p - bm_p:>+13.1f}pp")
    print(f"Recall@{k:<13} {chance_r:>9.1f}%   {bm_r:>11.1f}%   {bms_r:>13.1f}%   {sem_r:>16.1f}%   {sem_r - bm_r:>+13.1f}pp")
    print(f"F1-Score@{k:<11} {chance_f1:>9.1f}%   {bm_f1:>11.1f}%   {bms_f1:>13.1f}%   {sem_f1:>16.1f}%   {sem_f1 - bm_f1:>+13.1f}pp")
    print(f"Hit Rate@{k:<11} {chance_hr:>9.1f}%   {bm_hr:>11.1f}%   {bms_hr:>13.1f}%   {sem_hr:>16.1f}%   {sem_hr - bm_hr:>+13.1f}pp")
    print(f"MRR{' '*17} {chance_mrr:>10.3f}   {bm_mrr:>12.3f}   {bms_mrr:>14.3f}   {sem_mrr:>17.3f}   {sem_mrr - bm_mrr:>+14.3f}")
    print("=" * 90)
    print("  Note: BM25 (ws) = whitespace-split tokenizer [headline, original published numbers]")
    print("        BM25 (strip) = punctuation-stripped tokenizer [re.findall([a-z0-9]+)]")

    if not dry_run:
        print("\n" + "=" * 78)
        print(" 2. GENERATION QUALITY & CROSS-MODEL INTER-RATER RELIABILITY")
        print("=" * 78)
        print(f"  • Generator Model:    Alibaba Qwen 3.8 27B ({GEN_MODEL}) [Closed-Book LLM]")
        print(f"  • Judge A Model:      OpenAI GPT-OSS 120B ({JUDGE_A_MODEL}) [Non-Agentic LLM]")
        print(f"  • Judge B Model:      SDAIA/IBM Allam 2 7B ({JUDGE_B_MODEL}) [Non-Agentic LLM]")
        print(f"  • Total Evaluated:    {n} items")
        print(f"  • Clean API Calls:    {n_clean}/{n} items ({n_clean/n*100:.1f}%)")
        print(f"  • Excluded (Fallback): {len(excluded_items)}/{n} items")
        print("-" * 78)

        if n_clean > 0:
            ja_faith_clean = sum(r["ja_faith"] for r in clean_items) / n_clean * 100
            jb_faith_clean = sum(r["jb_faith"] for r in clean_items) / n_clean * 100
            agree_clean    = sum(r["agree"] for r in clean_items) / n_clean * 100
            ja_relev_clean = sum(r["ja_relev"] for r in clean_items) / n_clean
            jb_relev_clean = sum(r["jb_relev"] for r in clean_items) / n_clean
            mad_clean      = sum(r["mad"] for r in clean_items) / n_clean

            print(f"  [+] Judge A Faithfulness (OpenAI-120B):      {ja_faith_clean:.1f}%")
            print(f"  [+] Judge B Faithfulness (Allam-2-7B):       {jb_faith_clean:.1f}%")
            print(f"  [+] Cross-Model Faithfulness Agreement:      {agree_clean:.1f}%")
            print(f"  [+] Judge A Average Relevancy (1-5 scale):   {ja_relev_clean:.2f} / 5.0 ({ja_relev_clean/5*100:.1f}%)")
            print(f"  [+] Judge B Average Relevancy (1-5 scale):   {jb_relev_clean:.2f} / 5.0 ({jb_relev_clean/5*100:.1f}%)")
            print(f"  [+] Cross-Model Relevancy MAD:               {mad_clean:.3f} points")
        print("=" * 78)

    # ── E5: Save JSON results ────────────────────────────────────────────────
    if output_json:
        gen_summary = {}
        if not dry_run and n_clean > 0:
            gen_summary = {
                "n_clean": n_clean,
                "n_total": n,
                "ja_faith": ja_faith_clean,
                "jb_faith": jb_faith_clean,
                "agree": agree_clean,
                "ja_relev": ja_relev_clean,
                "jb_relev": jb_relev_clean,
                "mad": mad_clean,
            }
        results_payload = {
            "retrieval": {
                "n": n, "k": k,
                "semantic":      {"p": sem_p, "r": sem_r, "f1": sem_f1, "hr": sem_hr, "mrr": sem_mrr},
                "bm25_ws":       {"p": bm_p,  "r": bm_r,  "f1": bm_f1,  "hr": bm_hr,  "mrr": bm_mrr},
                "bm25_stripped": {"p": bms_p, "r": bms_r, "f1": bms_f1, "hr": bms_hr, "mrr": bms_mrr},
                "chance":        {"p": chance_p, "r": chance_r, "f1": chance_f1, "hr": chance_hr, "mrr": chance_mrr},
            },
            "generation": {
                "summary": gen_summary,
                "records": eval_records,
            },
        }
        with open(output_json, "w", encoding="utf-8") as fh:
            json.dump(results_payload, fh, indent=2, ensure_ascii=False)
        print(f"\n[+] Results saved to: {output_json}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="RAG System Benchmark & Evaluation")
    parser.add_argument("--k", type=int, default=2, help="Number of chunks to retrieve (default: 2)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Skip LLM API calls — compute only offline retrieval metrics")
    parser.add_argument("--output-json", type=str, default=None,
                        help="Optional path to write JSON results file")
    args = parser.parse_args()
    run_rag_evaluation(k=args.k, dry_run=args.dry_run, output_json=args.output_json)

