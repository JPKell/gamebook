from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gamebook.api import create_app
from gamebook.config import Settings
from gamebook.db.repository import NotFoundError


def test_unknown_api_route_uses_error_envelope(client: TestClient) -> None:
    res = client.get("/api/nope")
    assert res.status_code == 404
    assert res.json() == {"detail": "Not Found", "code": "not_found"}


def _app_with_routes(settings: Settings) -> FastAPI:
    app = create_app(settings)

    class Thing:
        pass

    @app.get("/api/_test/missing")
    def missing() -> None:
        raise NotFoundError(Thing, "abc")

    @app.get("/api/_test/boom")
    def boom() -> None:
        raise RuntimeError("kaboom")

    @app.get("/api/_test/typed")
    def typed(n: int) -> int:
        return n

    return app


def test_not_found_error_maps_to_404(settings: Settings) -> None:
    with TestClient(_app_with_routes(settings)) as c:
        res = c.get("/api/_test/missing")
    assert res.status_code == 404
    assert res.json() == {"detail": "Thing abc not found", "code": "not_found"}


def test_unhandled_error_is_500_without_leaking(settings: Settings) -> None:
    with TestClient(_app_with_routes(settings), raise_server_exceptions=False) as c:
        res = c.get("/api/_test/boom")
    assert res.status_code == 500
    assert res.json() == {"detail": "Internal server error", "code": "internal_error"}


def test_validation_error_envelope(settings: Settings) -> None:
    with TestClient(_app_with_routes(settings)) as c:
        res = c.get("/api/_test/typed", params={"n": "x"})
    body = res.json()
    assert res.status_code == 422
    assert body["code"] == "validation_error"
    assert body["errors"][0]["loc"] == ["query", "n"]


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    d = tmp_path / "dist"
    (d / "assets").mkdir(parents=True)
    (d / "index.html").write_text("<html>spa</html>")
    (d / "assets" / "app.js").write_text("console.log(1)")
    (d / "favicon.svg").write_text("<svg/>")
    (tmp_path / "secret.txt").write_text("nope")
    return d


def test_spa_serving(settings: Settings, dist: Path) -> None:
    settings.frontend_dist = dist
    with TestClient(create_app(settings)) as c:
        assert c.get("/").text == "<html>spa</html>"
        assert c.get("/story/some/deep/route").text == "<html>spa</html>"
        assert c.get("/assets/app.js").text == "console.log(1)"
        assert c.get("/favicon.svg").text == "<svg/>"
        assert c.get("/../secret.txt").text != "nope"
        assert c.get("/%2e%2e/secret.txt").text != "nope"
        assert c.get("/api/health").json()["status"] == "ok"
        assert c.get("/api/missing").status_code == 404
        assert c.get("/api").status_code == 404
        assert c.post("/api/missing").status_code == 404
        assert c.post("/api/health").status_code == 405
        assert c.post("/story").status_code == 404


def test_commit_happens_before_the_response(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed commit must surface as an error, not a success the client already saw."""
    from sqlalchemy.orm import Session

    def failing_commit(self: Session) -> None:
        raise RuntimeError("disk full")

    monkeypatch.setattr(Session, "commit", failing_commit)
    with TestClient(client.app, raise_server_exceptions=False) as c:
        res = c.post("/api/series", json={"title": "Never saved"})
    assert res.status_code == 500
