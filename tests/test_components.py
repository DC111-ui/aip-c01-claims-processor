"""Offline unit tests for the reusable components (no AWS calls)."""

import io
import json
import unittest
from datetime import date
from pathlib import Path

from claims_poc.evaluate import field_matches, score_result
from claims_poc.invoker import InvocationResult, ModelInvoker, ToolSpec, estimate_cost
from claims_poc.prompts import PromptTemplate, PromptTemplateManager
from claims_poc.rag import PolicyRecord, parse_policy
from claims_poc.validator import ClaimValidator, detect_verdict

DATA = Path(__file__).resolve().parent.parent / "data"

POLICY = PolicyRecord("POL-300552", "travel", "Priya Raman", date(2026, 6, 1), date(2026, 9, 30), 5000.0, 100.0)
GOOD = {
    "claimant_name": "Priya Raman", "policy_number": "POL-300552", "incident_date": "2026-07-22",
    "claim_amount": 900.0, "claim_type": "travel", "incident_description": "Suitcase stolen.",
}


class PromptTests(unittest.TestCase):
    def test_render_keeps_braces_in_documents(self):
        rendered = PromptTemplateManager().render("extract_claim", document_text='{"json": true}')
        self.assertIn('{"json": true}', rendered.user)
        self.assertEqual(rendered.version, "1.1")

    def test_missing_and_extra_variables_rejected(self):
        manager = PromptTemplateManager()
        with self.assertRaises(ValueError):
            manager.render("extract_claim")
        with self.assertRaises(ValueError):
            manager.render("extract_claim", document_text="x", other="y")

    def test_unknown_template(self):
        with self.assertRaises(KeyError):
            PromptTemplateManager().get("nope")

    def test_variables_detected(self):
        t = PromptTemplate(name="t", version="1", system="Hi $who", user="${a} and $b")
        self.assertEqual(t.variables, {"who", "a", "b"})


class FakeBedrock:
    def __init__(self, response):
        self.response, self.request = response, None

    def converse(self, **request):
        self.request = request
        return self.response


class InvokerTests(unittest.TestCase):
    def test_forced_tool_call_is_parsed(self):
        fake = FakeBedrock({
            "output": {"message": {"content": [{"toolUse": {"name": "record_claim", "input": {"a": 1}}}]}},
            "usage": {"inputTokens": 1000, "outputTokens": 200},
            "metrics": {"latencyMs": 450},
            "stopReason": "tool_use",
        })
        tool = ToolSpec("record_claim", "d", {"type": "object"})
        result = ModelInvoker(client=fake).invoke("nova-micro", user="u", system="s", tool=tool, max_tokens=50)
        self.assertEqual(result.tool_input, {"a": 1})
        self.assertEqual(fake.request["toolConfig"]["toolChoice"], {"tool": {"name": "record_claim"}})
        self.assertEqual(fake.request["inferenceConfig"]["maxTokens"], 50)
        self.assertNotIn("topP", fake.request["inferenceConfig"])
        self.assertAlmostEqual(result.cost_usd, (1000 * 0.035 + 200 * 0.14) / 1e6)

    def test_cost_by_model_id(self):
        self.assertAlmostEqual(estimate_cost("us.anthropic.claude-haiku-4-5-20251001-v1:0", 1_000_000, 0), 1.0)

    def test_unknown_model(self):
        with self.assertRaises(KeyError):
            ModelInvoker(client=object()).invoke("gpt", user="x")


class PolicyParsingTests(unittest.TestCase):
    def test_sample_policies_parse(self):
        for path in (DATA / "policies").glob("*.md"):
            record, sections = parse_policy(path.read_text(encoding="utf-8"))
            self.assertEqual(path.stem, record.policy_number)
            self.assertGreaterEqual(len(sections), 3)
            self.assertIn("Exclusions", [h for h, _ in sections])

    def test_missing_header_rejected(self):
        with self.assertRaises(ValueError):
            parse_policy("# Not a policy\n## Section\ntext")


class ValidatorTests(unittest.TestCase):
    def setUp(self):
        self.v = ClaimValidator(today=date(2026, 11, 17))

    def test_clean_claim(self):
        self.assertEqual(self.v.validate_extraction(dict(GOOD), POLICY).issues, [])

    def test_business_rules_warn(self):
        claim = dict(GOOD, claim_amount=6800.0, incident_date="2026-10-15", claim_type="home")
        report = self.v.validate_extraction(claim, POLICY)
        self.assertTrue(report.valid)
        self.assertEqual({i.field for i in report.warnings}, {"claim_amount", "incident_date", "claim_type"})

    def test_schema_errors(self):
        claim = dict(GOOD, claim_amount="lots", incident_date="22/07/2026", policy_number="12345")
        report = self.v.validate_extraction(claim, None)
        self.assertFalse(report.valid)
        self.assertEqual({i.field for i in report.errors}, {"claim_amount", "incident_date", "policy_number"})

    def test_future_date_and_unknown_policy(self):
        report = self.v.validate_extraction(dict(GOOD, incident_date="2027-01-01"), None)
        self.assertEqual({i.field for i in report.errors}, {"incident_date", "policy_number"})

    def test_no_output(self):
        self.assertFalse(self.v.validate_extraction(None, None).valid)

    def test_summary_checks(self):
        self.assertTrue(self.v.validate_summary("NEEDS REVIEW: amount exceeds limit.").valid)
        self.assertFalse(self.v.validate_summary("Looks fine.").valid)
        self.assertFalse(self.v.validate_summary("NEEDS REVIEW. SSN 123-45-6789").valid)
        self.assertFalse(self.v.validate_summary("NEEDS REVIEW. card 4111 1111 1111 1111").valid)

    def test_covered_verdict_inconsistent_with_rule_flags(self):
        flagged = self.v.validate_extraction(dict(GOOD, claim_amount=6800.0), POLICY)
        report = self.v.validate_summary("LIKELY COVERED under Baggage.", flagged)
        self.assertEqual([i.field for i in report.warnings], ["summary"])
        self.assertEqual(self.v.validate_summary("NEEDS REVIEW: over limit.", flagged).issues, [])

    def test_detect_verdict(self):
        self.assertEqual(detect_verdict("Assessment: LIKELY NOT COVERED because..."), "LIKELY NOT COVERED")
        self.assertEqual(detect_verdict("**Likely covered** - see Covered Perils"), "LIKELY COVERED")
        self.assertIsNone(detect_verdict("unclear"))


class EvaluateTests(unittest.TestCase):
    def test_scoring(self):
        truth = json.loads((DATA / "ground_truth.json").read_text(encoding="utf-8"))["claims/claim-003-travel.txt"]
        result = {
            "fields": dict(GOOD, claim_amount="6800", claimant_name="priya raman"),
            "extraction_issues": [{"field": "claim_amount", "severity": "warning", "message": ""}],
            "verdict": "NEEDS REVIEW",
        }
        score = score_result(result, truth)
        self.assertEqual(score["field_accuracy"], 1.0)
        self.assertTrue(score["verdict_ok"] and score["flags_ok"])
        self.assertFalse(field_matches("claim_amount", 1, "n/a"))


if __name__ == "__main__":
    unittest.main()
