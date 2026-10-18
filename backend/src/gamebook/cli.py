"""Command-line entry point: ``gamebook <command>``."""

import argparse
import json
import sys
from pathlib import Path


def cmd_serve(args: argparse.Namespace) -> None:
    import uvicorn

    uvicorn.run(
        "gamebook.api:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=args.reload,
        reload_dirs=[str(Path(__file__).parent)] if args.reload else None,
    )


def cmd_db_upgrade(args: argparse.Namespace) -> None:
    from gamebook.config import get_settings
    from gamebook.db import migrate

    migrate.upgrade(get_settings().database_url, args.revision)


def cmd_db_revision(args: argparse.Namespace) -> None:
    from gamebook.config import get_settings
    from gamebook.db import migrate

    migrate.revision(get_settings().database_url, args.message)


def cmd_openapi(args: argparse.Namespace) -> None:
    from gamebook.api import create_app
    from gamebook.config import Settings

    app = create_app(Settings(database_url="sqlite:///:memory:", auto_migrate=False))
    schema = json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"
    if args.output == "-":
        sys.stdout.write(schema)
    else:
        Path(args.output).write_text(schema)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gamebook", description="Gamebook Studio")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="Run the API server")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true")
    serve.set_defaults(func=cmd_serve)

    db = sub.add_parser("db", help="Database migrations").add_subparsers(
        dest="db_cmd", required=True
    )
    up = db.add_parser("upgrade", help="Apply migrations")
    up.add_argument("revision", nargs="?", default="head")
    up.set_defaults(func=cmd_db_upgrade)
    rev = db.add_parser("revision", help="Autogenerate a migration")
    rev.add_argument("-m", "--message", required=True)
    rev.set_defaults(func=cmd_db_revision)

    oa = sub.add_parser("openapi", help="Write the OpenAPI schema")
    oa.add_argument("-o", "--output", default="-")
    oa.set_defaults(func=cmd_openapi)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
