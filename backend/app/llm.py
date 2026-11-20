"""Thin wrapper around the Anthropic SDK: typed structured output + refusal fallbacks."""

import logging
from functools import lru_cache
from typing import TypeVar

import anthropic
from pydantic import BaseModel, ValidationError

from app.config import settings

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class LLMError(RuntimeError):
    """Raised when Claude can't produce a usable structured answer."""


@lru_cache
def get_client() -> anthropic.Anthropic:
    # Key from .env/env via settings; otherwise the SDK's default chain (e.g. an `ant auth login` profile).
    kwargs = {"api_key": settings.anthropic_api_key} if settings.anthropic_api_key else {}
    try:
        return anthropic.Anthropic(max_retries=4, **kwargs)
    except Exception as e:  # raised when no credential can be resolved
        raise LLMError("No Claude credentials found: set ANTHROPIC_API_KEY in .env") from e


def structured_call(
    *,
    system: list[dict] | str,
    user: str,
    output: type[T],
    effort: str = "medium",
    max_tokens: int = 16000,
) -> tuple[T, str]:
    """Run one LLM request and return (validated output, model that served it)."""
    if settings.llm_provider == "gateway":
        from app.llm_gateway import gateway_structured_call

        return gateway_structured_call(system=system, user=user, output=output, effort=effort, max_tokens=max_tokens)
    return _anthropic_structured_call(system=system, user=user, output=output, effort=effort, max_tokens=max_tokens)


def _anthropic_structured_call(*, system, user, output: type[T], effort: str, max_tokens: int) -> tuple[T, str]:
    try:
        response = get_client().beta.messages.parse(
            model=settings.anthropic_model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=output,
            output_config={"effort": effort},
            # If a safety classifier declines, the API retries on a fallback model in the same call.
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )
    except anthropic.RateLimitError as e:
        raise LLMError(f"Rate limited by Claude API: {e}") from e
    except anthropic.APIStatusError as e:
        raise LLMError(f"Claude API error {e.status_code}: {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise LLMError(f"Could not reach Claude API: {e}") from e
    except TypeError as e:
        # The SDK raises TypeError at request time when no auth method can be resolved.
        raise LLMError("No Claude credentials found: set ANTHROPIC_API_KEY in .env") from e
    except ValidationError as e:
        # parse() validates eagerly; a refused or truncated response has no valid JSON to validate.
        raise LLMError("Claude returned no valid structured output (likely a refusal or truncated response)") from e

    if response.stop_reason == "refusal":
        category = getattr(response.stop_details, "category", None) if response.stop_details else None
        raise LLMError(f"Claude declined this item (category: {category})")
    if response.stop_reason == "max_tokens":
        raise LLMError("Response hit max_tokens before completing")
    if response.parsed_output is None:
        raise LLMError(f"No structured output (stop_reason={response.stop_reason})")

    usage = response.usage
    log.info(
        "claude %s in=%s out=%s cache_read=%s",
        response.model,
        usage.input_tokens,
        usage.output_tokens,
        getattr(usage, "cache_read_input_tokens", None),
    )
    return response.parsed_output, response.model
