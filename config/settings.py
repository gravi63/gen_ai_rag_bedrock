"""
config/settings.py
------------------
All configuration loaded from environment variables.
Override by setting env vars before running, or create a .env file and load with python-dotenv.

    export AWS_REGION=us-east-1
    export VECTOR_BUCKET_NAME=my-rag-bucket
    export BEDROCK_GENERATION_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0
"""

import os
import uuid
from typing import List

# ── AWS ──────────────────────────────────────────────────────────────────────
AWS_REGION: str = (
    os.environ.get("AWS_REGION")
    or os.environ.get("AWS_DEFAULT_REGION")
    or "us-east-1"
)

UNIQUE_SUFFIX: str = os.environ.get("WORKSHOP_SUFFIX") or uuid.uuid4().hex[:8]
VECTOR_BUCKET_NAME: str = os.environ.get("VECTOR_BUCKET_NAME") or f"sa-rag-demo-{UNIQUE_SUFFIX}"
VECTOR_INDEX_NAME: str = os.environ.get("VECTOR_INDEX_NAME") or "hr-policy-index"

# ── Embedding ─────────────────────────────────────────────────────────────────
EMBEDDING_MODEL_ID: str = (
    os.environ.get("BEDROCK_EMBEDDING_MODEL_ID") or "amazon.titan-embed-text-v2:0"
)
EMBEDDING_DIMENSIONS: int = int(os.environ.get("EMBEDDING_DIMENSIONS", "1024"))
if EMBEDDING_DIMENSIONS not in (256, 512, 1024):
    raise ValueError("EMBEDDING_DIMENSIONS must be 256, 512, or 1024 for Titan Text Embeddings V2.")

# ── Generation ────────────────────────────────────────────────────────────────
GENERATION_MODEL_ID: str = os.environ.get("BEDROCK_GENERATION_MODEL_ID", "")

# ── Terraform outputs (paste from: terraform output -raw env_export_block) ────
# These are set by Terraform and consumed here — no hardcoding needed.
IAM_ROLE_ARN: str         = os.environ.get("AWS_ROLE_ARN", "")
KMS_KEY_ARN: str          = os.environ.get("KMS_KEY_ARN", "")
CLOUDWATCH_LOG_GROUP: str = os.environ.get("CLOUDWATCH_LOG_GROUP", "")

# ── Distance / retrieval ──────────────────────────────────────────────────────
DISTANCE_METRIC: str = os.environ.get("DISTANCE_METRIC", "cosine")
NO_ANSWER_DISTANCE_THRESHOLD = None   # set a float (e.g. 0.75) to enable retrieval-layer refusal

# ── Chunking ──────────────────────────────────────────────────────────────────
CHUNK_STRATEGY: str = os.environ.get("CHUNK_STRATEGY", "recursive")   # "fixed" or "recursive"
CHUNK_SIZE: int = int(os.environ.get("CHUNK_SIZE", "400"))
CHUNK_OVERLAP: int = int(os.environ.get("CHUNK_OVERLAP", "50"))

# ── Geo-aware generation model candidates ─────────────────────────────────────
_US_REGIONS = {"us-east-1", "us-east-2", "us-west-1", "us-west-2", "ca-central-1", "ca-west-1"}
_EU_REGIONS = {
    "eu-central-1", "eu-central-2", "eu-north-1", "eu-south-1", "eu-south-2",
    "eu-west-1", "eu-west-2", "eu-west-3",
}
_AU_REGIONS = {"ap-southeast-2", "ap-southeast-4", "ap-southeast-6"}


def _geo_prefix(region: str) -> str:
    if region in _US_REGIONS:
        return "us"
    if region in _EU_REGIONS:
        return "eu"
    if region in _AU_REGIONS:
        return "au"
    return "global"


def preferred_generation_model_ids() -> List[str]:
    geo = _geo_prefix(AWS_REGION)
    candidates = []
    for prefix in dict.fromkeys([geo, "global"]):
        candidates.append(f"{prefix}.anthropic.claude-haiku-4-5-20251001-v1:0")
    candidates += [
        "anthropic.claude-haiku-4-5-20251001-v1:0",
        "amazon.nova-lite-v1:0",
        "amazon.nova-micro-v1:0",
    ]
    return list(dict.fromkeys(candidates))


PREFERRED_GENERATION_MODEL_IDS: List[str] = preferred_generation_model_ids()
