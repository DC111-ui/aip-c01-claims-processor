#!/usr/bin/env bash
# Deploy the stack and upload sample data. Uses AWS_PROFILE / AWS_REGION from your environment.
set -euo pipefail
STACK="${CLAIMS_STACK:-claims-poc}"
REGION="${AWS_REGION:-us-east-1}"
aws sts get-caller-identity --query Account --output text
aws cloudformation deploy --region "$REGION" --stack-name "$STACK" \
  --template-file "$(dirname "$0")/../infra/stack.yaml" --tags Project=claims-poc
python -m claims_poc --stack "$STACK" upload
