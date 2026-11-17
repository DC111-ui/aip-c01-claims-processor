"""Simple retrieval-augmented generation (RAG) over policy documents stored in S3.

Each policy is a Markdown file with a small header of structured facts (number, type,
coverage period, limit, deductible) and a set of "## " sections such as exclusions.
- The header is parsed into a PolicyRecord, used for deterministic checks.
- The sections are the chunks. They are embedded with Titan Text Embeddings V2 and
  searched by cosine similarity, filtered to the claimant's own policy number.

Splitting on headings (a semantic or hierarchical strategy) keeps every exclusion clause
together. Fixed-size chunks could cut a clause in half. Filtering on policy number does
the same job as metadata filtering in Bedrock Knowledge Bases, which is what you would
use in production instead of this in-memory index.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from typing import Any

EMBED_MODEL_ID = "amazon.titan-embed-text-v2:0"
EMBED_DIMENSIONS = 512


@dataclass(frozen=True)
class PolicyRecord:
    policy_number: str
    policy_type: str
    holder: str
    coverage_start: date
    coverage_end: date
    coverage_limit: float
    deductible: float


@dataclass(frozen=True)
class Chunk:
    policy_number: str
    heading: str
    text: str
    embedding: tuple[float, ...]


@dataclass(frozen=True)
class RetrievedChunk:
    policy_number: str
    heading: str
    text: str
    score: float


_HEADER_FIELDS = {
    "policy_number": r"Policy Number:\s*(\S+)",
    "policy_type": r"Policy Type:\s*(\w+)",
    "holder": r"Policyholder:\s*(.+)",
    "period": r"Coverage Period:\s*(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})",
    "limit": r"Coverage Limit:\s*\$?([\d,]+(?:\.\d+)?)",
    "deductible": r"Deductible:\s*\$?([\d,]+(?:\.\d+)?)",
}


def parse_policy(markdown: str) -> tuple[PolicyRecord, list[tuple[str, str]]]:
    """Return the structured header and the (heading, body) sections of a policy document."""
    found: dict[str, re.Match[str]] = {}
    for key, pattern in _HEADER_FIELDS.items():
        match = re.search(pattern, markdown)
        if not match:
            raise ValueError(f"Policy document is missing '{key}'")
        found[key] = match

    def money(key: str) -> float:
        return float(found[key].group(1).replace(",", ""))

    record = PolicyRecord(
        policy_number=found["policy_number"].group(1),
        policy_type=found["policy_type"].group(1).lower(),
        holder=found["holder"].group(1).strip(),
        coverage_start=date.fromisoformat(found["period"].group(1)),
        coverage_end=date.fromisoformat(found["period"].group(2)),
        coverage_limit=money("limit"),
        deductible=money("deductible"),
    )

    sections = []
    for block in re.split(r"^## ", markdown, flags=re.MULTILINE)[1:]:
        heading, _, body = block.partition("\n")
        if body.strip():
            sections.append((heading.strip(), body.strip()))
    return record, sections


class PolicyRetriever:
    def __init__(self, s3: Any, bedrock_runtime: Any, bucket: str, prefix: str = "policies/") -> None:
        self._s3 = s3
        self._bedrock = bedrock_runtime
        self._bucket = bucket
        self._prefix = prefix
        self._policies: dict[str, PolicyRecord] = {}
        self._chunks: list[Chunk] = []
        self.embedding_tokens = 0

    def load(self) -> None:
        """Read every policy in the bucket prefix and embed its sections (run once per session)."""
        self._policies.clear()
        self._chunks.clear()
        paginator = self._s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._bucket, Prefix=self._prefix):
            for obj in page.get("Contents", []):
                if not obj["Key"].endswith(".md"):
                    continue
                body = self._s3.get_object(Bucket=self._bucket, Key=obj["Key"])["Body"].read().decode("utf-8")
                record, sections = parse_policy(body)
                self._policies[record.policy_number] = record
                for heading, text in sections:
                    embedding = self._embed(f"{heading}\n{text}")
                    self._chunks.append(Chunk(record.policy_number, heading, text, embedding))
        if not self._policies:
            raise RuntimeError(f"No policy documents found in s3://{self._bucket}/{self._prefix}")

    def get_policy(self, policy_number: str | None) -> PolicyRecord | None:
        if not policy_number:
            return None
        return self._policies.get(policy_number.strip().upper())

    def retrieve(self, query: str, policy_number: str | None = None, k: int = 3) -> list[RetrievedChunk]:
        candidates = self._chunks
        if policy_number:
            candidates = [c for c in candidates if c.policy_number == policy_number.strip().upper()]
        if not candidates:
            return []
        q = self._embed(query)
        scored = [(sum(a * b for a, b in zip(q, c.embedding)), c) for c in candidates]  # vectors are unit length
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [RetrievedChunk(c.policy_number, c.heading, c.text, round(score, 4)) for score, c in scored[:k]]

    def retrieve_multi(self, queries: list[str], policy_number: str | None = None,
                       k_per_query: int = 2, k: int = 4) -> list[RetrievedChunk]:
        """Multi-query retrieval: union of each query's top hits, keeping the best score per section."""
        best: dict[tuple[str, str], RetrievedChunk] = {}
        for query in queries:
            for hit in self.retrieve(query, policy_number, k_per_query):
                key = (hit.policy_number, hit.heading)
                if key not in best or hit.score > best[key].score:
                    best[key] = hit
        return sorted(best.values(), key=lambda h: h.score, reverse=True)[:k]

    def _embed(self, text: str) -> tuple[float, ...]:
        response = self._bedrock.invoke_model(
            modelId=EMBED_MODEL_ID,
            body=json.dumps({"inputText": text, "dimensions": EMBED_DIMENSIONS, "normalize": True}),
        )
        payload = json.loads(response["body"].read())
        self.embedding_tokens += payload.get("inputTextTokenCount", 0)
        return tuple(payload["embedding"])
