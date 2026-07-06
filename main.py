"""
main.py
-------
Entry point for the Bedrock RAG pipeline.

Two modes:
  python main.py ingest   — chunk, embed, and index all documents
  python main.py query    — run interactive Q&A against the index

Usage:
  # 1. Set environment variables (or export them in your shell)
  export AWS_REGION=us-east-1
  export VECTOR_BUCKET_NAME=my-rag-bucket

  # 2. Install dependencies
  pip install -r requirements.txt

  # 3. Run ingest
  python main.py ingest

  # 4. Run queries
  python main.py query
"""

import argparse
import logging
import sys

from config import settings
from core.aws_clients import create_clients, run_preflight
from pipeline.documents import DOCUMENTS
from pipeline.chunker import chunk_documents
from pipeline.embedder import embed_chunks
from pipeline.indexer import create_vector_bucket, create_vector_index, write_vectors
from query.rag import generate_answer
from utils.helpers import format_distance, show_answer

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Ingest pipeline ───────────────────────────────────────────────────────────

def run_ingest(clients) -> None:
    logger.info("=== INGEST MODE ===")

    # Step 1: chunk
    chunks = chunk_documents(DOCUMENTS)
    logger.info("Produced %d chunks from %d documents.", len(chunks), len(DOCUMENTS))

    # Step 2: embed (concurrent, with retry and checkpoint)
    chunks = embed_chunks(clients.bedrock_runtime, chunks, resume=True)

    # Step 3: create bucket + index (idempotent)
    create_vector_bucket(clients.s3vectors)
    create_vector_index(clients.s3vectors)

    # Step 4: write vectors
    write_vectors(clients.s3vectors, chunks)

    logger.info("=== INGEST COMPLETE ===")


# ── Query / Q&A ───────────────────────────────────────────────────────────────

def run_query(clients) -> None:
    logger.info("=== QUERY MODE ===")

    # Standard test questions
    test_questions = [
        "How many weeks of parental leave does Acme offer to primary caregivers?",
        "Can I work from another country?",
        "What is the maximum I can get reimbursed for AWS certifications?",
        "How does the stock vesting schedule work?",
        "Do I need to report foreign travel?",
        "What's our policy on free lunches?",   # out-of-corpus — should return no-answer
    ]

    for q in test_questions:
        print("\n" + "=" * 70)
        result = generate_answer(
            clients.bedrock_runtime,
            clients.s3vectors,
            clients.generation_model_id,
            question=q,
            top_k=3,
            tenant_id=None,   # set to authenticated user's tenant in production
        )
        print(f"Q: {q}")
        show_answer(result["answer"], header="A")

        if result["retrieved_chunks"]:
            top = result["retrieved_chunks"][0]
            print(f"   top distance: {format_distance(top.get('distance'))}")
        else:
            print("   (no chunks retrieved)")

    # topK experiment
    print("\n" + "=" * 70)
    print("topK experiment — 'What benefits do I get while on parental leave?'")
    for k in [1, 3, 5, 7]:
        r = generate_answer(
            clients.bedrock_runtime,
            clients.s3vectors,
            clients.generation_model_id,
            question="What benefits do I get while on parental leave?",
            top_k=k,
        )
        top_dist = r["retrieved_chunks"][0].get("distance") if r["retrieved_chunks"] else None
        dist_text = f"{top_dist:.4f}" if isinstance(top_dist, (int, float)) else "n/a"
        print(f"\n--- topK={k}  top_distance={dist_text} ---")
        show_answer(r["answer"])

    # Distance threshold demo
    print("\n" + "=" * 70)
    print("Distance threshold demo — out-of-corpus question")
    no_answer_q = "What's our policy on free lunches?"
    baseline = generate_answer(
        clients.bedrock_runtime,
        clients.s3vectors,
        clients.generation_model_id,
        question=no_answer_q,
        top_k=3,
    )
    observed = (
        baseline["retrieved_chunks"][0].get("distance")
        if baseline["retrieved_chunks"] else None
    )
    print(f"Top distance without threshold: {format_distance(observed)}")

    if isinstance(observed, (int, float)):
        demo_threshold = max(0.0, float(observed) - 1e-6)
        thresholded = generate_answer(
            clients.bedrock_runtime,
            clients.s3vectors,
            clients.generation_model_id,
            question=no_answer_q,
            top_k=3,
            distance_threshold=demo_threshold,
        )
        print(f"With threshold {demo_threshold:.6f}:")
        show_answer(thresholded["answer"], header="Answer")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Bedrock RAG pipeline")
    parser.add_argument(
        "mode",
        choices=["ingest", "query"],
        help="ingest: chunk/embed/index documents. query: run Q&A.",
    )
    args = parser.parse_args()

    logger.info("Region:      %s", settings.AWS_REGION)
    logger.info("Bucket:      %s", settings.VECTOR_BUCKET_NAME)
    logger.info("Index:       %s", settings.VECTOR_INDEX_NAME)
    if settings.IAM_ROLE_ARN:
        logger.info("IAM Role:    %s", settings.IAM_ROLE_ARN)
    if settings.KMS_KEY_ARN:
        logger.info("KMS Key:     %s", settings.KMS_KEY_ARN)
    if settings.CLOUDWATCH_LOG_GROUP:
        logger.info("CW LogGroup: %s", settings.CLOUDWATCH_LOG_GROUP)

    clients = create_clients()
    clients = run_preflight(clients)

    if args.mode == "ingest":
        run_ingest(clients)
    else:
        run_query(clients)


if __name__ == "__main__":
    main()
