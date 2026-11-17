"""Model comparison (Step 4): run every sample claim through every model and score the results.

Metrics per model:
- field accuracy: extracted fields compared with hand-labelled ground truth
- verdict agreement: the summary's coverage verdict compared with the expected verdict
- validation flags: whether the rule checks caught the issues planted in the sample claims
- latency, tokens and cost, all reported by the Converse API itself
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any

SCORED_FIELDS = ("claimant_name", "policy_number", "incident_date", "claim_amount", "claim_type")


def field_matches(name: str, expected: Any, actual: Any) -> bool:
    if actual is None:
        return False
    if name == "claim_amount":
        try:
            return abs(float(actual) - float(expected)) < 0.01
        except (TypeError, ValueError):
            return False
    return str(actual).strip().casefold() == str(expected).strip().casefold()


def score_result(result: dict[str, Any], truth: dict[str, Any]) -> dict[str, Any]:
    fields = result.get("fields") or {}
    matches = {f: field_matches(f, truth["fields"][f], fields.get(f)) for f in SCORED_FIELDS}
    flagged = {i["field"] for i in result["extraction_issues"]}
    expected_flags = set(truth.get("expected_flags", []))
    return {
        "field_accuracy": sum(matches.values()) / len(matches),
        "field_misses": [f for f, ok in matches.items() if not ok],
        "verdict_ok": result.get("verdict") == truth["expected_verdict"],
        "flags_ok": expected_flags <= flagged,
    }


def summarise(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_model: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_model.setdefault(row["model"], []).append(row)
    table = []
    for model, items in by_model.items():
        n = len(items)
        cost_per_claim = statistics.mean(r["cost_usd"] for r in items)
        table.append({
            "model": model,
            "claims": n,
            "field_accuracy": statistics.mean(r["score"]["field_accuracy"] for r in items),
            "verdict_agreement": sum(r["score"]["verdict_ok"] for r in items) / n,
            "flags_caught": sum(r["score"]["flags_ok"] for r in items) / n,
            "summary_checks_passed": sum(not any(i["severity"] == "error" for i in r["summary_issues"])
                                         for r in items) / n,
            "mean_latency_ms": round(statistics.mean(r["latency_ms"] for r in items)),
            "mean_tokens": round(statistics.mean(r["input_tokens"] + r["output_tokens"] for r in items)),
            "cost_per_claim_usd": cost_per_claim,
            "cost_per_10k_claims_usd": cost_per_claim * 10_000,
        })
    return sorted(table, key=lambda t: (-t["field_accuracy"], -t["verdict_agreement"], t["cost_per_claim_usd"]))


def write_report(rows: list[dict[str, Any]], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    table = summarise(rows)
    (out_dir / "comparison.json").write_text(json.dumps({"summary": table, "runs": rows}, indent=2), encoding="utf-8")

    lines = [
        "# Model comparison",
        "",
        "| Model | Field accuracy | Verdict agreement | Rule flags caught | Summary checks | "
        "Mean latency | Mean tokens | Cost / claim | Cost / 10k claims |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for t in table:
        lines.append(
            f"| {t['model']} | {t['field_accuracy']:.0%} | {t['verdict_agreement']:.0%} | {t['flags_caught']:.0%} | "
            f"{t['summary_checks_passed']:.0%} | {t['mean_latency_ms']:,} ms | {t['mean_tokens']:,} | "
            f"${t['cost_per_claim_usd']:.5f} | ${t['cost_per_10k_claims_usd']:.2f} |"
        )
    lines += ["", "## Per-claim results", ""]
    for r in rows:
        s = r["score"]
        misses = ", ".join(s["field_misses"]) or "none"
        lines.append(f"### {r['model']} - `{r['document_key']}`")
        lines.append("")
        lines.append(f"- Field misses: {misses}; verdict: {r['verdict']} "
                     f"({'matches' if s['verdict_ok'] else 'differs from'} expected); "
                     f"guardrail: {r['guardrail_action']} {r['pii_masked'] or ''}")
        issues = r["extraction_issues"] + r["summary_issues"]
        if issues:
            lines.append("- Validation: " + "; ".join(f"[{i['severity']}] {i['field']}: {i['message']}" for i in issues))
        lines += ["", "> " + r["summary"].replace("\n", "\n> "), ""]
    path = out_dir / "comparison.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
