"""Deterministic validation of model output (Skill 1.1.3: basic content validator).

LLM output is untrusted until checked. This module checks:
- schema: required fields are present, have the right types and are well formed
- business rules: the policy exists, the dates fall in its coverage period, the amount is within
  the coverage limit and the claim type matches the policy type
- summary: there is a coverage verdict, the length is bounded and no unmasked PII remains
Errors mean the record cannot be trusted. Warnings mean a human should review it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from .rag import PolicyRecord

CLAIM_TYPES = ("auto", "home", "travel", "other")

CLAIM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "claimant_name": {"type": "string", "description": "Full name of the person making the claim"},
        "policy_number": {"type": "string", "description": "Policy number, e.g. POL-123456"},
        "incident_date": {"type": "string", "description": "Date the incident happened, YYYY-MM-DD"},
        "claim_amount": {"type": "number", "description": "Total amount claimed, number only"},
        "currency": {"type": "string", "description": "ISO 4217 currency code, e.g. USD"},
        "claim_type": {"type": "string", "enum": list(CLAIM_TYPES)},
        "incident_description": {"type": "string", "description": "One or two sentence factual description"},
    },
    "required": ["claimant_name", "policy_number", "incident_date", "claim_amount", "claim_type",
                 "incident_description"],
}

VERDICTS = ("LIKELY COVERED", "NEEDS REVIEW", "LIKELY NOT COVERED")

_POLICY_NUMBER = re.compile(r"^POL-\d{6}$")
_UNMASKED_PII = {
    "SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"),
    "card number": re.compile(r"\b(?:\d[ -]?){13,16}\b"),
}


@dataclass(frozen=True)
class ValidationIssue:
    field: str
    severity: str  # "error" or "warning"
    message: str


@dataclass
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def valid(self) -> bool:
        return not self.errors

    def error(self, field_name: str, message: str) -> None:
        self.issues.append(ValidationIssue(field_name, "error", message))

    def warn(self, field_name: str, message: str) -> None:
        self.issues.append(ValidationIssue(field_name, "warning", message))

    def as_notes(self) -> str:
        if not self.issues:
            return "- No issues found."
        return "\n".join(f"- [{i.severity.upper()}] {i.field}: {i.message}" for i in self.issues)


class ClaimValidator:
    def __init__(self, today: date | None = None, max_summary_words: int = 180) -> None:
        self._today = today or date.today()
        self._max_summary_words = max_summary_words

    def validate_extraction(self, fields: dict[str, Any] | None, policy: PolicyRecord | None) -> ValidationReport:
        report = ValidationReport()
        if not fields:
            report.error("extraction", "Model returned no structured output")
            return report

        for name in CLAIM_SCHEMA["required"]:
            value = fields.get(name)
            if value is None or (isinstance(value, str) and not value.strip()):
                report.error(name, "Missing")

        policy_number = str(fields.get("policy_number") or "").strip().upper()
        if policy_number and not _POLICY_NUMBER.match(policy_number):
            report.error("policy_number", f"Unexpected format: {policy_number!r}")

        incident_date = None
        raw_date = fields.get("incident_date")
        if raw_date:
            try:
                incident_date = date.fromisoformat(str(raw_date))
            except ValueError:
                report.error("incident_date", f"Not an ISO date: {raw_date!r}")
        if incident_date and incident_date > self._today:
            report.error("incident_date", f"{incident_date} is in the future")

        amount = fields.get("claim_amount")
        if amount is not None:
            if isinstance(amount, bool) or not isinstance(amount, (int, float)):
                report.error("claim_amount", f"Not a number: {amount!r}")
                amount = None
            elif amount <= 0:
                report.error("claim_amount", "Must be positive")

        claim_type = fields.get("claim_type")
        if claim_type and claim_type not in CLAIM_TYPES:
            report.error("claim_type", f"Unknown type {claim_type!r}")

        if policy_number and _POLICY_NUMBER.match(policy_number):
            if policy is None:
                report.error("policy_number", f"{policy_number} not found in the policy store")
            else:
                self._check_against_policy(report, policy, incident_date, amount, claim_type)
        return report

    def _check_against_policy(self, report: ValidationReport, policy: PolicyRecord,
                              incident_date: date | None, amount: float | None, claim_type: str | None) -> None:
        if incident_date and not policy.coverage_start <= incident_date <= policy.coverage_end:
            report.warn("incident_date", f"Outside coverage period {policy.coverage_start} to {policy.coverage_end}")
        if amount is not None and amount > policy.coverage_limit:
            report.warn("claim_amount", f"{amount:,.2f} exceeds coverage limit {policy.coverage_limit:,.2f}")
        if claim_type and claim_type != policy.policy_type:
            report.warn("claim_type", f"Claim type '{claim_type}' does not match '{policy.policy_type}' policy")

    def validate_summary(self, summary: str, extraction: ValidationReport | None = None) -> ValidationReport:
        report = ValidationReport()
        if not summary.strip():
            report.error("summary", "Empty")
            return report
        if not any(v in summary.upper() for v in VERDICTS):
            report.error("summary", f"No coverage verdict (expected one of {', '.join(VERDICTS)})")
        words = len(summary.split())
        if words > self._max_summary_words:
            report.warn("summary", f"{words} words exceeds the {self._max_summary_words}-word budget")
        if extraction and extraction.issues and detect_verdict(summary) == "LIKELY COVERED":
            report.warn("summary", "Verdict is LIKELY COVERED although rule checks raised issues")
        for label, pattern in _UNMASKED_PII.items():
            if pattern.search(summary):
                report.error("summary", f"Possible unmasked {label}")
        return report


def detect_verdict(summary: str) -> str | None:
    """Return the first verdict phrase in the summary (the prompt asks the model to lead with it)."""
    upper = summary.upper()
    positions = [(upper.find(v), v) for v in VERDICTS if v in upper]
    return min(positions)[1] if positions else None
