from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gamebook.api import create_app
from gamebook.config import Settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data", cors_origins=["http://testserver"])


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as c:
        yield c
