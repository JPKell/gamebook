"""Git-friendly series export/import (SPEC §6.1, ADR 0004).

Layout::

    series.yaml
    rules/<key>.yaml
    enemies/<key>.yaml  items/<key>.yaml  tables/<key>.yaml
    characters/<key>.md  lore/<type>/<key>.md
    books/<NN>-<key>/book.yaml
    books/<NN>-<key>/{enemies,items,tables,characters,lore}/…   (book-specific)
    books/<NN>-<key>/acts/<NN>-<key>/act.yaml
    books/<NN>-<key>/acts/<NN>-<key>/nodes/<key>.md            (front matter + beat notes)

Output is deterministic (stable ordering, no timestamps, empty values omitted)
so diffs show only real changes. Cross references are written as keys for
readability; ids are kept so identity survives a round trip.
"""

from __future__ import annotations

import io
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from gamebook.core.keys import key_problem
from gamebook.db.base import utcnow
from gamebook.db.models import (
    Act,
    BeatNode,
    Book,
    Character,
    Choice,
    ChoiceOutcome,
    Encounter,
    EncounterEnemy,
    Enemy,
    Item,
    LoreEntry,
    Node,
    NodeCharacter,
    NodeItem,
    ProseVersion,
    RandomTable,
    RuleSystem,
    Series,
    ShopItem,
    StoryBeat,
    TextVariant,
)

FORMAT = "gamebook-tree"
VERSION = 1
MANAGED = ("series.yaml", "rules", "enemies", "items", "tables", "characters", "lore", "books")


class TreeError(ValueError):
    pass


# ── YAML ────────────────────────────────────────────────────────────────


class _Dumper(yaml.SafeDumper):
    pass


def _str_representer(dumper: yaml.SafeDumper, value: str) -> yaml.Node:
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_Dumper.add_representer(str, _str_representer)


def _dump(data: Mapping[str, Any]) -> str:
    return yaml.dump(
        dict(data),
        Dumper=_Dumper,
        sort_keys=False,
        allow_unicode=True,
        width=100,
        default_flow_style=False,
    )


def _clean(data: Mapping[str, Any]) -> dict[str, Any]:
    """Drop top-level None, empty strings/lists/dicts and False flags (all are
    the defaults on import). Nested values are kept verbatim — e.g. an effect's
    ``once: false`` is meaningful and must survive."""
    return {
        k: v
        for k, v in data.items()
        if not (v is None or v is False or v == "" or v == [] or v == {})
    }


def _front_matter(meta: Mapping[str, Any], body: str) -> str:
    text = f"---\n{_dump(meta)}---\n"
    if body:
        text += body if body.endswith("\n") else body + "\n"
    return text


def _parse_front_matter(text: str, path: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        raise TreeError(f"{path}: missing front matter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise TreeError(f"{path}: unterminated front matter")
    meta = yaml.safe_load(text[4 : end + 1]) or {}
    body = text[end + 5 :]
    if body.endswith("\n"):
        body = body[:-1]
    return meta, body


def _load_yaml(text: str, path: str) -> dict[str, Any]:
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise TreeError(f"{path}: expected a mapping")
    return data


# ── export ──────────────────────────────────────────────────────────────


def _dir(position: int, key: str) -> str:
    return f"{position:02d}-{key}"


def export_series(session: Session, series_id: str) -> dict[str, str]:
    """Return ``{relative path: file content}`` for a whole series."""
    series = session.get(Series, series_id)
    if series is None:
        raise TreeError(f"Series {series_id} not found")
    files: dict[str, str] = {}

    def entity_keys(model: type[Any]) -> dict[str, str]:
        return dict(
            session.execute(select(model.id, model.key).where(model.series_id == series_id)).all()
        )

    item_keys = entity_keys(Item)
    enemy_keys = entity_keys(Enemy)
    table_keys = entity_keys(RandomTable)
    char_keys = entity_keys(Character)
    lore_keys = entity_keys(LoreEntry)

    files["series.yaml"] = _dump(
        _clean(
            {
                "format": FORMAT,
                "version": VERSION,
                "id": series.id,
                "key": series.key,
                "title": series.title,
                "description": series.description,
                "style": series.style,
            }
        )
    )
    for rs in sorted(series.rule_systems, key=lambda r: r.key):
        files[f"rules/{rs.key}.yaml"] = _dump(
            _clean({"id": rs.id, "key": rs.key, "name": rs.name, "is_active": rs.is_active})
            | {"definition": rs.definition}
        )

    books = sorted(series.books, key=lambda b: (b.number or 0, b.key))
    book_dirs = {b.id: f"books/{_dir(b.number or 0, b.key)}" for b in books}

    def prefix(book_id: str | None) -> str:
        return f"{book_dirs[book_id]}/" if book_id else ""

    for e in session.scalars(select(Enemy).where(Enemy.series_id == series_id).order_by(Enemy.key)):
        files[f"{prefix(e.book_id)}enemies/{e.key}.yaml"] = _dump(
            _clean(
                {
                    "id": e.id,
                    "key": e.key,
                    "name": e.name,
                    "description": e.description,
                    "tags": e.tags,
                    "default_level": e.default_level if e.default_level != 1 else None,
                    "stat_formulas": dict(sorted(e.stat_formulas.items())),
                    "abilities": e.abilities,
                    "loot": e.loot,
                    "lore": lore_keys.get(e.lore_entry_id or ""),
                }
            )
        )
    for i in session.scalars(select(Item).where(Item.series_id == series_id).order_by(Item.key)):
        files[f"{prefix(i.book_id)}items/{i.key}.yaml"] = _dump(
            _clean(
                {
                    "id": i.id,
                    "key": i.key,
                    "name": i.name,
                    "description": i.description,
                    "category": i.category,
                    "slot": i.slot,
                    "stackable": i.stackable,
                    "max_stack": i.max_stack,
                    "value": i.value or None,
                    "uses": i.uses,
                    "modifiers": i.modifiers,
                    "use_effects": i.use_effects,
                }
            )
        )
    for t in session.scalars(
        select(RandomTable).where(RandomTable.series_id == series_id).order_by(RandomTable.key)
    ):
        files[f"{prefix(t.book_id)}tables/{t.key}.yaml"] = _dump(
            _clean(
                {
                    "id": t.id,
                    "key": t.key,
                    "name": t.name,
                    "description": t.description,
                    "dice": t.dice,
                }
            )
            | {"entries": t.entries}
        )
    for c in session.scalars(
        select(Character).where(Character.series_id == series_id).order_by(Character.key)
    ):
        files[f"{prefix(c.book_id)}characters/{c.key}.md"] = _front_matter(
            _clean(
                {
                    "id": c.id,
                    "key": c.key,
                    "name": c.name,
                    "role": c.role,
                    "appearance": c.appearance,
                    "voice": c.voice,
                    "motivations": c.motivations,
                    "secrets": c.secrets,
                    "relationships": c.relationships,
                }
            ),
            c.notes,
        )
    for le in session.scalars(
        select(LoreEntry).where(LoreEntry.series_id == series_id).order_by(LoreEntry.key)
    ):
        files[f"{prefix(le.book_id)}lore/{le.type}/{le.key}.md"] = _front_matter(
            _clean(
                {
                    "id": le.id,
                    "key": le.key,
                    "name": le.name,
                    "fields": dict(sorted(le.fields.items())),
                }
            ),
            le.body,
        )

    keys = _ExportKeys(item_keys, enemy_keys, table_keys, char_keys, lore_keys)
    for b in books:
        for rel, content in _book_files(session, b, keys, include_prose=True).items():
            files[f"{book_dirs[b.id]}/{rel}"] = content
    return dict(sorted(files.items()))


@dataclass(frozen=True)
class _ExportKeys:
    item: Mapping[str, str]
    enemy: Mapping[str, str]
    table: Mapping[str, str]
    character: Mapping[str, str]
    lore: Mapping[str, str]

    @classmethod
    def load(cls, session: Session, series_id: str) -> _ExportKeys:
        def ids(model: type[Any]) -> dict[str, str]:
            return dict(
                session.execute(
                    select(model.id, model.key).where(model.series_id == series_id)
                ).all()
            )

        return cls(ids(Item), ids(Enemy), ids(RandomTable), ids(Character), ids(LoreEntry))


def _book_files(
    session: Session, b: Book, keys: _ExportKeys, *, include_prose: bool = False
) -> dict[str, str]:
    """Files for one book, relative to its directory (book.yaml, acts/…)."""
    files: dict[str, str] = {}
    nodes = list(session.scalars(select(Node).where(Node.book_id == b.id).order_by(Node.key)))
    node_keys = {n.id: n.key for n in nodes}
    files["book.yaml"] = _dump(
        _clean(
            {
                "id": b.id,
                "key": b.key,
                "number": b.number,
                "title": b.title,
                "synopsis": b.synopsis,
                "style_overrides": b.style_overrides,
                "start": node_keys.get(b.start_node_id or ""),
            }
        )
    )
    acts = sorted(b.acts, key=lambda a: a.position)
    act_dirs = {a.id: f"acts/{_dir(a.position + 1, a.key)}" for a in acts}
    for a in acts:
        files[f"{act_dirs[a.id]}/act.yaml"] = _dump(
            _clean(
                {
                    "id": a.id,
                    "key": a.key,
                    "title": a.title,
                    "color": a.color,
                    "summary": a.summary,
                    "beats": [
                        _clean(
                            {
                                "id": bt.id,
                                "title": bt.title,
                                "description": bt.description,
                                "nodes": [node_keys[n] for n in bt.node_ids if n in node_keys],
                            }
                        )
                        for bt in a.beats
                    ],
                }
            )
        )
    # Approved prose travels with the git tree (not with undo snapshots: prose has its
    # own version history, which undo must not rewind).
    approved: dict[str, ProseVersion] = {}
    if include_prose:
        for pv in session.scalars(
            select(ProseVersion).where(
                ProseVersion.book_id == b.id, ProseVersion.status == "approved"
            )
        ):
            approved[pv.variant_id] = pv
    for n in nodes:
        meta = _node_meta(
            n, node_keys, keys.item, keys.enemy, keys.table, keys.character, keys.lore
        )
        prose = [
            _clean(
                {
                    "variant": v.id,
                    "text": approved[v.id].text,
                    "summary": approved[v.id].summary,
                    "inputs_hash": approved[v.id].inputs_hash,
                }
            )
            for v in n.variants
            if v.id in approved
        ]
        if prose:
            meta["prose"] = prose
        files[f"{act_dirs[n.act_id]}/nodes/{n.key}.md"] = _front_matter(meta, n.beat_notes)
    return files


def export_book(session: Session, book_id: str) -> dict[str, str]:
    """One book's story graph (no entities), as used by undo history."""
    book = session.get(Book, book_id)
    if book is None:
        raise TreeError(f"Book {book_id} not found")
    return dict(
        sorted(_book_files(session, book, _ExportKeys.load(session, book.series_id)).items())
    )


def restore_book(session: Session, book_id: str, files: Mapping[str, str]) -> None:
    """Replace a book's acts and nodes (and its own fields) with an ``export_book`` snapshot.

    Raises TreeError if the snapshot refers to entities that no longer exist.
    """
    from gamebook.services import refs  # local import: export ← services is one-way

    book = session.get(Book, book_id)
    if book is None:
        raise TreeError(f"Book {book_id} not found")
    try:
        meta = _load_yaml(files["book.yaml"], "book.yaml")
    except KeyError as exc:
        raise TreeError("Snapshot has no book.yaml") from exc
    keys = _EntityKeys(session, book.series_id)
    book.start_node_id = None
    session.flush()
    for node in list(session.scalars(select(Node).where(Node.book_id == book_id))):
        refs.drop_node_tree(session, node)
        session.delete(node)
    session.flush()
    refs.drop(session, "beat", [b.id for a in book.acts for b in a.beats])
    for act in list(book.acts):
        session.delete(act)
    session.flush()
    session.expire(book)
    book.key = _k(meta)
    book.number = meta.get("number")
    book.title = meta["title"]
    book.synopsis = meta.get("synopsis", "")
    book.style_overrides = meta.get("style_overrides", {})
    _import_book(session, book, files, keys)
    session.flush()
    ctx = refs.RefContext(session, book.series_id)
    for node in session.scalars(select(Node).where(Node.book_id == book_id)):
        refs.reindex_node_tree(session, node, ctx)
    for beat in session.scalars(
        select(StoryBeat).join(Act, StoryBeat.act_id == Act.id).where(Act.book_id == book_id)
    ):
        refs.reindex(session, "beat", beat, ctx)


def _node_meta(
    n: Node,
    node_keys: Mapping[str, str],
    item_keys: Mapping[str, str],
    enemy_keys: Mapping[str, str],
    table_keys: Mapping[str, str],
    char_keys: Mapping[str, str],
    lore_keys: Mapping[str, str],
) -> dict[str, Any]:
    ending = (
        _clean({"kind": n.ending_kind, "grade": n.ending_grade, "label": n.ending_label})
        if n.ending_kind
        else None
    )
    return _clean(
        {
            "id": n.id,
            "key": n.key,
            "title": n.title,
            "summary": n.summary,
            "act_entry": n.is_act_entry,
            "act_exit": n.is_act_exit,
            "ending": ending,
            "location": lore_keys.get(n.location_id or ""),
            "characters": sorted(
                char_keys[c.character_id] for c in n.characters if c.character_id in char_keys
            ),
            "canonical_predecessor": node_keys.get(n.canonical_predecessor_id or ""),
            "style_override": n.style_override,
            "section_pin": n.section_pin,
            "on_enter": n.on_enter,
            "items": [
                {"item": item_keys[p.item_id], "qty": p.qty}
                for p in n.items
                if p.item_id in item_keys
            ],
            "shop": (
                _clean(
                    {
                        "enabled": True,
                        "sell_rate": n.shop_sell_rate,
                        "items": [
                            _clean(
                                {"item": item_keys[s.item_id], "price": s.price, "stock": s.stock}
                            )
                            for s in n.shop_items
                            if s.item_id in item_keys
                        ],
                    }
                )
                if n.is_shop
                else None
            ),
            "variants": [
                _clean(
                    {
                        "id": v.id,
                        "label": v.label,
                        "condition": v.condition,
                        "priority": v.priority or None,
                    }
                )
                for v in n.variants
            ],
            "encounters": [
                _clean(
                    {
                        "id": e.id,
                        "label": e.label,
                        "mode": e.mode if e.mode != "fixed" else None,
                        "fight": e.fight if e.fight != "sequential" else None,
                        "table": table_keys.get(e.table_id or ""),
                        "enemies": [
                            {"enemy": enemy_keys[x.enemy_id], "level": x.level, "count": x.count}
                            for x in e.enemies
                            if x.enemy_id in enemy_keys
                        ],
                    }
                )
                for e in n.encounters
            ],
            "choices": [
                _clean(
                    {
                        "id": c.id,
                        "label": c.label,
                        "kind": c.kind if c.kind != "goto" else None,
                        "condition": c.condition,
                        "unmet_display": c.unmet_display if c.unmet_display != "hide" else None,
                        "print_text": c.print_text,
                        "min_tier": c.min_tier,
                        "effects": c.effects,
                        "dice": c.dice,
                        "test": c.test,
                        "encounter": c.encounter_id,
                        "flee_allowed": c.flee_allowed,
                        "outcomes": [
                            {
                                "key": o.key,
                                "target": node_keys.get(o.target_node_id or ""),
                                **(
                                    {"range": [o.range_lo, o.range_hi]}
                                    if o.range_lo is not None or o.range_hi is not None
                                    else {}
                                ),
                            }
                            for o in c.outcomes
                        ],
                    }
                )
                for c in n.choices
            ],
            "layout": _clean({"x": n.x, "y": n.y, "collapsed": n.collapsed})
            or {"x": 0.0, "y": 0.0},
        }
    )


# ── files on disk / zip ─────────────────────────────────────────────────


def write_tree(files: Mapping[str, str], root: Path) -> None:
    """Write an export, removing stale managed files (other files are untouched)."""
    root.mkdir(parents=True, exist_ok=True)
    real_root = root.resolve()
    for name in MANAGED:
        target = root / name
        if target.is_symlink():
            raise TreeError(f"{target} is a symlink; refusing to manage it")
        if target.is_file():
            target.unlink()
        elif target.is_dir():
            for p in sorted(target.rglob("*"), reverse=True):
                p.unlink() if p.is_file() else p.rmdir()
            target.rmdir()
    for rel, content in files.items():
        path = root / rel
        if not path.resolve().is_relative_to(real_root):
            raise TreeError(f"Refusing to write outside the export folder: {rel}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def read_tree(root: Path) -> dict[str, str]:
    if not (root / "series.yaml").is_file():
        raise TreeError(f"{root} has no series.yaml")
    files: dict[str, str] = {}
    for name in MANAGED:
        target = root / name
        paths = (
            [target] if target.is_file() else sorted(target.rglob("*")) if target.is_dir() else []
        )
        for p in paths:
            if p.is_file() and p.suffix in (".yaml", ".md"):
                files[p.relative_to(root).as_posix()] = p.read_text(encoding="utf-8")
    return files


def to_zip(files: Mapping[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel, content in files.items():
            info = zipfile.ZipInfo(rel, date_time=(2000, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, content)
    return buf.getvalue()


MAX_ZIP_ENTRIES = 50_000
MAX_ZIP_BYTES = 200 * 1024 * 1024


def from_zip(data: bytes) -> dict[str, str]:
    files: dict[str, str] = {}
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        infos = zf.infolist()
        if len(infos) > MAX_ZIP_ENTRIES:
            raise TreeError("Too many files in the zip")
        if sum(i.file_size for i in infos) > MAX_ZIP_BYTES:
            raise TreeError("The zip is too large once extracted")
        for info in infos:
            path = PurePosixPath(info.filename)
            if info.is_dir() or path.is_absolute() or ".." in path.parts:
                continue
            files[path.as_posix()] = zf.read(info).decode("utf-8")
    return files


# ── import ──────────────────────────────────────────────────────────────


def import_series(session: Session, files: Mapping[str, str], *, replace: bool = False) -> Series:
    """Create a series from an export (see ``_import_series``); malformed files raise TreeError."""
    try:
        return _import_series(session, files, replace=replace)
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        if isinstance(exc, TreeError):
            raise
        raise TreeError(f"Malformed export: {type(exc).__name__}: {exc}") from exc


def _import_series(session: Session, files: Mapping[str, str], *, replace: bool = False) -> Series:
    """Create a series from an export. With ``replace``, an existing series with
    the same id is deleted first. The RefIndex is rebuilt afterwards."""
    from gamebook.services import refs  # local import: export ← services is one-way

    if "series.yaml" not in files:
        raise TreeError("Missing series.yaml")
    meta = _load_yaml(files["series.yaml"], "series.yaml")
    if meta.get("format") != FORMAT:
        raise TreeError("series.yaml is not a gamebook tree export")
    if int(meta.get("version", 0)) > VERSION:
        raise TreeError(f"Export version {meta['version']} is newer than this app supports")

    existing = session.get(Series, meta["id"])
    if existing is not None:
        if not replace:
            raise TreeError(f"Series {meta['key']!r} already exists (use replace)")
        from gamebook.services.series import delete_series

        delete_series(session, existing.id)
    clash = session.scalar(select(Series).where(Series.key == meta["key"]))
    if clash is not None:
        raise TreeError(f"Another series already uses the key {meta['key']!r}")

    series = Series(
        id=meta["id"],
        key=_k(meta),
        title=meta["title"],
        description=meta.get("description", ""),
        style=meta.get("style", {}),
    )
    session.add(series)
    session.flush()

    # Group files by book directory.
    book_dirs: dict[str, dict[str, str]] = {}
    series_files: dict[str, str] = {}
    for rel, content in files.items():
        parts = rel.split("/")
        if parts[0] == "books" and len(parts) > 2:
            book_dirs.setdefault(parts[1], {})["/".join(parts[2:])] = content
        elif parts[0] != "books":
            series_files[rel] = content

    for rel, content in _under(series_files, "rules"):
        data = _load_yaml(content, rel)
        session.add(
            RuleSystem(
                id=data["id"],
                series_id=series.id,
                key=_k(data),
                name=data["name"],
                is_active=bool(data.get("is_active", False)),
                definition=data["definition"],
            )
        )

    books: list[tuple[Book, dict[str, str]]] = []
    for dirname in sorted(book_dirs):
        bfiles = book_dirs[dirname]
        if "book.yaml" not in bfiles:
            raise TreeError(f"books/{dirname} has no book.yaml")
        data = _load_yaml(bfiles["book.yaml"], f"books/{dirname}/book.yaml")
        book = Book(
            id=data["id"],
            series_id=series.id,
            key=_k(data),
            number=data.get("number"),
            title=data["title"],
            synopsis=data.get("synopsis", ""),
            style_overrides=data.get("style_overrides", {}),
        )
        session.add(book)
        books.append((book, bfiles))
    session.flush()

    # Lore (any scope) first — enemies may link to it — then other entities.
    _import_lore(session, series.id, None, series_files, "")
    for book, bfiles in books:
        _import_lore(session, series.id, book.id, bfiles, f"books/{book.key}/")
    session.flush()
    _import_entities(session, series.id, None, series_files, "")
    for book, bfiles in books:
        _import_entities(session, series.id, book.id, bfiles, f"books/{book.key}/")
    session.flush()

    keys = _EntityKeys(session, series.id)
    for book, bfiles in books:
        _import_book(session, book, bfiles, keys)
    session.flush()
    refs.rebuild_series(session, series.id)
    return series


def _under(files: Mapping[str, str], folder: str) -> list[tuple[str, str]]:
    return sorted((k, v) for k, v in files.items() if k.startswith(f"{folder}/"))


class _EntityKeys:
    def __init__(self, session: Session, series_id: str) -> None:
        def keys(model: type[Any]) -> dict[str, str]:
            return dict(
                session.execute(
                    select(model.key, model.id).where(model.series_id == series_id)
                ).all()
            )

        self.item = keys(Item)
        self.enemy = keys(Enemy)
        self.table = keys(RandomTable)
        self.character = keys(Character)
        self.lore = keys(LoreEntry)

    @staticmethod
    def required(table: Mapping[str, str], key: str, where: str) -> str:
        if key not in table:
            raise TreeError(f"{where}: unknown key {key!r}")
        return table[key]

    @staticmethod
    def get(table: Mapping[str, str], key: str | None, where: str) -> str | None:
        if key is None:
            return None
        if key not in table:
            raise TreeError(f"{where}: unknown key {key!r}")
        return table[key]


LORE_TYPES = frozenset({"location", "faction", "history", "glossary", "other"})


def _k(data: Mapping[str, Any]) -> str:
    """A validated key from imported data (keys end up in file paths on export)."""
    key = data.get("key")
    if not isinstance(key, str) or (problem := key_problem(key)) is not None:
        raise TreeError(f"Invalid key {key!r}: {problem if isinstance(key, str) else 'missing'}")
    return key


def _import_lore(
    session: Session, series_id: str, book_id: str | None, files: Mapping[str, str], where: str
) -> None:
    for rel, content in _under(files, "lore"):
        meta, body = _parse_front_matter(content, where + rel)
        lore_type = rel.split("/")[1]
        if lore_type not in LORE_TYPES:
            raise TreeError(f"{where}{rel}: unknown lore type {lore_type!r}")
        session.add(
            LoreEntry(
                id=meta["id"],
                series_id=series_id,
                book_id=book_id,
                key=_k(meta),
                name=meta["name"],
                type=lore_type,
                body=body,
                fields=meta.get("fields", {}),
            )
        )


def _import_entities(
    session: Session, series_id: str, book_id: str | None, files: Mapping[str, str], where: str
) -> None:
    all_lore = dict(
        session.execute(
            select(LoreEntry.key, LoreEntry.id).where(LoreEntry.series_id == series_id)
        ).all()
    )
    for rel, content in _under(files, "enemies"):
        d = _load_yaml(content, where + rel)
        session.add(
            Enemy(
                id=d["id"],
                series_id=series_id,
                book_id=book_id,
                key=_k(d),
                name=d["name"],
                description=d.get("description", ""),
                tags=d.get("tags", []),
                default_level=d.get("default_level", 1),
                stat_formulas=d.get("stat_formulas", {}),
                abilities=d.get("abilities", []),
                loot=d.get("loot", []),
                lore_entry_id=_EntityKeys.get(all_lore, d.get("lore"), where + rel),
            )
        )
    for rel, content in _under(files, "items"):
        d = _load_yaml(content, where + rel)
        session.add(
            Item(
                id=d["id"],
                series_id=series_id,
                book_id=book_id,
                key=_k(d),
                name=d["name"],
                description=d.get("description", ""),
                category=d.get("category", "treasure"),
                slot=d.get("slot"),
                stackable=d.get("stackable", False),
                max_stack=d.get("max_stack"),
                value=d.get("value", 0),
                uses=d.get("uses"),
                modifiers=d.get("modifiers", []),
                use_effects=d.get("use_effects", []),
            )
        )
    for rel, content in _under(files, "tables"):
        d = _load_yaml(content, where + rel)
        session.add(
            RandomTable(
                id=d["id"],
                series_id=series_id,
                book_id=book_id,
                key=_k(d),
                name=d["name"],
                description=d.get("description", ""),
                dice=d.get("dice", "1d6"),
                entries=d.get("entries", []),
            )
        )
    for rel, content in _under(files, "characters"):
        meta, body = _parse_front_matter(content, where + rel)
        session.add(
            Character(
                id=meta["id"],
                series_id=series_id,
                book_id=book_id,
                key=_k(meta),
                name=meta["name"],
                role=meta.get("role", ""),
                appearance=meta.get("appearance", ""),
                voice=meta.get("voice", ""),
                motivations=meta.get("motivations", ""),
                secrets=meta.get("secrets", ""),
                notes=body,
                relationships=meta.get("relationships", []),
            )
        )


def _import_book(session: Session, book: Book, files: Mapping[str, str], keys: _EntityKeys) -> None:
    act_files = sorted(k for k in files if k.startswith("acts/") and k.endswith("/act.yaml"))
    node_metas: list[tuple[str, dict[str, Any], str, str]] = []  # (act id, meta, body, path)
    beat_data: list[tuple[str, list[dict[str, Any]], str]] = []  # (act id, beats, path)
    for position, act_rel in enumerate(act_files):
        d = _load_yaml(files[act_rel], act_rel)
        act = Act(
            id=d["id"],
            book_id=book.id,
            key=_k(d),
            position=position,
            title=d["title"],
            color=d.get("color"),
            summary=d.get("summary", ""),
        )
        session.add(act)
        beat_data.append((act.id, d.get("beats", []), act_rel))
        act_dir = act_rel.rsplit("/", 1)[0]
        for rel in sorted(k for k in files if k.startswith(f"{act_dir}/nodes/")):
            meta, body = _parse_front_matter(files[rel], rel)
            node_metas.append((act.id, meta, body, rel))
    session.flush()

    node_ids = {meta["key"]: meta["id"] for _, meta, _, _ in node_metas}

    def node_ref(key: str | None, where: str) -> str | None:
        return _EntityKeys.get(node_ids, key, where)

    for act_id, meta, body, rel in node_metas:
        ending = meta.get("ending") or {}
        layout = meta.get("layout") or {}
        shop = meta.get("shop")
        node = Node(
            id=meta["id"],
            book_id=book.id,
            act_id=act_id,
            key=_k(meta),
            title=meta["title"],
            beat_notes=body,
            summary=meta.get("summary", ""),
            is_act_entry=meta.get("act_entry", False),
            is_act_exit=meta.get("act_exit", False),
            ending_kind=ending.get("kind"),
            ending_grade=ending.get("grade"),
            ending_label=ending.get("label", ""),
            location_id=_EntityKeys.get(keys.lore, meta.get("location"), rel),
            style_override=meta.get("style_override", {}),
            section_pin=meta.get("section_pin"),
            on_enter=meta.get("on_enter", []),
            is_shop=shop is not None,
            shop_sell_rate=(shop or {}).get("sell_rate"),
            x=float(layout.get("x", 0.0)),
            y=float(layout.get("y", 0.0)),
            collapsed=layout.get("collapsed", False),
        )
        node.characters = [
            NodeCharacter(character_id=_EntityKeys.required(keys.character, k, rel))
            for k in meta.get("characters", [])
        ]
        node.items = [
            NodeItem(
                item_id=_EntityKeys.required(keys.item, p["item"], rel),
                qty=p.get("qty", 1),
                position=i,
            )
            for i, p in enumerate(meta.get("items", []))
        ]
        node.shop_items = [
            ShopItem(
                item_id=_EntityKeys.required(keys.item, s["item"], rel),
                price=s.get("price", 0),
                stock=s.get("stock"),
                position=i,
            )
            for i, s in enumerate((shop or {}).get("items", []))
        ]
        node.variants = [
            TextVariant(
                id=v["id"],
                label=v.get("label", "Default"),
                condition=v.get("condition"),
                priority=v.get("priority", 0),
                position=i,
            )
            for i, v in enumerate(meta.get("variants", []))
        ]
        node.encounters = [
            Encounter(
                id=e["id"],
                label=e.get("label", ""),
                mode=e.get("mode", "fixed"),
                fight=e.get("fight", "sequential"),
                table_id=_EntityKeys.get(keys.table, e.get("table"), rel),
                position=i,
                enemies=[
                    EncounterEnemy(
                        enemy_id=_EntityKeys.required(keys.enemy, x["enemy"], rel),
                        level=x.get("level", 1),
                        count=x.get("count", 1),
                        position=j,
                    )
                    for j, x in enumerate(e.get("enemies", []))
                ],
            )
            for i, e in enumerate(meta.get("encounters", []))
        ]
        session.add(node)
    session.flush()

    for _act_id, meta, _body, rel in node_metas:
        for i, c in enumerate(meta.get("choices", [])):
            choice = Choice(
                id=c["id"],
                node_id=meta["id"],
                position=i,
                label=c.get("label", ""),
                kind=c.get("kind", "goto"),
                condition=c.get("condition"),
                unmet_display=c.get("unmet_display", "hide"),
                print_text=c.get("print_text"),
                min_tier=c.get("min_tier"),
                effects=c.get("effects", []),
                dice=c.get("dice"),
                test=c.get("test"),
                encounter_id=c.get("encounter"),
                flee_allowed=c.get("flee_allowed", False),
            )
            choice.outcomes = [
                ChoiceOutcome(
                    key=o.get("key", "default"),
                    position=j,
                    target_node_id=node_ref(o.get("target"), rel),
                    range_lo=(o.get("range") or [None, None])[0],
                    range_hi=(o.get("range") or [None, None])[1],
                )
                for j, o in enumerate(c.get("outcomes", []))
            ]
            session.add(choice)
        stored = session.get(Node, meta["id"])
        assert stored is not None
        stored.canonical_predecessor_id = node_ref(meta.get("canonical_predecessor"), rel)
        variant_ids = {v.id for v in stored.variants}
        for p in meta.get("prose", []):
            if p.get("variant") not in variant_ids:
                raise TreeError(f"{rel}: prose for unknown variant {p.get('variant')!r}")
            session.add(
                ProseVersion(
                    book_id=book.id,
                    node_id=stored.id,
                    variant_id=p["variant"],
                    text=p.get("text", ""),
                    summary=p.get("summary", ""),
                    inputs_hash=p.get("inputs_hash", ""),
                    status="approved",
                    source="human",
                    approved_at=utcnow(),
                )
            )
    for act_id, beats, rel in beat_data:
        for i, bt in enumerate(beats):
            beat = StoryBeat(
                id=bt["id"],
                act_id=act_id,
                position=i,
                title=bt.get("title", ""),
                description=bt.get("description", ""),
            )
            beat.links = [
                BeatNode(node_id=nid, position=j)
                for j, key in enumerate(bt.get("nodes", []))
                if (nid := node_ref(key, rel)) is not None
            ]
            session.add(beat)
    book.start_node_id = node_ref(
        _load_yaml(files["book.yaml"], "book.yaml").get("start"), "book.yaml"
    )
