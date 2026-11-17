#!/usr/bin/env bash
# Empty the bucket and delete the stack, so nothing is left behind.
set -euo pipefail
STACK="${CLAIMS_STACK:-claims-poc}"
REGION="${AWS_REGION:-us-east-1}"
BUCKET=$(aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK" \
  --query "Stacks[0].Outputs[?OutputKey=='BucketName'].OutputValue" --output text)
aws s3 rm "s3://$BUCKET" --recursive --region "$REGION"
aws cloudformation delete-stack --region "$REGION" --stack-name "$STACK"
aws cloudformation wait stack-delete-complete --region "$REGION" --stack-name "$STACK"
echo "Stack $STACK deleted."
