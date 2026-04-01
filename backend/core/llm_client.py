"""Unified LLM client — switches between direct API and Copilot proxy.

Provides a single `acompletion` wrapper that routes requests based on the
configured LLM_PROVIDER setting:

  - "direct"       → Standard LiteLLM call (uses OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.)
  - "copilot_proxy" → Routes through a local OpenAI-compatible proxy (e.g. vscode-lm-proxy)

All call sites (agent loop, LLM parser) import from here instead of litellm directly.
"""

from __future__ import annotations

import os
from typing import Any

from loguru import logger


def _get_provider() -> str:
    return os.environ.get("LLM_PROVIDER", "direct").lower()


def _get_proxy_url() -> str:
    return os.environ.get("COPILOT_PROXY_URL", "http://localhost:4000/v1")


def _get_proxy_model() -> str | None:
    """Return the model override for copilot proxy, or None to use the caller's model."""
    return os.environ.get("COPILOT_PROXY_MODEL", "").strip() or None


async def acompletion(
    model: str,
    messages: list[dict[str, Any]],
    *,
    tools: list[dict] | None = None,
    max_tokens: int = 4096,
    temperature: float | None = None,
    **kwargs: Any,
) -> Any:
    """Drop-in replacement for litellm.acompletion with provider routing.

    Args:
        model: LiteLLM model identifier (e.g. 'gpt-4o'). May be overridden
               by COPILOT_PROXY_MODEL when using copilot_proxy provider.
        messages: Chat messages in OpenAI format.
        tools: OpenAI function-calling tool definitions.
        max_tokens: Max tokens for response.
        temperature: Sampling temperature (omitted if None).
        **kwargs: Passed through to litellm.acompletion.
    """
    from litellm import acompletion as _litellm_acompletion

    provider = _get_provider()

    call_kwargs: dict[str, Any] = {
        "messages": messages,
        "max_tokens": max_tokens,
        **kwargs,
    }

    if tools:
        call_kwargs["tools"] = tools
    if temperature is not None:
        call_kwargs["temperature"] = temperature

    if provider == "copilot_proxy":
        proxy_url = _get_proxy_url()
        proxy_model = _get_proxy_model() or model

        call_kwargs["model"] = f"openai/{proxy_model}"
        call_kwargs["api_base"] = proxy_url
        call_kwargs["api_key"] = "copilot-proxy"  # Proxy doesn't validate keys

        logger.debug(
            f"LLM call via copilot_proxy: model={proxy_model}, "
            f"api_base={proxy_url}"
        )
    else:
        # Direct provider — use LiteLLM's standard routing
        call_kwargs["model"] = model
        logger.debug(f"LLM call via direct API: model={model}")

    return await _litellm_acompletion(**call_kwargs)


def get_active_provider_info() -> dict[str, str]:
    """Return info about the currently active LLM provider (for health/debug endpoints)."""
    provider = _get_provider()
    if provider == "copilot_proxy":
        return {
            "provider": "copilot_proxy",
            "proxy_url": _get_proxy_url(),
            "proxy_model": _get_proxy_model() or "(uses caller model)",
        }
    return {
        "provider": "direct",
        "note": "Using LiteLLM standard routing with API keys from environment",
    }
