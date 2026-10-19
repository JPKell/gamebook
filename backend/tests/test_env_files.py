"""Keys in a .env file reach providers (which read os.environ)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from gamebook import config


def test_env_files_load_without_overriding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".env").write_text("GB_TEST_ONE_KEY='from-file'\nGB_TEST_TWO_KEY=from-file\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "REPO_ROOT", tmp_path / "missing")
    monkeypatch.delenv("GB_TEST_ONE_KEY", raising=False)
    monkeypatch.setenv("GB_TEST_TWO_KEY", "from-env")
    assert config.load_env_files() == [tmp_path / ".env"]
    try:
        assert os.environ["GB_TEST_ONE_KEY"] == "from-file"
        assert os.environ["GB_TEST_TWO_KEY"] == "from-env"  # the real environment wins
    finally:
        os.environ.pop("GB_TEST_ONE_KEY", None)


def test_repo_root_points_at_the_repository() -> None:
    assert (config.REPO_ROOT / "backend" / "pyproject.toml").is_file()
