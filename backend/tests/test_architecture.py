"""Enforce layering rules from docs/adr/0002-pure-core.md."""

import ast
from pathlib import Path

import gamebook

PKG = Path(gamebook.__file__).parent

# core/ may only import the stdlib, itself, and these third-party packages.
CORE_ALLOWED_THIRD_PARTY = {"pydantic"}
CORE_FORBIDDEN_STDLIB = {"os", "socket", "subprocess", "sqlite3", "urllib", "http", "asyncio"}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
    return names


def test_core_is_pure() -> None:
    violations = []
    for path in (PKG / "core").rglob("*.py"):
        for name in _imports(path):
            top = name.split(".")[0]
            if top == "gamebook":
                if not name.startswith("gamebook.core"):
                    violations.append(f"{path.relative_to(PKG)} imports {name}")
            elif top in CORE_FORBIDDEN_STDLIB:
                violations.append(f"{path.relative_to(PKG)} imports {name} (IO)")
            elif not _is_stdlib(top) and top not in CORE_ALLOWED_THIRD_PARTY:
                violations.append(f"{path.relative_to(PKG)} imports third-party {name}")
    assert violations == []


def test_api_does_not_reach_into_llm_or_export_directly() -> None:
    """Routers go through services/, keeping HTTP handlers thin."""
    violations = []
    for path in (PKG / "api").rglob("*.py"):
        for name in _imports(path):
            if name.startswith(("gamebook.llm", "gamebook.export", "gamebook.jobs")):
                violations.append(f"{path.relative_to(PKG)} imports {name}")
    assert violations == []


def _is_stdlib(name: str) -> bool:
    import sys

    return name in sys.stdlib_module_names or name == "__future__"


def test_operation_ids_are_unique() -> None:
    """Route function names become client operation ids; a duplicate silently
    mixes up two endpoints' types in the generated TypeScript client."""
    from collections import Counter

    from gamebook.api import create_app
    from gamebook.config import Settings

    app = create_app(Settings(database_url="sqlite:///:memory:", auto_migrate=False))
    ids = [
        op["operationId"]
        for path in app.openapi()["paths"].values()
        for op in path.values()
        if isinstance(op, dict) and "operationId" in op
    ]
    assert [k for k, n in Counter(ids).items() if n > 1] == []
