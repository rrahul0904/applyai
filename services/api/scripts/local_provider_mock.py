from __future__ import annotations

import base64
import hashlib
import math
import time
import uuid
from typing import Any

import jwt
import uvicorn
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, Header, HTTPException, Query
from pydantic import BaseModel


HOST = "127.0.0.1"
PORT = 8099
ISSUER = f"http://{HOST}:{PORT}/clerk"
OPENAI_KEY = "local-openai-protocol-key"
KID = "applyai-local-clerk"

_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_public_numbers = _private_key.public_key().public_numbers()


def _b64uint(value: int) -> str:
    width = max(1, (value.bit_length() + 7) // 8)
    return base64.urlsafe_b64encode(value.to_bytes(width, "big")).decode().rstrip("=")


app = FastAPI(title="ApplyAI local provider protocol mock")


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/clerk/.well-known/jwks.json")
def jwks() -> dict[str, Any]:
    return {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "kid": KID,
                "n": _b64uint(_public_numbers.n),
                "e": _b64uint(_public_numbers.e),
            }
        ]
    }


@app.get("/clerk/token")
def clerk_token(
    email: str = Query(default="local.clerk@example.test"),
    subject: str = Query(default="local_clerk_user"),
) -> dict[str, str]:
    now = int(time.time())
    token = jwt.encode(
        {
            "iss": ISSUER,
            "sub": subject,
            "email": email,
            "iat": now,
            "nbf": now - 1,
            "exp": now + 300,
        },
        _private_key,
        algorithm="RS256",
        headers={"kid": KID},
    )
    return {"token": token, "issuer": ISSUER, "jwks_url": f"{ISSUER}/.well-known/jwks.json"}


def _require_openai_auth(authorization: str | None) -> None:
    if authorization != f"Bearer {OPENAI_KEY}":
        raise HTTPException(status_code=401, detail="Invalid local OpenAI protocol key")


def _example_for_schema(schema: dict[str, Any]) -> Any:
    if "const" in schema:
        return schema["const"]
    if "enum" in schema and schema["enum"]:
        return schema["enum"][0]
    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        schema_type = next((item for item in schema_type if item != "null"), "null")
    if schema_type == "object" or "properties" in schema:
        properties = schema.get("properties") or {}
        required = set(schema.get("required") or properties.keys())
        return {
            name: _example_for_schema(child)
            for name, child in properties.items()
            if name in required
        }
    if schema_type == "array":
        min_items = int(schema.get("minItems") or 0)
        return [_example_for_schema(schema.get("items") or {}) for _ in range(min_items)]
    if schema_type == "integer":
        return int(schema.get("minimum") or 1)
    if schema_type == "number":
        return float(schema.get("minimum") or 1.0)
    if schema_type == "boolean":
        return True
    if schema_type == "null":
        return None
    return "local-protocol-value"


class ResponseRequest(BaseModel):
    model: str
    instructions: str | None = None
    input: str
    reasoning: dict[str, Any] | None = None
    text: dict[str, Any]
    store: bool = False
    safety_identifier: str | None = None


@app.post("/v1/responses")
def responses(
    payload: ResponseRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_openai_auth(authorization)
    schema = (((payload.text or {}).get("format") or {}).get("schema") or {})
    output = _example_for_schema(schema)
    import json

    return {
        "id": f"resp_local_{uuid.uuid4().hex}",
        "model": payload.model,
        "output_text": json.dumps(output),
        "usage": {"input_tokens": 11, "output_tokens": 7},
    }


class EmbeddingRequest(BaseModel):
    model: str
    input: list[str] | str


def _vector(text: str, dimensions: int = 8) -> list[float]:
    digest = hashlib.sha256(text.encode()).digest()
    values = [((digest[index] / 255.0) * 2.0) - 1.0 for index in range(dimensions)]
    norm = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / norm for value in values]


@app.post("/v1/embeddings")
def embeddings(
    payload: EmbeddingRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_openai_auth(authorization)
    texts = payload.input if isinstance(payload.input, list) else [payload.input]
    return {
        "object": "list",
        "model": payload.model,
        "data": [
            {"object": "embedding", "index": index, "embedding": _vector(text)}
            for index, text in enumerate(texts)
        ],
        "usage": {"prompt_tokens": len(texts), "total_tokens": len(texts)},
    }


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
