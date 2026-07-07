# Bedrock RAG Pipeline

End-to-end RAG pipeline on AWS using Bedrock (Titan embeddings + Claude), S3 Vectors as the vector store, and Terraform for IAM and observability — fully modular Python with concurrent embedding, retry logic, and multi-tenant metadata filtering.

## Architecture Diagram

<img width="1472" height="1280" alt="image" src="https://github.com/user-attachments/assets/9c12de12-aa66-4fae-8f81-95428eb99f91" />

## Project structure

```
gen_ai_rag_bedrock/
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

### 1. Run Terraform to create IAM and Log groups
```bash
cd gen_ai_rag_bedrock/terraform
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars with your values
terraform init
terraform apply
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure AWS credentials
```bash
aws configure
# or use IAM role / instance profile in SageMaker / EC2
```

### 3. Set environment variables
```bash
export AWS_REGION=us-east-1
export VECTOR_BUCKET_NAME=my-rag-bucket        # optional — auto-generated if not set
export BEDROCK_GENERATION_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0
export AWS_ROLE_ARN="arn:aws:iam::123456789:role/rag-bedrock-dev-pipeline-role"
export KMS_KEY_ARN=""  # only if enable_kms = true
export CLOUDWATCH_LOG_GROUP="/app/rag-bedrock-dev/pipeline"
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
