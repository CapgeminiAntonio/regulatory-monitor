"""Exercise the real SDK request path against a mock transport (no network, no API key needed)."""

import json

import anthropic
import httpx2
import pytest

from app import llm
from app.pipeline.analyze import ChangeAnalysis

ANALYSIS = {
    "title": "t", "summary": "s", "what_changed": [], "new_obligations": [], "who_is_affected": "w",
    "effective_date": None, "comment_deadline": None, "regulation": "FINRA", "severity": "low", "topics": [],
}


def make_client(handler):
    return anthropic.Anthropic(
        api_key="test", max_retries=0, http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(handler))
    )


def message(stop_reason="end_turn", text=json.dumps(ANALYSIS), **extra):
    return {
        "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
        "content": [{"type": "text", "text": text}], "stop_reason": stop_reason, "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 5}, **extra,
    }


def test_request_shape_and_parsing(monkeypatch):
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        seen["beta"] = request.headers.get("anthropic-beta", "")
        return httpx2.Response(200, json=message())

    monkeypatch.setattr(llm, "get_client", lambda: make_client(handler))
    out, model = llm.structured_call(
        system=[{"type": "text", "text": "lib", "cache_control": {"type": "ephemeral"}}],
        user="hi", output=ChangeAnalysis, effort="high",
    )
    assert isinstance(out, ChangeAnalysis) and out.regulation == "FINRA" and model == "claude-opus-5-5"
    body = seen["body"]
    assert body["model"] == "claude-opus-5-5"
    assert body["fallbacks"] == "default" and "server-side-fallback-2026-07-01" in seen["beta"]
    assert body["output_config"]["effort"] == "high"
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert body["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "thinking" not in body  # always-on for Opus 5.5; must not send disabled/budget


def test_refusal_raises(monkeypatch):
    def handler(request):
        return httpx2.Response(200, json=message(
            stop_reason="refusal", text="", stop_details={"type": "refusal", "category": "cyber", "explanation": None}
        ))

    monkeypatch.setattr(llm, "get_client", lambda: make_client(handler))
    with pytest.raises(llm.LLMError, match="declined|no valid structured output"):
        llm.structured_call(system="s", user="u", output=ChangeAnalysis)


def test_api_error_raises(monkeypatch):
    def handler(request):
        return httpx2.Response(500, json={"type": "error", "error": {"type": "api_error", "message": "boom"}})

    monkeypatch.setattr(llm, "get_client", lambda: make_client(handler))
    with pytest.raises(llm.LLMError, match="500"):
        llm.structured_call(system="s", user="u", output=ChangeAnalysis)
