terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.30"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = merge(
      {
        Project     = var.project_name
        Environment = var.environment
        ManagedBy   = "terraform"
      },
      var.tags
    )
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.region
  prefix     = "${var.project_name}-${var.environment}"
}


# ─────────────────────────────────────────────────────────────────────────────
# KMS — customer managed key for S3 Vectors encryption
# Only created when enable_kms = true (required for FedRAMP/HIPAA)
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_kms_key" "s3_vectors" {
  count = var.enable_kms ? 1 : 0

  description             = "CMK for ${local.prefix} S3 Vectors bucket and index"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowRootAccount"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${local.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "AllowRAGRole"
        Effect = "Allow"
        Principal = {
          AWS = aws_iam_role.rag_pipeline.arn
        }
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey",
          "kms:DescribeKey"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_kms_alias" "s3_vectors" {
  count = var.enable_kms ? 1 : 0

  name          = "alias/${local.prefix}-s3-vectors"
  target_key_id = aws_kms_key.s3_vectors[0].key_id
}


# ─────────────────────────────────────────────────────────────────────────────
# IAM — role for the RAG pipeline (assumed by the Python process / Lambda / EC2)
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_iam_role" "rag_pipeline" {
  name        = "${local.prefix}-pipeline-role"
  description = "Role assumed by the RAG pipeline Python process"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # Allow EC2, Lambda, SageMaker, and direct user assumption.
        # Restrict Principal to the specific service or user ARN in production.
        Sid    = "AllowAssumeRole"
        Effect = "Allow"
        Principal = {
          Service = [
            "ec2.amazonaws.com",
            "lambda.amazonaws.com",
            "sagemaker.amazonaws.com"
          ]
          AWS = "arn:aws:iam::${local.account_id}:root"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}


# ── S3 Vectors permissions ────────────────────────────────────────────────────
# Note: S3 Vectors bucket/index creation is NOT yet supported in Terraform
# (as of mid-2025 — tracked in hashicorp/terraform-provider-aws#43409).
# The Python pipeline (pipeline/indexer.py) handles bucket and index creation.
# Once Terraform support lands, move those resources here and remove from Python.

resource "aws_iam_policy" "s3_vectors" {
  name        = "${local.prefix}-s3-vectors-policy"
  description = "S3 Vectors permissions for RAG pipeline"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3VectorsReadWrite"
        Effect = "Allow"
        Action = [
          "s3vectors:CreateVectorBucket",
          "s3vectors:GetVectorBucket",
          "s3vectors:ListVectorBuckets",
          "s3vectors:DeleteVectorBucket",
          "s3vectors:CreateIndex",
          "s3vectors:GetIndex",
          "s3vectors:ListIndexes",
          "s3vectors:DeleteIndex",
          "s3vectors:PutVectors",
          "s3vectors:GetVectors",
          "s3vectors:ListVectors",
          "s3vectors:QueryVectors",
          "s3vectors:DeleteVectors"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "s3_vectors" {
  role       = aws_iam_role.rag_pipeline.name
  policy_arn = aws_iam_policy.s3_vectors.arn
}


# ── Bedrock permissions ───────────────────────────────────────────────────────

resource "aws_iam_policy" "bedrock" {
  name        = "${local.prefix}-bedrock-policy"
  description = "Bedrock model invocation permissions for RAG pipeline"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "BedrockInvokeModels"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
          "bedrock:Converse",
          "bedrock:ConverseStream"
        ]
        Resource = [
          var.embedding_model_arn,
          var.generation_model_arn,
          # Allow geo-prefixed inference profiles (us.*, eu.*, global.*)
          "arn:aws:bedrock:${local.region}::foundation-model/*",
          "arn:aws:bedrock:${local.region}:${local.account_id}:inference-profile/*"
        ]
      },
      {
        Sid    = "BedrockListModels"
        Effect = "Allow"
        Action = [
          "bedrock:ListFoundationModels",
          "bedrock:GetFoundationModel"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "bedrock" {
  role       = aws_iam_role.rag_pipeline.name
  policy_arn = aws_iam_policy.bedrock.arn
}


# ── KMS permissions (only if KMS enabled) ────────────────────────────────────

resource "aws_iam_policy" "kms" {
  count = var.enable_kms ? 1 : 0

  name        = "${local.prefix}-kms-policy"
  description = "KMS permissions for S3 Vectors CMK encryption"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "KMSAccess"
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey",
          "kms:DescribeKey"
        ]
        Resource = aws_kms_key.s3_vectors[0].arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "kms" {
  count = var.enable_kms ? 1 : 0

  role       = aws_iam_role.rag_pipeline.name
  policy_arn = aws_iam_policy.kms[0].arn
}


# ── STS permissions (for preflight identity check) ───────────────────────────

resource "aws_iam_policy" "sts" {
  name        = "${local.prefix}-sts-policy"
  description = "STS GetCallerIdentity for preflight check"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "STSGetCallerIdentity"
        Effect   = "Allow"
        Action   = "sts:GetCallerIdentity"
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "sts" {
  role       = aws_iam_role.rag_pipeline.name
  policy_arn = aws_iam_policy.sts.arn
}


# ─────────────────────────────────────────────────────────────────────────────
# CloudWatch — log group for Bedrock invocation logging + pipeline logs
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_cloudwatch_log_group" "bedrock_invocations" {
  count = var.enable_bedrock_logging ? 1 : 0

  name              = "/aws/bedrock/${local.prefix}/invocations"
  retention_in_days = var.log_retention_days
  kms_key_id        = var.enable_kms ? aws_kms_key.s3_vectors[0].arn : null
}

resource "aws_cloudwatch_log_group" "pipeline" {
  name              = "/app/${local.prefix}/pipeline"
  retention_in_days = var.log_retention_days
  kms_key_id        = var.enable_kms ? aws_kms_key.s3_vectors[0].arn : null
}


# ── IAM role for Bedrock to write to CloudWatch ───────────────────────────────

resource "aws_iam_role" "bedrock_logging" {
  count = var.enable_bedrock_logging ? 1 : 0

  name        = "${local.prefix}-bedrock-logging-role"
  description = "Allows Bedrock to write invocation logs to CloudWatch"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "bedrock.amazonaws.com"
        }
        Action = "sts:AssumeRole"
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = local.account_id
          }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "bedrock_logging" {
  count = var.enable_bedrock_logging ? 1 : 0

  name = "${local.prefix}-bedrock-logging-policy"
  role = aws_iam_role.bedrock_logging[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.bedrock_invocations[0].arn}:*"
      }
    ]
  })
}


# ── Bedrock model invocation logging config ───────────────────────────────────

resource "aws_bedrock_model_invocation_logging_configuration" "this" {
  count = var.enable_bedrock_logging ? 1 : 0

  logging_config {
    cloudwatch_config {
      log_group_name = aws_cloudwatch_log_group.bedrock_invocations[0].name
      role_arn       = aws_iam_role.bedrock_logging[0].arn
    }
    embedding_data_delivery_enabled = true
    text_data_delivery_enabled      = true
    image_data_delivery_enabled     = false
  }
}
