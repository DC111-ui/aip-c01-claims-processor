"""Command line entry point.

    python -m claims_poc upload                       # upload sample claims + policies to S3
    python -m claims_poc process claims/claim-001-auto.txt --model haiku-4.5
    python -m claims_poc compare                      # every claim x every model -> results/

AWS credentials come from the standard chain (set AWS_PROFILE / AWS_REGION).
Bucket and guardrail are read from the CloudFormation stack outputs.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import boto3

from .evaluate import score_result, write_report
from .invoker import MODELS, ModelInvoker
from .processor import ClaimProcessor
from .rag import PolicyRetriever

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def stack_outputs(session: boto3.Session, stack_name: str) -> dict[str, str]:
    stack = session.client("cloudformation").describe_stacks(StackName=stack_name)["Stacks"][0]
    return {o["OutputKey"]: o["OutputValue"] for o in stack.get("Outputs", [])}


def build_processor(session: boto3.Session, stack_name: str) -> ClaimProcessor:
    outputs = stack_outputs(session, stack_name)
    s3 = session.client("s3")
    runtime = session.client("bedrock-runtime")
    retriever = PolicyRetriever(s3, runtime, outputs["BucketName"])
    retriever.load()
    return ClaimProcessor(
        s3=s3,
        bedrock_runtime=runtime,
        bucket=outputs["BucketName"],
        guardrail_id=outputs["GuardrailId"],
        guardrail_version=outputs["GuardrailVersion"],
        invoker=ModelInvoker(client=runtime),
        retriever=retriever,
    )


def cmd_upload(session: boto3.Session, args: argparse.Namespace) -> None:
    bucket = stack_outputs(session, args.stack)["BucketName"]
    s3 = session.client("s3")
    for folder in ("claims", "policies"):
        for path in sorted((DATA / folder).iterdir()):
            key = f"{folder}/{path.name}"
            s3.upload_file(str(path), bucket, key)
            print(f"uploaded s3://{bucket}/{key}")


def cmd_process(session: boto3.Session, args: argparse.Namespace) -> None:
    processor = build_processor(session, args.stack)
    result = processor.process(args.key, args.model, args.escalate_to)
    print(json.dumps(result.to_dict(), indent=2))


def cmd_compare(session: boto3.Session, args: argparse.Namespace) -> None:
    truth = json.loads((DATA / "ground_truth.json").read_text(encoding="utf-8"))
    processor = build_processor(session, args.stack)
    runs = [(m, None) for m in args.models] + [(m, args.escalate_to) for m in args.cascade]
    rows = []
    for model, escalate_to in runs:
        for key, expected in truth.items():
            label = f"{model} -> {escalate_to}" if escalate_to else model
            print(f"{label:<24} {key} ...", end=" ", flush=True)
            result = processor.process(key, model, escalate_to).to_dict()
            result["score"] = score_result(result, expected)
            rows.append(result)
            print(f"accuracy={result['score']['field_accuracy']:.0%} verdict={result['verdict']} "
                  f"latency={result['latency_ms']}ms cost=${result['cost_usd']:.5f}")
    report = write_report(rows, ROOT / "results")
    print(f"\nReport written to {report.relative_to(ROOT)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="claims_poc")
    parser.add_argument("--stack", default=os.environ.get("CLAIMS_STACK", "claims-poc"))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("upload")
    p = sub.add_parser("process")
    p.add_argument("key", help="S3 key of the claim document, e.g. claims/claim-001-auto.txt")
    p.add_argument("--model", default="haiku-4.5", choices=sorted(MODELS))
    p.add_argument("--escalate-to", choices=sorted(MODELS), help="stronger model for claims the rules flag")
    c = sub.add_parser("compare")
    c.add_argument("--models", nargs="+", default=list(MODELS), choices=sorted(MODELS))
    c.add_argument("--cascade", nargs="*", default=["nova-micro", "nova-lite"], choices=sorted(MODELS),
                   help="cheap models to also run with escalation of flagged claims")
    c.add_argument("--escalate-to", default="haiku-4.5", choices=sorted(MODELS))
    args = parser.parse_args(argv)

    session = boto3.Session(region_name=os.environ.get("AWS_REGION", "us-east-1"))
    {"upload": cmd_upload, "process": cmd_process, "compare": cmd_compare}[args.command](session, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
