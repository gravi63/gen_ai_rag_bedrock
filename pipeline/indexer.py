"""
pipeline/indexer.py
-------------------
Creates the S3 Vectors bucket and index, then writes all embedded chunks.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from botocore.exceptions import ClientError

from config import settings
from utils.helpers import as_float32_list, client_error_code, client_error_summary

logger = logging.getLogger(__name__)

BATCH_SIZE = 500


# ── Bucket ────────────────────────────────────────────────────────────────────

def create_vector_bucket(s3vectors) -> None:
    """Create the vector bucket. Idempotent — skips if already exists."""
    # Use CMK from Terraform output if KMS_KEY_ARN is set, otherwise default SSE-S3
    if settings.KMS_KEY_ARN:
        encryption = {"sseType": "aws:kms", "kmsKeyArn": settings.KMS_KEY_ARN}
        logger.info("Using CMK encryption: %s", settings.KMS_KEY_ARN)
    else:
        encryption = {"sseType": "AES256"}

    args = {
        "vectorBucketName": settings.VECTOR_BUCKET_NAME,
        "encryptionConfiguration": encryption,
    }
    try:
        s3vectors.create_vector_bucket(**args)
        logger.info("Created vector bucket: %s", settings.VECTOR_BUCKET_NAME)
    except s3vectors.exceptions.ConflictException:
        logger.info("Vector bucket already exists: %s", settings.VECTOR_BUCKET_NAME)
    except ClientError as exc:
        raise RuntimeError(f"Error creating vector bucket: {client_error_summary(exc)}") from exc

    _wait_for_bucket(s3vectors, settings.VECTOR_BUCKET_NAME)


def _wait_for_bucket(s3vectors, bucket_name: str, timeout_seconds: int = 90) -> None:
    deadline = time.time() + timeout_seconds
    while True:
        try:
            s3vectors.get_vector_bucket(vectorBucketName=bucket_name)
            logger.info("Vector bucket ready: %s", bucket_name)
            return
        except ClientError as exc:
            code = client_error_code(exc)
            if code in {"NotFound", "NotFoundException", "ResourceNotFoundException", "NoSuchVectorBucket"}:
                if time.time() < deadline:
                    time.sleep(2)
                    continue
            raise


# ── Index ─────────────────────────────────────────────────────────────────────

def create_vector_index(s3vectors) -> None:
    """Create the vector index inside the bucket. Idempotent — skips if already exists."""
    args = {
        "vectorBucketName": settings.VECTOR_BUCKET_NAME,
        "indexName": settings.VECTOR_INDEX_NAME,
        "dataType": "float32",
        "dimension": settings.EMBEDDING_DIMENSIONS,
        "distanceMetric": settings.DISTANCE_METRIC,
        "metadataConfiguration": {"nonFilterableMetadataKeys": ["text"]},
    }
    try:
        s3vectors.create_index(**args)
        logger.info("Created vector index: %s", settings.VECTOR_INDEX_NAME)
    except s3vectors.exceptions.ConflictException:
        logger.info("Vector index already exists: %s", settings.VECTOR_INDEX_NAME)
    except ClientError as exc:
        raise RuntimeError(f"Error creating vector index: {client_error_summary(exc)}") from exc

    _wait_for_index(s3vectors, settings.VECTOR_BUCKET_NAME, settings.VECTOR_INDEX_NAME)


def _wait_for_index(s3vectors, bucket_name: str, index_name: str, timeout_seconds: int = 180) -> None:
    deadline = time.time() + timeout_seconds
    while True:
        try:
            s3vectors.get_index(vectorBucketName=bucket_name, indexName=index_name)
            logger.info("Vector index ready: %s", index_name)
            return
        except ClientError as exc:
            code = client_error_code(exc)
            if code in {"NotFound", "NotFoundException", "ResourceNotFoundException", "NoSuchIndex", "NoSuchVectorIndex"}:
                if time.time() < deadline:
                    time.sleep(3)
                    continue
            raise


# ── Write vectors ─────────────────────────────────────────────────────────────

def _to_vector_record(chunk: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "key": chunk["chunk_id"],
        "data": {"float32": as_float32_list(chunk["embedding"], expected_dimensions=settings.EMBEDDING_DIMENSIONS)},
        "metadata": {
            "text": chunk["text"],
            "doc_id": chunk["doc_id"],
            "title": chunk["title"],
            "source": chunk["source"],
            "page": chunk["page"],
            "tenant_id": chunk["tenant_id"],
            "access_group": chunk["access_group"],
            "chunk_index": chunk["chunk_index"],
            "chunking_version": chunk["chunking_version"],
        },
    }


def write_vectors(s3vectors, chunks: List[Dict[str, Any]]) -> None:
    """Batch-upload all embedded chunks to the S3 Vectors index."""
    records = [_to_vector_record(c) for c in chunks if c.get("embedding") is not None]
    skipped = len(chunks) - len(records)
    if skipped:
        logger.warning("Skipping %d chunks with missing embeddings.", skipped)

    total_batches = (len(records) + BATCH_SIZE - 1) // BATCH_SIZE
    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        try:
            s3vectors.put_vectors(
                vectorBucketName=settings.VECTOR_BUCKET_NAME,
                indexName=settings.VECTOR_INDEX_NAME,
                vectors=batch,
            )
            logger.info("Uploaded batch %d / %d (%d vectors)", batch_num, total_batches, len(batch))
        except ClientError as exc:
            raise RuntimeError(
                f"PutVectors failed at batch {batch_num}: {client_error_summary(exc)}"
            ) from exc

    logger.info("Total vectors uploaded: %d", len(records))
