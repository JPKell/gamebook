"""
Inference service.

HTTP client for sending prompts to the external AI inference endpoint.
This module does NOT serve or run models — it only constructs requests,
sends them to the configured endpoint (e.g. LoadCoach), and returns
responses.

Used in Phase 6+ for the inference bridge (health checks) and Phase 7+
for story generation and AI playthroughs. The prompt construction is
handled by individual route handlers or future services; this module
provides the transport layer.

Configuration comes from app.config.settings.inference.
"""

import logging
import time
from typing import Optional

import httpx
from app.config import settings

logger = logging.getLogger(__name__)


async def send_completion(
    prompt: str,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> str:
    """
    Send a chat completion request to the inference endpoint.

    Retries on transient failures (connection errors, timeouts, 5xx)
    with exponential backoff. Uses the configured max_retries from
    settings.

    Args:
        prompt: The text prompt to send to the model.
        model: Model name to use. Defaults to settings.inference.default_model.
        temperature: Sampling temperature. Defaults to 0.7.
        max_tokens: Maximum tokens in the response. Defaults to 2000.

    Returns:
        The model's response text.

    Raises:
        httpx.HTTPError: If the request fails after all retries.
        RuntimeError: If the response does not contain a valid choices array.
    """
    model = model or settings.inference.default_model
    temp = temperature if temperature is not None else 0.7
    max_tok = max_tokens if max_tokens is not None else 2000
    max_retries = settings.inference.max_retries

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.inference.api_key}"
        if settings.inference.api_key
        else "",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temp,
        "max_tokens": max_tok,
    }

    last_exc: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        try:
            async with httpx.AsyncClient(
                timeout=settings.inference.timeout
            ) as client:
                logger.info(
                    "Inference request attempt %d/%d: model=%s",
                    attempt + 1,
                    max_retries + 1,
                    model,
                )
                response = await client.post(
                    settings.inference.endpoint,
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

                choices = data.get("choices")
                if not choices or not isinstance(choices, list) or len(choices) == 0:
                    raise RuntimeError(
                        f"Inference response has no choices: {data}"
                    )

                content = choices[0].get("message", {}).get("content", "")
                logger.info(
                    "Inference response received: %d chars", len(content)
                )
                return content

        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            last_exc = exc
            if attempt < max_retries:
                backoff = 2 ** attempt
                logger.warning(
                    "Retry %d after %s (backoff %ds): %s",
                    attempt + 1,
                    type(exc).__name__,
                    backoff,
                    exc,
                )
                time.sleep(backoff)
            else:
                logger.error("All %d retries exhausted: %s", max_retries + 1, exc)

        except httpx.HTTPStatusError as exc:
            # 5xx errors are retried; 4xx are not
            if exc.response.status_code >= 500 and attempt < max_retries:
                backoff = 2 ** attempt
                logger.warning(
                    "Retry %d after HTTP %d (backoff %ds)",
                    attempt + 1,
                    exc.response.status_code,
                    backoff,
                )
                time.sleep(backoff)
                last_exc = exc
                continue
            else:
                logger.error("HTTP error (not retrying): %s", exc)
                raise

    raise last_exc  # type: ignore[misc]


async def check_health() -> dict:
    """
    Check the health of the inference endpoint.

    Sends a minimal request to verify the endpoint is reachable and
    returns a status dict. Does NOT use retries — this is a quick
    connectivity probe.

    Returns:
        Dict with keys:
            - status: "healthy", "unhealthy", or "not_configured"
            - endpoint: The configured endpoint URL
            - message: Human-readable status message
    """
    endpoint = settings.inference.endpoint

    # If no endpoint is configured (defaults still point to localhost),
    # report not_configured only if api_key is empty AND endpoint is default.
    if not settings.inference.api_key and endpoint == settings.inference.__class__.model_fields["endpoint"].default:
        return {
            "status": "not_configured",
            "endpoint": endpoint,
            "message": "Inference endpoint not configured. Set INFERENCE_API_KEY and INFERENCE_ENDPOINT environment variables.",
        }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(endpoint)
            # Many OpenAI-compatible endpoints return 200 on a simple GET
            # or may redirect. We accept 2xx as healthy.
            if 200 <= response.status_code < 300:
                return {
                    "status": "healthy",
                    "endpoint": endpoint,
                    "message": "Inference endpoint is reachable.",
                }
            return {
                "status": "unhealthy",
                "endpoint": endpoint,
                "message": f"Inference endpoint returned HTTP {response.status_code}.",
            }
    except Exception as exc:
        return {
            "status": "unhealthy",
            "endpoint": endpoint,
            "message": f"Connection failed: {exc}",
        }
