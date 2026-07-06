variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Short name used as prefix for all resources"
  type        = string
  default     = "rag-bedrock"
}

variable "environment" {
  description = "Environment tag (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "embedding_model_arn" {
  description = "Bedrock embedding model ARN. Titan Text Embeddings V2 default."
  type        = string
  default     = "arn:aws:bedrock:*::foundation-model/amazon.titan-embed-text-v2:0"
}

variable "generation_model_arn" {
  description = "Bedrock generation model ARN. Haiku default."
  type        = string
  default     = "arn:aws:bedrock:*::foundation-model/anthropic.claude-haiku-4-5-20251001-v1:0"
}

variable "enable_kms" {
  description = "Set to true to create a customer-managed KMS key for S3 Vectors encryption (recommended for FedRAMP/HIPAA)"
  type        = bool
  default     = false
}

variable "enable_bedrock_logging" {
  description = "Enable Bedrock model invocation logging to CloudWatch"
  type        = bool
  default     = true
}

variable "log_retention_days" {
  description = "CloudWatch log group retention in days"
  type        = number
  default     = 30
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}
