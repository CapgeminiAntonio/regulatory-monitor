"""Gateway provider against a mocked HTTP endpoint (no network)."""

import json

import httpx
import pytest
import respx

from app import llm
from app.config import settings
from app.llm import LLMError
from app.llm_gateway import strict_schema
from app.pipeline.map_policies import PolicyMapping

URL = settings.gateway_base_url.rstrip("/") + "/responses"
MAPPING = {"impacts": [{"policy_id": "ai-governance", "impact": "high", "affected_sections": ["3.1"],
                        "rationale": "r", "recommended_action": "a", "confidence": 0.8}]}


def ok_response(text: str) -> dict:
    return {"status": "completed", "model": "anthropic.claude-opus-5-5",
            "output": [{"type": "reasoning", "content": []},
                       {"type": "message", "content": [{"type": "output_text", "text": text}]}],
            "usage": {"input_tokens": 10, "output_tokens": 5}}


@pytest.fixture(autouse=True)
def use_gateway(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "gateway")


def test_strict_schema_closes_nested_objects():
    s = strict_schema(PolicyMapping)
    inner = s["$defs"]["PolicyImpact"]
    assert s["additionalProperties"] is False and inner["additionalProperties"] is False
    assert set(inner["required"]) == set(inner["properties"])


@respx.mock
def test_gateway_request_and_parse():
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=ok_response(json.dumps(MAPPING))))
    out, model = llm.structured_call(
        system=[{"type": "text", "text": "A"}, {"type": "text", "text": "B", "cache_control": {"type": "ephemeral"}}],
        user="change", output=PolicyMapping, effort="high",
    )
    assert out.impacts[0].impact == "high" and model == "anthropic.claude-opus-5-5"
    req = route.calls.last.request
    body = json.loads(req.content)
    assert req.headers["authorization"] == "Bearer test-key"
    assert body["instructions"] == "A\n\nB" and body["input"] == "change"
    assert body["reasoning"] == {"effort": "high"}
    assert body["text"]["format"]["type"] == "json_schema" and body["text"]["format"]["strict"] is True
    assert body["prompt_cache_key"].startswith("regmon-")


@respx.mock
def test_gateway_plan_error_is_reported():
    respx.post(URL).mock(return_value=httpx.Response(
        403, json={"error": True, "errorCode": "ANTHROPIC_ACCESS_DENIED", "message": "not on your plan"}))
    with pytest.raises(LLMError, match="403: not on your plan"):
        llm.structured_call(system="s", user="u", output=PolicyMapping)


@respx.mock
def test_gateway_bad_json_and_incomplete():
    respx.post(URL).mock(return_value=httpx.Response(200, json=ok_response("not json")))
    with pytest.raises(LLMError, match="does not match the schema"):
        llm.structured_call(system="s", user="u", output=PolicyMapping)
    respx.post(URL).mock(return_value=httpx.Response(
        200, json={"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"}, "output": []}))
    with pytest.raises(LLMError, match="max_output_tokens"):
        llm.structured_call(system="s", user="u", output=PolicyMapping)
