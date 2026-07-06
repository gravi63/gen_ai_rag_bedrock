"""
utils/helpers.py
----------------
Shared utility functions used across the pipeline.
No Jupyter/IPython dependencies — plain Python logging replaces display(Markdown(...)).
"""

import logging
import math
from typing import Any, List, Optional

import numpy as np
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


# ── Vector helpers ────────────────────────────────────────────────────────────

def as_float32_list(vector: List[float], expected_dimensions: Optional[int] = None) -> List[float]:
    """Validate and cast a vector to a Python list of float32 values for S3 Vectors."""
    arr = np.asarray(vector, dtype=np.float32).reshape(-1)

    if expected_dimensions is not None and arr.shape[0] != expected_dimensions:
        raise ValueError(f"Expected {expected_dimensions} dimensions but got {arr.shape[0]}.")

    if not np.isfinite(arr).all():
        raise ValueError("Embedding contains NaN or Inf values.")

    if float(np.linalg.norm(arr)) == 0.0:
        raise ValueError("Embedding is a zero vector, which is not useful for cosine similarity.")

    return arr.tolist()


def format_distance(value: Any, precision: int = 4) -> str:
    """Safely format a distance returned by S3 Vectors."""
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return f"{float(value):.{precision}f}"
    return "n/a"


# ── AWS error helpers ─────────────────────────────────────────────────────────

def client_error_code(error: ClientError) -> str:
    return error.response.get("Error", {}).get("Code", "Unknown")


def client_error_summary(error: ClientError) -> str:
    err = error.response.get("Error", {})
    return f"{err.get('Code', 'Unknown')}: {err.get('Message', str(error))}"


# ── Output helpers ────────────────────────────────────────────────────────────

def show_answer(answer_text: str, header: Optional[str] = None) -> None:
    """Print answer to stdout (replaces Jupyter display/Markdown)."""
    if header:
        print(f"\n{'=' * 60}")
        print(f"{header}")
        print('=' * 60)
    print(answer_text or "")
