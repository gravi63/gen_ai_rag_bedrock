"""
core/aws_clients.py
-------------------
Creates and validates all AWS service clients.
Returns a named tuple so callers get explicit references — no global mutation.
"""

import logging
from typing import Any, Dict, List, NamedTuple, Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError, UnknownServiceError

from config import settings
from utils.helpers import as_float32_list, client_error_code, client_error_summary

logger = logging.getLogger(__name__)

BOTO_CONFIG = Config(
    retries={"max_attempts": 10, "mode": "adaptive"},
    connect_timeout=10,
    read_timeout=60,
    user_agent_extra="s3-vectors-rag/1.0",
)


class AWSClients(NamedTuple):
    s3vectors: Any
    bedrock_runtime: Any
    bedrock: Any
    sts: Any
    generation_model_id: str   # resolved during preflight — no global needed


def create_clients() -> AWSClients:
    """Create all required AWS clients and validate the s3vectors service model is available."""
    session = boto3.Session(region_name=settings.AWS_REGION)

    try:
        available = set(session.get_available_services())
        if "s3vectors" not in available:
            raise RuntimeError(
                "botocore service model does not include 's3vectors'. "
                "Run: pip install --upgrade boto3 botocore"
            )
        s3vectors = session.client("s3vectors", config=BOTO_CONFIG)
        bedrock_runtime = session.client("bedrock-runtime", config=BOTO_CONFIG)
        bedrock = session.client("bedrock", config=BOTO_CONFIG)
        sts = session.client("sts", config=BOTO_CONFIG)
    except UnknownServiceError as exc:
        raise RuntimeError("Could not create required AWS clients. Upgrade boto3/botocore.") from exc

    return AWSClients(
        s3vectors=s3vectors,
        bedrock_runtime=bedrock_runtime,
        bedrock=bedrock,
        sts=sts,
        generation_model_id="",   # resolved in run_preflight()
    )


# ── Preflight helpers ─────────────────────────────────────────────────────────

def _list_active_models(bedrock_client) -> Dict[str, Dict[str, Any]]:
    try:
        resp = bedrock_client.list_foundation_models(byOutputModality="TEXT")
        return {m["modelId"]: m for m in resp.get("modelSummaries", [])}
    except ClientError as exc:
        logger.warning("Could not list Bedrock foundation models: %s", client_error_summary(exc))
        return {}


def _resolve_generation_model(bedrock_runtime_client, bedrock_client) -> str:
    """Try candidate models in order, return the first that responds. No global mutation."""
    if settings.GENERATION_MODEL_ID:
        return settings.GENERATION_MODEL_ID

    models = _list_active_models(bedrock_client)
    candidates = settings.PREFERRED_GENERATION_MODEL_IDS

    failures = []
    for candidate in candidates:
        try:
            resp = bedrock_runtime_client.converse(
                modelId=candidate,
                messages=[{"role": "user", "content": [{"text": "Reply with exactly: OK"}]}],
                inferenceConfig={"maxTokens": 8, "temperature": 0.0},
            )
            selected = candidate
            logger.info("Generation model resolved: %s", selected)
            return selected
        except ClientError as exc:
            failures.append(f"{candidate}: {client_error_summary(exc)}")
        except Exception as exc:
            failures.append(f"{candidate}: {type(exc).__name__}: {exc}")

    raise RuntimeError(
        "No generation model worked. Set BEDROCK_GENERATION_MODEL_ID env var.\n"
        "Tried:\n  - " + "\n  - ".join(failures)
    )


def run_preflight(clients: AWSClients) -> AWSClients:
    """
    Validate AWS access before touching any resources.
    Returns a new AWSClients with generation_model_id populated.
    """
    logger.info("Running AWS preflight checks ...")
    logger.info("Region:           %s", settings.AWS_REGION)

    # Identity check
    try:
        identity = clients.sts.get_caller_identity()
        logger.info("AWS account:      %s", identity.get("Account"))
        logger.info("AWS principal:    %s", identity.get("Arn"))
    except (NoCredentialsError, PartialCredentialsError) as exc:
        raise RuntimeError("AWS credentials not found or incomplete.") from exc
    except ClientError as exc:
        raise RuntimeError(f"STS GetCallerIdentity failed: {client_error_summary(exc)}") from exc

    # S3 Vectors access
    try:
        buckets = clients.s3vectors.list_vector_buckets().get("vectorBuckets", [])
        logger.info("S3 Vectors:       OK (%d visible buckets)", len(buckets))
    except ClientError as exc:
        raise RuntimeError(f"S3 Vectors access check failed: {client_error_summary(exc)}") from exc

    # Embedding model access
    try:
        import json
        resp = clients.bedrock_runtime.invoke_model(
            modelId=settings.EMBEDDING_MODEL_ID,
            body=json.dumps({
                "inputText": "preflight check",
                "dimensions": settings.EMBEDDING_DIMENSIONS,
                "normalize": True,
            }),
            accept="application/json",
            contentType="application/json",
        )
        import json as _json
        body = _json.loads(resp["body"].read())
        emb = body.get("embedding") or (body.get("embeddingsByType") or {}).get("float")
        vec = as_float32_list(emb, expected_dimensions=settings.EMBEDDING_DIMENSIONS)
        logger.info("Embedding model:  OK (%d dims)", len(vec))
    except ClientError as exc:
        raise RuntimeError(f"Embedding model access failed: {client_error_summary(exc)}") from exc

    # Generation model resolution
    gen_model_id = _resolve_generation_model(clients.bedrock_runtime, clients.bedrock)
    logger.info("Generation model: OK (%s)", gen_model_id)

    if gen_model_id.startswith("global."):
        logger.warning(
            "Selected a global cross-region inference profile. "
            "Confirm data residency requirements before production use."
        )

    logger.info("Preflight complete.")

    # Return new AWSClients with resolved model — avoids global mutation
    return AWSClients(
        s3vectors=clients.s3vectors,
        bedrock_runtime=clients.bedrock_runtime,
        bedrock=clients.bedrock,
        sts=clients.sts,
        generation_model_id=gen_model_id,
    )
