# Bedrock RAG Pipeline

End-to-end RAG using AWS S3 Vectors + Bedrock Titan Embeddings + Bedrock generation models.

## Project structure

```
rag_bedrock/
├── main.py                  # entry point — run ingest or query
├── requirements.txt
├── config/
│   └── settings.py          # all config via environment variables
├── core/
│   └── aws_clients.py       # boto3 client creation + preflight checks
├── pipeline/
│   ├── documents.py         # document corpus (replace with your loader)
│   ├── chunker.py           # fixed-size and recursive chunking (tiktoken-accurate)
│   ├── embedder.py          # concurrent embedding with retry + checkpointing
│   └── indexer.py           # S3 Vectors bucket/index creation + vector writes
├── query/
│   ├── retriever.py         # semantic search with tenant isolation
│   └── rag.py               # prompt build + generation + distance threshold
└── utils/
    └── helpers.py           # shared utilities
```

## Quickstart

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure AWS credentials
```bash
aws configure
# or use IAM role / instance profile in SageMaker / EC2
```

### 3. Set environment variables
```bash
export AWS_REGION=us-east-1
export VECTOR_BUCKET_NAME=my-rag-bucket        # optional — auto-generated if not set
export BEDROCK_GENERATION_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0
```

### 4. Run ingest (chunk → embed → index)
```bash
python main.py ingest
```

### 5. Run queries
```bash
python main.py query
```

## Required IAM permissions

```json
{
  "Effect": "Allow",
  "Action": [
    "s3vectors:CreateVectorBucket",
    "s3vectors:GetVectorBucket",
    "s3vectors:ListVectorBuckets",
    "s3vectors:CreateIndex",
    "s3vectors:GetIndex",
    "s3vectors:ListIndexes",
    "s3vectors:PutVectors",
    "s3vectors:ListVectors",
    "s3vectors:QueryVectors",
    "s3vectors:GetVectors",
    "bedrock:InvokeModel",
    "bedrock:Converse",
    "bedrock:ListFoundationModels"
  ],
  "Resource": "*"
}
```

## Key fixes vs original notebook

| Issue | Original | Fixed |
|---|---|---|
| Embedding retry | No retry — one throttle kills the run | tenacity exponential backoff |
| Embedding concurrency | Sequential loop | ThreadPoolExecutor (5 workers) |
| Embedding checkpoint | None — restart from zero | Checkpoint to `.embed_checkpoint.pkl` |
| Token counting | `1 token ≈ 4 chars` proxy | tiktoken `cl100k_base` tokenizer |
| Global mutation | `global GENERATION_MODEL_ID` | Returned from preflight, passed explicitly |
| Tenant isolation | Filter accepted from caller | Injected from auth context only |
| Observability | `print()` only | `logging` throughout + token usage from response |
| Jupyter dependency | `IPython.display` everywhere | Plain Python — runs in VSCode / terminal |
