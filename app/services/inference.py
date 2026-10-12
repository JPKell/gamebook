"""
Inference service.

HTTP client for sending prompts to the external AI inference endpoint.
This module does NOT serve or run models — it only constructs requests,
sends them to the configured endpoint (e.g. LoadCoach), and returns
responses.

Used in Phase 7+ for story generation and AI playthroughs. The prompt
construction is handled by individual route handlers or future services;
this module provides the transport layer.

Configuration comes from app.config.settings.inference.
"""

import httpx
from app.config import settings


async def send_completion(prompt: str, model: str | None = None) -> str:
    """
    Send a chat completion request to the inference endpoint.

    Args:
        prompt: The text prompt to send to the model.
        model: Model name to use. Defaults to settings.inference.default_model.

    Returns:
        The model's response text.

    Raises:
        httpx.HTTPError: If the request fails (timeout, connection, etc.).
    """
    model = model or settings.inference.default_model
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.inference.api_key}"
        if settings.inference.api_key
        else "",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 2000,
    }

    async with httpx.AsyncClient(timeout=settings.inference.timeout) as client:
        response = await client.post(
            settings.inference.endpoint,
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
