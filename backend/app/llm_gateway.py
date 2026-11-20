"""Capgemini AI Passport Gateway provider (OpenAI-compatible Responses API).

Used when LLM_PROVIDER=gateway. Claude models (e.g. `anthropic.claude-opus-5-5`) are reachable through
this endpoint even on plans where the gateway's Anthropic-format endpoint is not enabled.
Structured output uses `text.format = json_schema` (strict), and the reply is validated with Pydantic.
"""

import copy
import hashlib
import logging
import time
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.config import settings
from app.llm import LLMError

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

RETRY_STATUS = {408, 409, 429, 500, 502, 503, 504}


def strict_schema(model: type[BaseModel]) -> dict:
    """Pydantic JSON schema → strict json_schema: every object closed and every property required."""
    schema = copy.deepcopy(model.model_json_schema())

    def walk(node):
        if isinstance(node, dict):
            node.pop("title", None)
            node.pop("default", None)
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
                node["required"] = list(node["properties"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(schema)
    return schema


def system_text(system: list[dict] | str) -> str:
    if isinstance(system, str):
        return system
    return "\n\n".join(block["text"] for block in system if block.get("type") == "text")


def error_message(resp: httpx.Response) -> str:
    try:
        body = resp.json()
    except ValueError:
        return resp.text[:300]
    err = body.get("error")
    if isinstance(err, dict):  # OpenAI-style
        return err.get("message") or str(err)
    return body.get("message") or body.get("errorCode") or str(body)[:300]


def gateway_structured_call(
    *, system: list[dict] | str, user: str, output: type[T], effort: str = "medium", max_tokens: int = 16000
) -> tuple[T, str]:
    if not settings.gateway_api_key:
        raise LLMError("LLM_PROVIDER=gateway but GATEWAY_API_KEY is not set in .env")

    instructions = system_text(system)
    payload = {
        "model": settings.gateway_model,
        "instructions": instructions,
        "input": user,
        "max_output_tokens": max_tokens,
        "reasoning": {"effort": effort},
        "text": {"format": {"type": "json_schema", "name": output.__name__, "strict": True, "schema": strict_schema(output)}},
        # Same instructions (policy library) on every mapping call → lets the gateway reuse its prompt cache.
        "prompt_cache_key": "regmon-" + hashlib.sha256(instructions.encode()).hexdigest()[:16],
    }
    headers = {"Authorization": f"Bearer {settings.gateway_api_key}"}
    url = settings.gateway_base_url.rstrip("/") + "/responses"

    resp = None
    for attempt in range(4):
        try:
            resp = httpx.post(url, json=payload, headers=headers, timeout=settings.gateway_timeout_s)
        except httpx.TransportError as e:
            if attempt == 3:
                raise LLMError(f"Could not reach the AI gateway: {e}") from e
        else:
            if resp.status_code not in RETRY_STATUS:
                break
            if attempt == 3:
                break
        time.sleep(2 ** attempt * 2)

    if resp.status_code >= 400:
        raise LLMError(f"AI gateway error {resp.status_code}: {error_message(resp)}")

    body = resp.json()
    if body.get("error"):
        raise LLMError(f"AI gateway error: {error_message(resp)}")
    if body.get("status") != "completed":
        detail = (body.get("incomplete_details") or {}).get("reason")
        raise LLMError(f"Model response incomplete (status={body.get('status')}, reason={detail})")

    text = "".join(
        part.get("text", "")
        for item in body.get("output", [])
        if item.get("type") == "message"
        for part in item.get("content") or []
        if part.get("type") in ("output_text", "text")
    )
    refusals = [
        part.get("refusal")
        for item in body.get("output", [])
        if item.get("type") == "message"
        for part in item.get("content") or []
        if part.get("type") == "refusal"
    ]
    if refusals and not text:
        raise LLMError(f"Model declined this item: {refusals[0]}")
    try:
        parsed = output.model_validate_json(text)
    except ValidationError as e:
        raise LLMError(f"Model returned output that does not match the schema: {e.errors()[:2]}") from e

    usage = body.get("usage") or {}
    log.info(
        "gateway %s in=%s out=%s cached=%s",
        body.get("model"),
        usage.get("input_tokens"),
        usage.get("output_tokens"),
        (usage.get("input_tokens_details") or {}).get("cached_tokens"),
    )
    return parsed, body.get("model") or settings.gateway_model
