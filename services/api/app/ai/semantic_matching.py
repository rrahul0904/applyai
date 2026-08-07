from __future__ import annotations

import hashlib
import math
import os
import re
from collections import Counter
from typing import Iterable

import httpx

TOKEN_RE = re.compile(r"[a-z0-9+#.]{2,}")


def normalize_tokens(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def local_embedding(text: str, dimensions: int = 384) -> list[float]:
    vector = [0.0] * dimensions
    tokens = normalize_tokens(text)
    counts = Counter(tokens)
    for token, count in counts.items():
        digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[bucket] += sign * (1.0 + math.log(count))
    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector] if norm else vector


def cosine(left: Iterable[float], right: Iterable[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=False))


class EmbeddingProvider:
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class LocalEmbeddingProvider(EmbeddingProvider):
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [local_embedding(text) for text in texts]


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com").rstrip("/")
        self.model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAI embeddings")

    def embed(self, texts: list[str]) -> list[list[float]]:
        with httpx.Client(timeout=45.0) as client:
            response = client.post(
                f"{self.base_url}/v1/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "input": texts},
            )
        response.raise_for_status()
        rows = sorted(response.json()["data"], key=lambda row: row["index"])
        return [row["embedding"] for row in rows]


def get_embedding_provider() -> EmbeddingProvider:
    provider = os.getenv("EMBEDDING_PROVIDER", "local").strip().lower()
    if provider == "openai":
        return OpenAIEmbeddingProvider()
    if provider == "local":
        return LocalEmbeddingProvider()
    raise RuntimeError(f"Unsupported embedding provider: {provider}")


def rerank(query_text: str, documents: list[tuple[str, str]]) -> list[tuple[str, float]]:
    provider = get_embedding_provider()
    vectors = provider.embed([query_text, *[text for _, text in documents]])
    query_vector = vectors[0]
    scored = [(identifier, round(max(-1.0, min(1.0, cosine(query_vector, vector))) * 100, 2)) for (identifier, _), vector in zip(documents, vectors[1:], strict=True)]
    return sorted(scored, key=lambda row: row[1], reverse=True)
