"""
Application configuration.

Loads settings from config.yaml (with environment variable overrides)
and exposes them as a typed dataclass. Settings cover the database URL,
inference endpoint for AI generation, CORS origin, and other runtime
parameters.

Environment variables take precedence over config.yaml values. This
allows deployment-specific settings (like API keys) to be injected
without touching the config file.
"""

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel


class InferenceConfig(BaseModel):
    """Configuration for the external inference (LLM) endpoint."""

    endpoint: str = "http://localhost:8442/v1/chat/completions"
    api_key: str = ""
    default_model: str = "qwen3-35b"
    timeout: int = 120
    max_retries: int = 3


class Settings(BaseModel):
    """Application settings, loaded from config.yaml + env vars."""

    # Database
    database_url: str = "sqlite:///gamebook.db"

    # Inference
    inference: InferenceConfig = InferenceConfig()

    # Frontend CORS
    frontend_url: str = "http://localhost:8000"

    # File storage for assembled outputs
    output_dir: str = "output"


def _load_config() -> dict:
    """Load config.yaml from the project root. Returns empty dict if not found."""
    config_path = Path(__file__).resolve().parent.parent.parent / "config.yaml"
    if config_path.exists():
        return yaml.safe_load(config_path.read_text()) or {}
    return {}


def _apply_env_overrides(data: dict) -> dict:
    """Override config values with environment variables where present."""
    overrides = {
        "database_url": "DATABASE_URL",
        "inference.endpoint": "INFERENCE_ENDPOINT",
        "inference.api_key": "INFERENCE_API_KEY",
        "inference.default_model": "INFERENCE_DEFAULT_MODEL",
        "frontend_url": "FRONTEND_URL",
    }
    for key, env_key in overrides.items():
        value = os.environ.get(env_key)
        if value:
            # Handle nested keys like "inference.endpoint"
            parts = key.split(".")
            d = data
            for part in parts[:-1]:
                d = d.setdefault(part, {})
            d[parts[-1]] = value
    return data


# Module-level settings instance. Loaded once on import.
_config = _load_config()
_config = _apply_env_overrides(_config)
settings = Settings(**_config)
