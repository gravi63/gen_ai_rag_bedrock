# ─────────────────────────────────────────────────────────────────────────────
# Outputs — paste these as environment variables before running Python
#
# Quick copy-paste:
#   terraform output -raw env_export_block
# ─────────────────────────────────────────────────────────────────────────────

output "iam_role_arn" {
  description = "ARN of the RAG pipeline IAM role. Set as AWS_ROLE_ARN if assuming the role explicitly."
  value       = aws_iam_role.rag_pipeline.arn
}

output "iam_role_name" {
  description = "Name of the RAG pipeline IAM role."
  value       = aws_iam_role.rag_pipeline.name
}

output "aws_region" {
  description = "AWS region where resources were created."
  value       = local.region
}

output "kms_key_arn" {
  description = "ARN of the CMK for S3 Vectors encryption. Empty if enable_kms = false."
  value       = var.enable_kms ? aws_kms_key.s3_vectors[0].arn : ""
}

output "kms_key_alias" {
  description = "Alias of the CMK. Empty if enable_kms = false."
  value       = var.enable_kms ? aws_kms_alias.s3_vectors[0].name : ""
}

output "cloudwatch_log_group_pipeline" {
  description = "CloudWatch log group name for Python pipeline logs."
  value       = aws_cloudwatch_log_group.pipeline.name
}

output "cloudwatch_log_group_bedrock" {
  description = "CloudWatch log group name for Bedrock invocation logs. Empty if logging disabled."
  value       = var.enable_bedrock_logging ? aws_cloudwatch_log_group.bedrock_invocations[0].name : ""
}

# ── Convenience block — copy-paste export block for your shell ────────────────

output "env_export_block" {
  description = "Copy-paste this into your shell before running Python."
  value = <<-ENV
    # ── Paste these into your shell ───────────────────────────────────────
    export AWS_REGION="${local.region}"
    export AWS_ROLE_ARN="${aws_iam_role.rag_pipeline.arn}"
    export KMS_KEY_ARN="${var.enable_kms ? aws_kms_key.s3_vectors[0].arn : ""}"
    export CLOUDWATCH_LOG_GROUP="${aws_cloudwatch_log_group.pipeline.name}"

    # ── Set these manually (not managed by Terraform) ─────────────────────
    # export VECTOR_BUCKET_NAME=<your-bucket-name>      # created by Python ingest
    # export VECTOR_INDEX_NAME=hr-policy-index          # created by Python ingest
    # export BEDROCK_GENERATION_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0
    # export EMBEDDING_DIMENSIONS=1024
    # ─────────────────────────────────────────────────────────────────────
  ENV
}
