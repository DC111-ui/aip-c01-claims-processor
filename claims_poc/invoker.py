"""Model-agnostic Bedrock invoker built on the Converse API (Skill 1.1.3).

Why Converse rather than InvokeModel: InvokeModel request and response bodies differ per
model provider (Anthropic, Amazon Nova, Meta, ...), so switching models means rewriting
parsing code. Converse has one request/response shape, one tool-use format and returns token
usage and latency for every call. That is what makes the model comparison a one-line change.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import boto3
from botocore.config import Config


@dataclass(frozen=True)
class ModelSpec:
    alias: str
    model_id: str  # cross-Region inference profile ID
    input_usd_per_mtok: float
    output_usd_per_mtok: float


# On-demand prices in us-east-1 when this was written. Check the Bedrock pricing page before relying on them.
MODELS: dict[str, ModelSpec] = {
    spec.alias: spec
    for spec in (
        ModelSpec("haiku-4.5", "us.anthropic.claude-haiku-4-5-20251001-v1:0", 1.00, 5.00),
        ModelSpec("nova-lite", "us.amazon.nova-lite-v1:0", 0.06, 0.24),
        ModelSpec("nova-micro", "us.amazon.nova-micro-v1:0", 0.035, 0.14),
    )
}


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    json_schema: dict[str, Any]


@dataclass(frozen=True)
class InvocationResult:
    model: str
    text: str
    tool_input: dict[str, Any] | None
    input_tokens: int
    output_tokens: int
    latency_ms: int
    stop_reason: str

    @property
    def cost_usd(self) -> float:
        return estimate_cost(self.model, self.input_tokens, self.output_tokens)


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    spec = resolve_model(model)
    return (input_tokens * spec.input_usd_per_mtok + output_tokens * spec.output_usd_per_mtok) / 1_000_000


def resolve_model(model: str) -> ModelSpec:
    if model in MODELS:
        return MODELS[model]
    for spec in MODELS.values():
        if spec.model_id == model:
            return spec
    raise KeyError(f"Unknown model {model!r}. Known aliases: {sorted(MODELS)}")


class ModelInvoker:
    """Single entry point for every model call: bounded tokens, retries and usage metrics."""

    def __init__(self, client: Any | None = None, region: str | None = None) -> None:
        self._client = client or boto3.client(
            "bedrock-runtime",
            region_name=region,
            config=Config(retries={"mode": "adaptive", "max_attempts": 6}, read_timeout=120),
        )

    def invoke(
        self,
        model: str,
        *,
        user: str,
        system: str | None = None,
        max_tokens: int = 800,
        temperature: float = 0.0,
        tool: ToolSpec | None = None,
    ) -> InvocationResult:
        spec = resolve_model(model)
        request: dict[str, Any] = {
            "modelId": spec.model_id,
            "messages": [{"role": "user", "content": [{"text": user}]}],
            # Claude 4.5 models reject temperature and topP together, so only temperature is set.
            "inferenceConfig": {"maxTokens": max_tokens, "temperature": temperature},
        }
        if system:
            request["system"] = [{"text": system}]
        if tool:
            # Forcing a specific tool makes the model return arguments that follow our JSON
            # schema, which is more reliable than asking for "JSON format" in the prompt.
            request["toolConfig"] = {
                "tools": [{"toolSpec": {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": {"json": tool.json_schema},
                }}],
                "toolChoice": {"tool": {"name": tool.name}},
            }

        response = self._client.converse(**request)

        text_parts: list[str] = []
        tool_input: dict[str, Any] | None = None
        for block in response["output"]["message"]["content"]:
            if "text" in block:
                text_parts.append(block["text"])
            elif "toolUse" in block and tool and block["toolUse"]["name"] == tool.name:
                tool_input = block["toolUse"]["input"]

        usage = response["usage"]
        return InvocationResult(
            model=spec.alias,
            text="".join(text_parts).strip(),
            tool_input=tool_input,
            input_tokens=usage["inputTokens"],
            output_tokens=usage["outputTokens"],
            latency_ms=response["metrics"]["latencyMs"],
            stop_reason=response["stopReason"],
        )
