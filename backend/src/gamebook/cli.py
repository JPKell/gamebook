"""Command-line entry point: ``gamebook <command>``."""

import argparse
import json
import sys
from pathlib import Path

from gamebook.config import load_env_files


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


def cmd_db_downgrade(args: argparse.Namespace) -> None:
    from gamebook.config import get_settings
    from gamebook.db import migrate

    migrate.downgrade(get_settings().database_url, args.revision)


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


def cmd_export(args: argparse.Namespace) -> None:
    from gamebook.config import get_settings
    from gamebook.db.session import Database
    from gamebook.services import assets, transfer

    settings = get_settings()
    db = Database(settings.database_url)
    with db.session() as session:
        store = assets.Store(settings.data_dir / "assets")
        count = transfer.export_to_dir(session, store, args.series, Path(args.directory))
    print(f"Exported {count} files to {args.directory}")


def cmd_import(args: argparse.Namespace) -> None:
    from gamebook.config import get_settings
    from gamebook.db import migrate
    from gamebook.db.session import Database
    from gamebook.services import assets, transfer

    settings = get_settings()
    url = settings.database_url
    migrate.upgrade(url)
    db = Database(url)
    with db.session() as session:
        store = assets.Store(settings.data_dir / "assets")
        series = transfer.import_from_dir(
            session, store, Path(args.directory), replace=args.replace
        )
        print(f"Imported series {series.key!r} ({series.title})")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gamebook", description="Gamebook Studio")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="Run the API server")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8788)
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

    ex = sub.add_parser("export", help="Export a series as a git-friendly file tree")
    ex.add_argument("series", help="Series key")
    ex.add_argument("directory")
    ex.set_defaults(func=cmd_export)

    im = sub.add_parser("import", help="Import a series from an exported file tree")
    im.add_argument("directory")
    im.add_argument("--replace", action="store_true", help="Replace the series if it exists")
    im.set_defaults(func=cmd_import)

    dn = db.add_parser("downgrade", help="Revert migrations")
    dn.add_argument("revision")
    dn.set_defaults(func=cmd_db_downgrade)

    oa = sub.add_parser("openapi", help="Write the OpenAPI schema")
    oa.add_argument("-o", "--output", default="-")
    oa.set_defaults(func=cmd_openapi)
    return parser


def main(argv: list[str] | None = None) -> None:
    load_env_files()
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
