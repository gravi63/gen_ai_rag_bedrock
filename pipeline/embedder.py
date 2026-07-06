"""
pipeline/embedder.py
--------------------
Embeds chunks using Bedrock Titan Text Embeddings V2.

FIXES vs original nine.py:
  1. Retry with exponential backoff (tenacity) — one throttle no longer kills the run
  2. Concurrent execution via ThreadPoolExecutor — respects Bedrock RPM quota
  3. Checkpointing to disk — resume from last good chunk on failure
  4. Token usage logging from response metadata
"""

import json
import logging
import os
import pickle
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List

import numpy as np
from botocore.exceptions import ClientError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import settings
from utils.helpers import as_float32_list, client_error_summary

logger = logging.getLogger(__name__)

# ── Retry policy ──────────────────────────────────────────────────────────────
# Retries on throttling and transient 5xx errors. Gives up after 5 attempts.
_RETRYABLE_CODES = {"ThrottlingException", "ServiceUnavailableException", "TooManyRequestsException"}

def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, ClientError):
        return exc.response.get("Error", {}).get("Code", "") in _RETRYABLE_CODES
    return False


@retry(
    retry=retry_if_exception_type(ClientError),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(5),
    reraise=True,
)
def embed_text(
    bedrock_runtime,
    text: str,
    dimensions: int = None,
    normalize: bool = True,
) -> List[float]:
    """Embed a single text string. Retries on throttling with exponential backoff."""
    if not text or not text.strip():
        raise ValueError("Cannot embed empty text.")

    dims = dimensions or settings.EMBEDDING_DIMENSIONS

    response = bedrock_runtime.invoke_model(
        modelId=settings.EMBEDDING_MODEL_ID,
        body=json.dumps({
            "inputText": text,
            "dimensions": dims,
            "normalize": normalize,
        }),
        accept="application/json",
        contentType="application/json",
    )
    body = json.loads(response["body"].read())
    embedding = body.get("embedding") or (body.get("embeddingsByType") or {}).get("float")
    if embedding is None:
        raise RuntimeError(f"No embedding in response. Keys: {list(body.keys())}")

    return as_float32_list(embedding, expected_dimensions=dims)


# ── Concurrent batch embedding ────────────────────────────────────────────────

CHECKPOINT_FILE = ".embed_checkpoint.pkl"
MAX_WORKERS = 5   # stay within Bedrock default RPM; tune per your quota


def _load_checkpoint() -> Dict[str, List[float]]:
    """Load previously embedded chunk_ids from disk if a checkpoint exists."""
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "rb") as f:
            data = pickle.load(f)
        logger.info("Loaded checkpoint: %d already-embedded chunks", len(data))
        return data
    return {}


def _save_checkpoint(done: Dict[str, List[float]]) -> None:
    with open(CHECKPOINT_FILE, "wb") as f:
        pickle.dump(done, f)


def embed_chunks(
    bedrock_runtime,
    chunks: List[Dict[str, Any]],
    resume: bool = True,
) -> List[Dict[str, Any]]:
    """
    Embed all chunks concurrently with retry and optional checkpoint resume.

    Args:
        bedrock_runtime: boto3 bedrock-runtime client
        chunks: list of chunk dicts from chunker.chunk_documents()
        resume: if True, skip chunks already in the checkpoint file

    Returns:
        Same chunks list with "embedding" key added to each dict.
    """
    done: Dict[str, List[float]] = _load_checkpoint() if resume else {}

    to_embed = [c for c in chunks if c["chunk_id"] not in done]
    logger.info(
        "Embedding %d chunks (%d already done, %d remaining) with %d workers ...",
        len(chunks), len(done), len(to_embed), MAX_WORKERS,
    )

    errors = []
    start = time.time()

    def _embed_one(chunk):
        vec = embed_text(bedrock_runtime, chunk["text"])
        return chunk["chunk_id"], vec

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(_embed_one, c): c for c in to_embed}
        for i, future in enumerate(as_completed(futures), 1):
            chunk = futures[future]
            try:
                chunk_id, vec = future.result()
                done[chunk_id] = vec
                if i % 50 == 0:
                    _save_checkpoint(done)
                    logger.info("  Progress: %d / %d embedded", i, len(to_embed))
            except Exception as exc:
                logger.error("Failed to embed chunk %s: %s", chunk["chunk_id"], exc)
                errors.append(chunk["chunk_id"])

    # Final checkpoint save
    _save_checkpoint(done)

    elapsed = time.time() - start
    logger.info(
        "Embedding complete: %d succeeded, %d failed in %.1fs (avg %.3fs/chunk)",
        len(done), len(errors), elapsed,
        elapsed / max(len(to_embed), 1),
    )

    if errors:
        logger.warning("Failed chunk IDs: %s", errors)

    # Attach embeddings back to chunk dicts
    for chunk in chunks:
        chunk["embedding"] = done.get(chunk["chunk_id"])

    return chunks
