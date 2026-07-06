"""
query/retriever.py
------------------
Semantic search against the S3 Vectors index.

FIX vs original: tenant_id filter is injected by the caller from auth context,
not passed through from the client request. This enforces multi-tenant isolation.
"""

import logging
from typing import Any, Dict, List, Optional

from botocore.exceptions import ClientError

from config import settings
from pipeline.embedder import embed_text
from utils.helpers import as_float32_list, client_error_code, client_error_summary

logger = logging.getLogger(__name__)


def query_index(
    bedrock_runtime,
    s3vectors,
    question: str,
    top_k: int = 5,
    tenant_id: Optional[str] = None,        # injected from auth context, not from client
    extra_filter: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Embed the question and run a nearest-neighbor search against S3 Vectors.

    Args:
        bedrock_runtime: boto3 bedrock-runtime client
        s3vectors: boto3 s3vectors client
        question: natural language query
        top_k: number of nearest neighbors (1–100)
        tenant_id: if provided, restricts results to this tenant.
                   MUST come from authenticated session — never from client input.
        extra_filter: additional metadata filters (e.g. {"source": {"$eq": "hr-handbook.pdf"}})

    Returns:
        List of result dicts with key, distance, and metadata.
    """
    if not question or not question.strip():
        raise ValueError("Question cannot be empty.")

    top_k = max(1, min(int(top_k), 100))

    query_vector = embed_text(
        bedrock_runtime, question,
        dimensions=settings.EMBEDDING_DIMENSIONS,
        normalize=True,
    )

    # Build filter: tenant isolation applied server-side
    metadata_filter: Optional[Dict[str, Any]] = None
    if tenant_id and extra_filter:
        metadata_filter = {"$and": [{"tenant_id": {"$eq": tenant_id}}, extra_filter]}
    elif tenant_id:
        metadata_filter = {"tenant_id": {"$eq": tenant_id}}
    elif extra_filter:
        metadata_filter = extra_filter

    kwargs: Dict[str, Any] = {
        "vectorBucketName": settings.VECTOR_BUCKET_NAME,
        "indexName": settings.VECTOR_INDEX_NAME,
        "topK": top_k,
        "queryVector": {"float32": as_float32_list(query_vector, expected_dimensions=settings.EMBEDDING_DIMENSIONS)},
        "returnDistance": True,
        "returnMetadata": True,
    }
    if metadata_filter is not None:
        kwargs["filter"] = metadata_filter

    try:
        response = s3vectors.query_vectors(**kwargs)
    except ClientError as exc:
        if client_error_code(exc) in {"AccessDenied", "AccessDeniedException", "Forbidden"}:
            logger.error(
                "QueryVectors access denied. Runtime role needs "
                "s3vectors:QueryVectors AND s3vectors:GetVectors."
            )
        raise

    results = response.get("vectors", [])
    logger.debug("query_index: question=%r top_k=%d results=%d", question[:60], top_k, len(results))
    return results
