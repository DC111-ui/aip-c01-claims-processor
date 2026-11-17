"""End-to-end claim processing pipeline (Skill 1.1.2: proof of concept).

    S3 claim document
      -> extract fields (Converse with forced tool use, temperature 0)
      -> validate (schema, then business rules checked against the policy record)
      -> retrieve the relevant policy sections (RAG, filtered to the claimant's policy)
      -> generate the summary (Converse, grounded in the fields, the excerpts and the validation notes)
      -> ApplyGuardrail (mask PII in the summary before it is shared)
      -> validate the summary
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .invoker import InvocationResult, ModelInvoker, ToolSpec
from .prompts import PromptTemplateManager
from .rag import PolicyRetriever
from .validator import CLAIM_SCHEMA, ClaimValidator, detect_verdict

EXTRACT_TOOL = ToolSpec(
    name="record_claim",
    description="Record the structured details of an insurance claim.",
    json_schema=CLAIM_SCHEMA,
)


@dataclass
class ClaimResult:
    document_key: str
    model: str
    summary_model: str
    fields: dict[str, Any] | None
    extraction_issues: list[dict[str, str]]
    retrieved_sections: list[dict[str, Any]]
    summary: str
    summary_issues: list[dict[str, str]]
    verdict: str | None
    guardrail_action: str
    pii_masked: list[str]
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cost_usd: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ClaimProcessor:
    def __init__(
        self,
        *,
        s3: Any,
        bedrock_runtime: Any,
        bucket: str,
        guardrail_id: str,
        guardrail_version: str,
        invoker: ModelInvoker,
        retriever: PolicyRetriever,
        prompts: PromptTemplateManager | None = None,
        validator: ClaimValidator | None = None,
    ) -> None:
        self._s3 = s3
        self._bedrock = bedrock_runtime
        self._bucket = bucket
        self._guardrail = (guardrail_id, guardrail_version)
        self._invoker = invoker
        self._retriever = retriever
        self._prompts = prompts or PromptTemplateManager()
        self._validator = validator or ClaimValidator()

    def upload(self, path: Path, key: str) -> str:
        self._s3.upload_file(str(path), self._bucket, key, ExtraArgs={"ContentType": "text/plain; charset=utf-8"})
        return f"s3://{self._bucket}/{key}"

    def process(self, key: str, model: str, escalate_to: str | None = None) -> ClaimResult:
        """Process one claim. With escalate_to set, the summary step is handed to the stronger model
        only when the rule checks raised issues (model cascading: cheap by default, strong when needed)."""
        document = self._s3.get_object(Bucket=self._bucket, Key=key)["Body"].read().decode("utf-8")

        # 1. Extraction: deterministic settings and schema-constrained output.
        prompt = self._prompts.render("extract_claim", document_text=document)
        extraction = self._invoker.invoke(model, user=prompt.user, system=prompt.system,
                                          max_tokens=600, temperature=0.0, tool=EXTRACT_TOOL)
        fields = extraction.tool_input
        if fields and fields.get("policy_number"):
            fields["policy_number"] = str(fields["policy_number"]).strip().upper()

        # 2. Validate fields and business rules before spending tokens on a summary.
        policy = self._retriever.get_policy((fields or {}).get("policy_number"))
        extraction_report = self._validator.validate_extraction(fields, policy)

        # 3. Retrieve the policy sections relevant to this incident.
        #    One embedding for a multi-incident description can miss sections (see README findings),
        #    so each sentence is used as its own query and the results are merged.
        claim_type = (fields or {}).get("claim_type", "")
        description = (fields or {}).get("incident_description", "")
        queries = [f"{claim_type} claim: {s}" for s in re.split(r"(?<=[.!?;])\s+|,\s+and\s+", description) if s.strip()]
        sections = self._retriever.retrieve_multi(queries or [claim_type], policy.policy_number if policy else None,
                                                  k_per_query=2, k=4)
        excerpts = "\n\n".join(f"### {s.heading} ({s.policy_number})\n{s.text}" for s in sections) \
            or "No policy found for this claim."

        # 4. Summarise, grounded in the fields, the excerpts and the validation notes.
        prompt = self._prompts.render(
            "summarize_claim",
            fields=json.dumps(fields or {}, indent=2),
            policy_excerpts=excerpts,
            validation_notes=extraction_report.as_notes(),
        )
        summary_model = escalate_to if escalate_to and extraction_report.issues else model
        summary = self._invoker.invoke(summary_model, user=prompt.user, system=prompt.system,
                                       max_tokens=400, temperature=0.2)

        # 5. Mask PII in the summary before it leaves the claims system.
        guarded_text, action, masked = self._apply_guardrail(summary.text)
        summary_report = self._validator.validate_summary(guarded_text, extraction_report)

        calls: tuple[InvocationResult, ...] = (extraction, summary)
        return ClaimResult(
            document_key=key,
            model=f"{extraction.model} -> {escalate_to}" if escalate_to else extraction.model,
            summary_model=summary.model,
            fields=fields,
            extraction_issues=[asdict(i) for i in extraction_report.issues],
            retrieved_sections=[{"heading": s.heading, "score": s.score} for s in sections],
            summary=guarded_text,
            summary_issues=[asdict(i) for i in summary_report.issues],
            verdict=detect_verdict(guarded_text),
            guardrail_action=action,
            pii_masked=masked,
            input_tokens=sum(c.input_tokens for c in calls),
            output_tokens=sum(c.output_tokens for c in calls),
            latency_ms=sum(c.latency_ms for c in calls),
            cost_usd=round(sum(c.cost_usd for c in calls), 6),
        )

    def _apply_guardrail(self, text: str) -> tuple[str, str, list[str]]:
        """ApplyGuardrail works on any text, including output from models outside Bedrock."""
        guardrail_id, version = self._guardrail
        response = self._bedrock.apply_guardrail(
            guardrailIdentifier=guardrail_id,
            guardrailVersion=version,
            source="OUTPUT",
            content=[{"text": {"text": text}}],
        )
        masked = sorted({
            entity["type"]
            for assessment in response.get("assessments", [])
            for entity in assessment.get("sensitiveInformationPolicy", {}).get("piiEntities", [])
        })
        if response["action"] == "GUARDRAIL_INTERVENED" and response.get("outputs"):
            return response["outputs"][0]["text"], response["action"], masked
        return text, response["action"], masked
