"""
query/rag.py
------------
End-to-end RAG: retrieve → augment → generate.
"""

import logging
from typing import Any, Dict, List, Optional

from config import settings
from query.retriever import query_index

logger = logging.getLogger(__name__)

NO_ANSWER_TEXT = "I don't have that information in the current HR policies."


# ── Prompt builder ────────────────────────────────────────────────────────────

def build_rag_prompt(question: str, retrieved_chunks: List[Dict[str, Any]]) -> str:
    context_blocks = []
    for i, r in enumerate(retrieved_chunks, 1):
        md = r.get("metadata", {})
        block = (
            f"[Source {i}: {md.get('title')} - {md.get('source')} page {md.get('page')}]\n"
            f"{md.get('text') or ''}\n"
        )
        context_blocks.append(block)

    context = "\n".join(context_blocks)

    return f"""You are an HR assistant for Acme Corp. Answer the employee's question using ONLY the context below.

If the answer is not contained in the context, say "{NO_ANSWER_TEXT}" Do not make up details.

When you cite information, reference the source by number in square brackets, like [Source 1].

CONTEXT:
{context}

QUESTION: {question}

ANSWER:"""


# ── Generation ────────────────────────────────────────────────────────────────

def invoke_generation_model(
    bedrock_runtime,
    generation_model_id: str,
    prompt: str,
    max_tokens: int = 500,
    temperature: float = 0.0,
) -> str:
    response = bedrock_runtime.converse(
        modelId=generation_model_id,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": max_tokens, "temperature": temperature},
    )
    # Log token usage from response metadata
    usage = response.get("usage", {})
    logger.debug(
        "Generation tokens — input: %d  output: %d",
        usage.get("inputTokens", 0),
        usage.get("outputTokens", 0),
    )
    return response["output"]["message"]["content"][0]["text"]


# ── End-to-end RAG ────────────────────────────────────────────────────────────

def generate_answer(
    bedrock_runtime,
    s3vectors,
    generation_model_id: str,
    question: str,
    top_k: int = 5,
    tenant_id: Optional[str] = None,
    extra_filter: Optional[Dict[str, Any]] = None,
    distance_threshold: Optional[float] = None,
    max_tokens: int = 500,
) -> Dict[str, Any]:
    """
    Full RAG pipeline: retrieve → optional threshold guard → generate.

    Args:
        tenant_id: injected from auth context for multi-tenant isolation.
    """
    retrieved = query_index(
        bedrock_runtime, s3vectors, question,
        top_k=top_k,
        tenant_id=tenant_id,
        extra_filter=extra_filter,
    )

    if not retrieved:
        return {
            "question": question,
            "answer": NO_ANSWER_TEXT,
            "retrieved_chunks": [],
            "prompt_length_chars": 0,
        }

    # Distance threshold guard — refuse at retrieval layer if best match is too far
    effective_threshold = (
        distance_threshold
        if distance_threshold is not None
        else settings.NO_ANSWER_DISTANCE_THRESHOLD
    )
    top_distance = retrieved[0].get("distance")
    if (
        effective_threshold is not None
        and isinstance(top_distance, (int, float))
        and top_distance > effective_threshold
    ):
        logger.debug(
            "Distance threshold triggered: top_distance=%.4f threshold=%.4f",
            top_distance, effective_threshold,
        )
        return {
            "question": question,
            "answer": NO_ANSWER_TEXT,
            "retrieved_chunks": retrieved,
            "prompt_length_chars": 0,
        }

    prompt = build_rag_prompt(question, retrieved)
    answer_text = invoke_generation_model(
        bedrock_runtime, generation_model_id, prompt,
        max_tokens=max_tokens,
        temperature=0.0,
    )

    return {
        "question": question,
        "answer": answer_text,
        "retrieved_chunks": retrieved,
        "prompt_length_chars": len(prompt),
    }
