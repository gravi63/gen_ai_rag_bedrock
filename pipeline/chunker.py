"""
pipeline/chunker.py
-------------------
Two chunking strategies: fixed-size and recursive/semantic.

FIX vs original: uses tiktoken for accurate token counts instead of the
"1 token ≈ 4 chars" proxy. This prevents silent context-window overflows
on non-English text, code, or mixed content.
"""

import hashlib
import logging
import warnings
from typing import Any, Dict, List

import tiktoken

from config import settings

logger = logging.getLogger(__name__)

_TOKENIZER = tiktoken.get_encoding("cl100k_base")


def _token_len(text: str) -> int:
    return len(_TOKENIZER.encode(text))


# ── Validation ────────────────────────────────────────────────────────────────

def _validate_chunking_args(chunk_size: int, overlap: int) -> None:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive.")
    if overlap < 0:
        raise ValueError("overlap cannot be negative.")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size.")
    if overlap > chunk_size * 0.5:
        warnings.warn(
            "overlap > 50% of chunk_size — may create many near-duplicate chunks.",
            RuntimeWarning,
        )


# ── Fixed-size chunker ────────────────────────────────────────────────────────

def fixed_size_chunker(text: str, chunk_size: int = 400, overlap: int = 50) -> List[str]:
    """Naive fixed-size token chunking. Simple but breaks sentences."""
    _validate_chunking_args(chunk_size, overlap)
    if not text:
        return []

    tokens = _TOKENIZER.encode(text)
    step = chunk_size - overlap
    chunks: List[str] = []
    start = 0

    while start < len(tokens):
        chunk_tokens = tokens[start : start + chunk_size]
        chunk = _TOKENIZER.decode(chunk_tokens)
        if chunk.strip():
            chunks.append(chunk)
        if start + chunk_size >= len(tokens):
            break
        start += step

    return chunks


# ── Recursive / semantic chunker ──────────────────────────────────────────────

def _split_to_units(text: str, max_unit_tokens: int, separators: List[str]) -> List[str]:
    text = text.strip()
    if not text:
        return []
    if _token_len(text) <= max_unit_tokens:
        return [text]

    if not separators:
        return fixed_size_chunker(text, chunk_size=max_unit_tokens, overlap=0)

    separator = separators[0]
    if separator == "":
        return fixed_size_chunker(text, chunk_size=max_unit_tokens, overlap=0)

    parts = text.split(separator)
    if separator == ". ":
        parts = [p + "." for p in parts[:-1]] + [parts[-1]]

    units: List[str] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if _token_len(part) <= max_unit_tokens:
            units.append(part)
        else:
            units.extend(_split_to_units(part, max_unit_tokens, separators[1:]))
    return units


def _pack_units_with_overlap(units: List[str], chunk_size: int, overlap: int) -> List[str]:
    chunks: List[str] = []
    current = ""

    for unit in units:
        candidate = f"{current} {unit}".strip() if current else unit
        if _token_len(candidate) <= chunk_size:
            current = candidate
            continue

        if current:
            chunks.append(current)
            if overlap:
                tail_tokens = _TOKENIZER.encode(current)[-overlap:]
                tail = _TOKENIZER.decode(tail_tokens)
                current = (tail[tail.index(" ") + 1:] if " " in tail else tail).strip()
            else:
                current = ""
            candidate = f"{current} {unit}".strip() if current else unit

        if _token_len(candidate) > chunk_size:
            chunks.extend(fixed_size_chunker(unit, chunk_size=chunk_size, overlap=overlap))
            current = ""
        else:
            current = candidate

    if current:
        chunks.append(current)

    return chunks


def recursive_chunker(text: str, chunk_size: int = 400, overlap: int = 50) -> List[str]:
    """Split on paragraphs → sentences → words. Token-accurate."""
    _validate_chunking_args(chunk_size, overlap)
    if not text:
        return []
    separators = ["\n\n", ". ", " ", ""]
    units = _split_to_units(text, max_unit_tokens=chunk_size, separators=separators)
    return _pack_units_with_overlap(units, chunk_size=chunk_size, overlap=overlap)


# ── Chunk ID ──────────────────────────────────────────────────────────────────

def deterministic_chunk_id(doc_id: str, text: str, chunking_version: str) -> str:
    """Stable key that changes when content or chunking strategy changes."""
    digest = hashlib.sha256(f"{doc_id}|{chunking_version}|{text}".encode()).hexdigest()[:16]
    return f"{doc_id}-{digest}"


# ── Main entry point ──────────────────────────────────────────────────────────

def chunk_documents(documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Chunk all documents using the configured strategy. Returns flat list of chunk dicts."""
    chunking_version = (
        f"{settings.CHUNK_STRATEGY}-tokens-v1"
        f"-size{settings.CHUNK_SIZE}-overlap{settings.CHUNK_OVERLAP}"
    )
    chunker = (
        recursive_chunker
        if settings.CHUNK_STRATEGY == "recursive"
        else fixed_size_chunker
    )

    all_chunks: List[Dict[str, Any]] = []
    for doc in documents:
        pieces = chunker(
            doc["text"],
            chunk_size=settings.CHUNK_SIZE,
            overlap=settings.CHUNK_OVERLAP,
        )
        for i, piece in enumerate(pieces):
            all_chunks.append({
                "chunk_id": deterministic_chunk_id(doc["doc_id"], piece, chunking_version),
                "text": piece,
                "doc_id": doc["doc_id"],
                "title": doc["title"],
                "source": doc["source"],
                "page": doc["page"],
                "tenant_id": doc["tenant_id"],
                "access_group": doc["access_group"],
                "chunk_index": i,
                "chunking_version": chunking_version,
            })

    logger.info(
        "Chunked %d documents → %d chunks (strategy=%s, size=%d, overlap=%d)",
        len(documents),
        len(all_chunks),
        settings.CHUNK_STRATEGY,
        settings.CHUNK_SIZE,
        settings.CHUNK_OVERLAP,
    )
    return all_chunks
