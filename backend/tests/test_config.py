from pathlib import Path

import pytest

from gamebook.config import Settings


def test_database_url_defaults_into_data_dir(tmp_path: Path) -> None:
    s = Settings(data_dir=tmp_path)
    assert s.database_url == f"sqlite:///{tmp_path / 'gamebook.db'}"


def test_yaml_then_env_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "custom.yaml"
    cfg.write_text("log_level: DEBUG\ndata_dir: from-yaml\ncors_origins: [http://a]\n")
    monkeypatch.setenv("GAMEBOOK_CONFIG", str(cfg))
    s = Settings()
    assert s.log_level == "DEBUG"
    assert s.data_dir == Path("from-yaml")
    assert s.cors_origins == ["http://a"]

    monkeypatch.setenv("GAMEBOOK_LOG_LEVEL", "ERROR")
    assert Settings().log_level == "ERROR"


def test_missing_yaml_is_fine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GAMEBOOK_CONFIG", str(tmp_path / "absent.yaml"))
    assert Settings().log_level == "INFO"
