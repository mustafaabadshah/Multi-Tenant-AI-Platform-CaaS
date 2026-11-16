"""Deterministic and mathematical evaluation metrics for RAG retrieval, answers, and citations."""

import math
import re
from typing import Any, Optional, Sequence

# Common stop words for token-level overlap
STOP_WORDS = {
    "a", "an", "the", "and", "or", "in", "on", "at", "to", "for", "with", "by", "from",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does",
    "did", "it", "this", "that", "these", "those", "i", "you", "he", "she", "we", "they",
    "of", "as", "if", "but", "so", "than", "which", "who", "what", "where", "when", "why", "how"
}

REFUSAL_PATTERNS = [
    r"do(?:es)? not have enough information",
    r"cannot find (?:any )?information",
    r"not mentioned in (?:the )?(?:provided|retrieved) (?:documents|sources|context)",
    r"not (?:stated|found|covered|available) in",
    r"unable to answer",
    r"no relevant information",
    r"outside the scope of (?:the )?provided",
    r"not have access to",
    r"don't know",
    r"cannot answer",
]


def tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase alphanumeric words."""
    if not text:
        return []
    words = re.findall(r"[a-zA-Z0-9_\-]+", text.lower())
    return [w for w in words if w not in STOP_WORDS and len(w) > 1]


def recall_at_k(retrieved_chunk_ids: Sequence[str], expected_chunk_ids: Sequence[str], k: int = 5) -> float:
    """Calculate Recall@K: proportion of expected ground-truth chunks retrieved in top K."""
    if not expected_chunk_ids:
        # If no specific chunks were expected (e.g. general query or unanswerable)
        return 1.0 if not retrieved_chunk_ids else 1.0

    top_k = retrieved_chunk_ids[:k]
    hits = len(set(top_k) & set(expected_chunk_ids))
    return float(hits) / float(len(expected_chunk_ids))


def precision_at_k(retrieved_chunk_ids: Sequence[str], expected_chunk_ids: Sequence[str], k: int = 5) -> float:
    """Calculate Precision@K: proportion of top K retrieved chunks that are relevant."""
    if not retrieved_chunk_ids or k <= 0:
        return 0.0
    if not expected_chunk_ids:
        return 1.0

    top_k = retrieved_chunk_ids[:k]
    hits = len(set(top_k) & set(expected_chunk_ids))
    return float(hits) / float(len(top_k))


def mean_reciprocal_rank(retrieved_chunk_ids: Sequence[str], expected_chunk_ids: Sequence[str]) -> float:
    """Calculate Reciprocal Rank (1 / rank of first relevant chunk)."""
    if not expected_chunk_ids:
        return 1.0 if not retrieved_chunk_ids else 0.5

    for rank, chunk_id in enumerate(retrieved_chunk_ids, start=1):
        if chunk_id in expected_chunk_ids:
            return 1.0 / rank
    return 0.0


def hit_rate_at_k(retrieved_chunk_ids: Sequence[str], expected_chunk_ids: Sequence[str], k: int = 5) -> float:
    """Calculate Hit Rate@K: 1.0 if at least one relevant chunk is in top K, else 0.0."""
    if not expected_chunk_ids:
        return 1.0
    return 1.0 if any(cid in expected_chunk_ids for cid in retrieved_chunk_ids[:k]) else 0.0


def ndcg_at_k(retrieved_chunk_ids: Sequence[str], expected_chunk_ids: Sequence[str], k: int = 5) -> float:
    """Calculate Normalized Discounted Cumulative Gain at K with binary relevance."""
    if not expected_chunk_ids:
        return 1.0
    if not retrieved_chunk_ids or k <= 0:
        return 0.0

    top_k = retrieved_chunk_ids[:k]
    dcg = 0.0
    for i, cid in enumerate(top_k):
        if cid in expected_chunk_ids:
            dcg += 1.0 / math.log2(i + 2)  # i + 2 because index 0 is rank 1, log2(1+1) = 1

    ideal_hits = min(k, len(expected_chunk_ids))
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))
    return dcg / idcg if idcg > 0 else 0.0


def calculate_faithfulness(generated_answer: str, context_chunks: Sequence[str]) -> float:
    """Calculate deterministic faithfulness: proportion of answer claims grounded in context."""
    if not generated_answer or not generated_answer.strip():
        return 0.0

    if not context_chunks:
        # If no context was provided, check if assistant abstained
        if is_refusal(generated_answer):
            return 1.0
        return 0.0

    # Combine context text tokens into a fast lookup set
    context_text = " ".join(context_chunks).lower()
    context_tokens = set(tokenize(context_text))
    if not context_tokens:
        return 0.0

    # Split answer into sentence-like clauses
    sentences = [s.strip() for s in re.split(r"[.!?\n]+", generated_answer) if len(s.strip()) > 10]
    if not sentences:
        # Short answer fallback
        answer_tokens = tokenize(generated_answer)
        if not answer_tokens:
            return 0.5
        overlap = len(set(answer_tokens) & context_tokens)
        return min(1.0, overlap / len(answer_tokens))

    supported_count = 0
    for sentence in sentences:
        s_tokens = tokenize(sentence)
        if not s_tokens:
            supported_count += 1
            continue
        overlap = len(set(s_tokens) & context_tokens)
        # If at least 35% of informational tokens in sentence appear in context
        if (overlap / len(s_tokens)) >= 0.35:
            supported_count += 1

    return round(float(supported_count) / float(len(sentences)), 4)


def is_refusal(text: str) -> bool:
    """Check if the text represents an explicit abstention or refusal due to missing information."""
    text_lower = text.lower()
    return any(re.search(pat, text_lower) for pat in REFUSAL_PATTERNS)


def calculate_abstention_accuracy(generated_answer: str, is_unanswerable: bool) -> float:
    """Measure if the model correctly abstains on unanswerable questions, or answers normal questions."""
    refused = is_refusal(generated_answer)
    if is_unanswerable:
        return 1.0 if refused else 0.0
    else:
        # On answerable queries, an unwarranted refusal is penalized
        return 0.0 if (refused and len(generated_answer.split()) < 30) else 1.0


def calculate_citation_metrics(
    citations: Sequence[dict[str, Any]],
    retrieved_chunk_ids: Sequence[str],
    retrieved_chunks: Optional[Sequence[dict[str, Any]]] = None,
) -> dict[str, float]:
    """Calculate citation presence, provenance validity, and content correctness."""
    if not citations:
        return {
            "citation_presence": 0.0,
            "citation_validity": 0.0,
            "citation_correctness": 0.0,
            "citation_score": 0.0,
        }

    presence = 1.0
    valid_count = 0
    correct_count = 0
    retrieved_set = set(retrieved_chunk_ids)

    # Build chunk id to content map if retrieved_chunks provided
    chunk_content_map: dict[str, str] = {}
    if retrieved_chunks:
        for chk in retrieved_chunks:
            cid = str(chk.get("chunk_id", chk.get("id", "")))
            if cid:
                chunk_content_map[cid] = (chk.get("content") or "").lower()

    for cit in citations:
        chunk_id = cit.get("chunk_id") or cit.get("id")
        cid_str = str(chunk_id) if chunk_id else ""
        snippet = (cit.get("snippet") or cit.get("citation_text") or "").strip().lower()

        is_valid = False
        if cid_str and (cid_str in retrieved_set or not retrieved_chunk_ids):
            valid_count += 1
            is_valid = True
        elif not chunk_id and cit.get("document_name"):
            valid_count += 1
            is_valid = True

        # Check citation correctness: snippet must actually match retrieved content
        if is_valid and snippet and cid_str in chunk_content_map:
            if snippet in chunk_content_map[cid_str] or any(w in chunk_content_map[cid_str] for w in tokenize(snippet)[:5]):
                correct_count += 1
        elif is_valid:
            correct_count += 1

    validity = float(valid_count) / float(len(citations)) if citations else 0.0
    correctness = float(correct_count) / float(len(citations)) if citations else 0.0
    composite = round(0.3 * presence + 0.4 * validity + 0.3 * correctness, 4)

    return {
        "citation_presence": presence,
        "citation_validity": validity,
        "citation_correctness": correctness,
        "citation_score": composite,
    }


def calculate_context_relevance(question: str, retrieved_contexts: Sequence[str]) -> float:
    """Measure the token-level relevance of retrieved context to the user question."""
    q_tokens = set(tokenize(question))
    if not q_tokens or not retrieved_contexts:
        return 0.0

    combined_context = " ".join(retrieved_contexts).lower()
    ctx_tokens = set(tokenize(combined_context))
    overlap = len(q_tokens & ctx_tokens)
    return round(float(overlap) / float(len(q_tokens)), 4)


def detect_unsupported_claims(generated_answer: str, retrieved_contexts: Sequence[str]) -> list[str]:
    """Identify sentences in the generated answer that lack grounding in retrieved context."""
    if not generated_answer or not retrieved_contexts:
        return []

    combined_context = " ".join(retrieved_contexts).lower()
    context_tokens = set(tokenize(combined_context))
    if not context_tokens:
        return []

    sentences = [s.strip() for s in re.split(r"[.!?\n]+", generated_answer) if len(s.strip()) > 15]
    unsupported = []
    for sentence in sentences:
        s_tokens = tokenize(sentence)
        if not s_tokens:
            continue
        overlap = len(set(s_tokens) & context_tokens)
        overlap_ratio = overlap / len(s_tokens)
        if overlap_ratio < 0.25:
            unsupported.append(sentence)

    return unsupported


def calculate_answer_completeness(generated_answer: str, expected_answer: Optional[str]) -> float:
    """Calculate token overlap recall of the expected ground truth answer in the generated answer."""
    if not expected_answer:
        return 1.0
    exp_tokens = set(tokenize(expected_answer))
    if not exp_tokens:
        return 1.0

    gen_tokens = set(tokenize(generated_answer))
    overlap = len(exp_tokens & gen_tokens)
    return round(float(overlap) / float(len(exp_tokens)), 4)

