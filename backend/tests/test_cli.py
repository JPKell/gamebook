import json
from pathlib import Path

from gamebook.cli import main


def test_openapi_command_writes_schema(tmp_path: Path) -> None:
    out = tmp_path / "openapi.json"
    main(["openapi", "-o", str(out)])
    spec = json.loads(out.read_text())
    assert spec["info"]["title"] == "Gamebook Studio"
    assert "/api/health" in spec["paths"]
