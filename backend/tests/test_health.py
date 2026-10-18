from fastapi.testclient import TestClient

from gamebook import __version__


def test_health_ok(client: TestClient) -> None:
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "version": __version__, "database": "ok"}


def test_startup_applies_migrations(client: TestClient) -> None:
    from alembic.script import ScriptDirectory
    from sqlalchemy import text

    from gamebook.db.migrate import alembic_config

    db = client.app.state.db  # type: ignore[attr-defined]
    with db.engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    head = ScriptDirectory.from_config(alembic_config(db.url)).get_current_head()
    assert version == head


def test_openapi_operation_ids_are_function_names(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()
    assert spec["paths"]["/api/health"]["get"]["operationId"] == "get_health"
