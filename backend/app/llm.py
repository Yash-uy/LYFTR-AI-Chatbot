
"""LiteLLM gateway: local cache plus ordered API-key fallback."""

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Any

from .config import settings

logger = logging.getLogger(__name__)

try:
    import litellm
    from litellm.caching import Cache

    litellm.cache = Cache(type="local")

except Exception:
    litellm = None
    logger.exception("LiteLLM initialization failed")


@dataclass
class GatewayResult:
    reply: str
    metadata: dict[str, Any]


def _usage_value(usage, key: str) -> int:
    if usage is None:
        return 0

    value = getattr(usage, key, None)

    if value is None and isinstance(usage, dict):
        value = usage.get(key)

    return int(value or 0)


def _parse_simulation(
    header: str | None,
    key_count: int
) -> dict[str, int]:

    parsed: dict[str, int] = {}

    if not header:
        return parsed

    for part in header.split(","):
        if "=" not in part:
            continue

        key_id, raw_status = part.strip().split("=", 1)

        try:
            status = int(raw_status)
        except ValueError:
            continue

        if status not in {429, 500, 502, 503}:
            continue

        if key_id == "*":
            parsed.update({
                f"key_{i + 1}": status
                for i in range(key_count)
            })

        elif key_id.startswith("key_"):
            parsed[key_id] = status

    return parsed


def _cache_identity(
    messages: list[dict],
    model: str
) -> str:

    raw = json.dumps(
        {
            "model": model,
            "messages": messages
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":")
    )

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()


def generate(
    messages: list[dict],
    failure_header: str | None = None
) -> GatewayResult:

    if litellm is None:
        raise RuntimeError(
            "LiteLLM is not installed or could not be initialized"
        )

    keys = settings.keys

    if len(keys) < 2:
        raise RuntimeError(
            "At least two LLM_API_KEYS must be configured"
        )

    simulation = (
        _parse_simulation(failure_header, len(keys))
        if settings.enable_failure_simulation
        else {}
    )

    started = time.perf_counter()
    attempts = 0
    last_error = None

    models = [
        settings.llm_model,
        "gemini/gemini-2.5-flash-lite",
        "gemini/gemini-flash-lite-latest",
        "gemini/gemini-flash-latest",
    ]

    models = list(dict.fromkeys(models))

    for model in models:

        cache_key = _cache_identity(messages, model)

        for index, api_key in enumerate(keys):

            key_id = f"key_{index + 1}"

            # Simulated provider failure
            if key_id in simulation:

                status = simulation[key_id]
                attempts += 1

                last_error = RuntimeError(
                    f"Simulated provider HTTP {status}"
                )

                logger.warning(
                    "Simulated provider failure: "
                    "model=%s key_id=%s status=%s",
                    model,
                    key_id,
                    status
                )

                continue

            try:

                logger.info(
                    "Trying LLM provider: model=%s key_id=%s",
                    model,
                    key_id
                )

                response = litellm.completion(
                    model=model,
                    messages=messages,
                    api_key=api_key,
                    caching=True,
                    cache_key=cache_key,
                    temperature=0.2,
                    num_retries=0,
                )

                elapsed = max(
                    0,
                    int((time.perf_counter() - started) * 1000)
                )

                hidden = (
                    getattr(response, "_hidden_params", {}) or {}
                )

                cache_hit = bool(
                    hidden.get("cache_hit")
                    or hidden.get("cached")
                )

                usage = getattr(response, "usage", None)

                choices = getattr(response, "choices", []) or []

                reply = (
                    choices[0].message.content
                    if choices
                    else None
                )

                if not isinstance(reply, str) or not reply.strip():
                    raise RuntimeError(
                        "Provider returned an empty response"
                    )

                metadata = {
                    "resolution_source": (
                        "LLM_CACHE"
                        if cache_hit
                        else "LIVE_INFERENCE"
                    ),
                    "model": (
                        getattr(response, "model", None) or model
                    ),
                    "latency_ms": elapsed,
                    "input_tokens": _usage_value(
                        usage, "prompt_tokens"
                    ),
                    "output_tokens": _usage_value(
                        usage, "completion_tokens"
                    ),
                    "key_id": (
                        None if cache_hit else key_id
                    ),
                    "fallback_attempts": (
                        0 if cache_hit else attempts
                    ),
                }

                logger.info(
                    "LLM provider succeeded: "
                    "model=%s key_id=%s cache_hit=%s "
                    "fallback_attempts=%s",
                    model,
                    key_id,
                    cache_hit,
                    attempts
                )

                return GatewayResult(
                    reply=reply.strip(),
                    metadata=metadata
                )

            except Exception as exc:

                last_error = exc
                attempts += 1

                status = getattr(exc, "status_code", None)

                logger.warning(
                    "LLM provider failed: "
                    "model=%s key_id=%s status=%s error_type=%s",
                    model,
                    key_id,
                    status,
                    type(exc).__name__
                )

                # Continue to the next key/model.

    logger.error(
        "All LLM providers failed: "
        "attempts=%s last_error_type=%s last_status=%s",
        attempts,
        type(last_error).__name__ if last_error else None,
        getattr(last_error, "status_code", None)
        if last_error else None
    )

    raise RuntimeError(
        "all providers unavailable"
    ) from last_error
