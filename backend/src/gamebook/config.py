"""Application settings.

Precedence (highest first): constructor arguments, environment variables
(``GAMEBOOK_*``, nested with ``__``), ``.env``, the YAML config file, defaults.
The YAML file is ``config.yaml`` in the working directory unless
``GAMEBOOK_CONFIG`` points elsewhere.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]


def _config_file() -> Path:
    return Path(os.environ.get("GAMEBOOK_CONFIG", "config.yaml"))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GAMEBOOK_",
        env_nested_delimiter="__",
        env_file=".env",
        extra="ignore",
    )

    data_dir: Path = Field(
        default=Path("data"), description="Directory for the database, checkpoints and exports."
    )
    database_url: str = Field(
        default="", description="SQLAlchemy URL. Defaults to <data_dir>/gamebook.db."
    )
    auto_migrate: bool = Field(
        default=True, description="Apply pending migrations when the server starts."
    )
    log_level: LogLevel = "INFO"
    log_json: bool = Field(default=False, description="Emit JSON log lines instead of text.")
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    sim_processes: int = Field(
        default=0,
        ge=0,
        description="Worker processes for bot batches; 0 = one per CPU core, 1 = in-process.",
    )
    frontend_dist: Path | None = Field(
        default=None, description="Built frontend to serve at '/'. Unset in development."
    )

    @model_validator(mode="after")
    def _default_database_url(self) -> "Settings":
        if not self.database_url:
            self.database_url = f"sqlite:///{self.data_dir / 'gamebook.db'}"
        return self

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            YamlConfigSettingsSource(settings_cls, yaml_file=_config_file()),
            file_secret_settings,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
