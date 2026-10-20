"""Fonts for print layouts: the system's families plus uploaded font files.

Uploads live at ``<data_dir>/fonts/<sha256>.<ext>`` and serve every book. A layout
names a family; the stylesheet gets an ``@font-face`` for each uploaded file of
the families it uses (WeasyPrint embeds them in the PDF). System families come
from fontconfig, which WeasyPrint itself uses.
"""

from __future__ import annotations

import hashlib
import io
import re
import shutil
import subprocess
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from gamebook.core.layout import GENERIC_FAMILIES, css_string
from gamebook.services.errors import InvalidError, ServiceError

MAX_BYTES = 15 * 1024 * 1024
MIMES = {"ttf": "font/ttf", "otf": "font/otf", "woff": "font/woff", "woff2": "font/woff2"}
_FILE = re.compile(r"^([0-9a-f]{64})\.(ttf|otf|woff|woff2)$")
#: Names a layout can use without a family (CSS generic families).
GENERIC = list(GENERIC_FAMILIES)


class NotFoundError(ServiceError):
    status = 404
    code = "not_found"


@dataclass(frozen=True)
class FontFile:
    id: str
    ext: str
    family: str
    weight: int
    italic: bool
    bytes: int

    @property
    def file(self) -> str:
        return f"{self.id}.{self.ext}"


class FontStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def path(self, name: str) -> Path:
        if not _FILE.fullmatch(name):
            raise NotFoundError("No such font")
        return self.root / name

    def list(self) -> list[FontFile]:
        if not self.root.is_dir():
            return []
        out = []
        for p in sorted(self.root.iterdir()):
            m = _FILE.fullmatch(p.name)
            if m and p.is_file():
                info = _describe(p, p.stat().st_mtime_ns)
                if info:
                    out.append(info)
        return sorted(out, key=lambda f: (f.family.lower(), f.weight, f.italic))

    def add(self, data: bytes) -> FontFile:
        if len(data) > MAX_BYTES:
            raise InvalidError("Font files must be at most 15 MB")
        family, weight, italic, ext = _read(data)
        sha = hashlib.sha256(data).hexdigest()
        self.root.mkdir(parents=True, exist_ok=True)
        target = self.root / f"{sha}.{ext}"
        if not target.exists():
            tmp = target.with_suffix(f".{uuid.uuid4().hex}.tmp")
            tmp.write_bytes(data)
            tmp.replace(target)
        return FontFile(sha, ext, family, weight, italic, len(data))

    def delete(self, font_id: str) -> None:
        for f in self.list():
            if f.id == font_id:
                self.path(f.file).unlink(missing_ok=True)
                return
        raise NotFoundError("No such font")

    def faces(self, families: Iterable[str], url: Callable[[FontFile], str]) -> str:
        """``@font-face`` rules for the uploaded files of these families."""
        wanted = {f.lower() for f in families}
        return "\n".join(
            f"@font-face {{ font-family: {css_string(f.family)}; src: url({css_string(url(f))}); "
            f"font-weight: {f.weight}; font-style: {'italic' if f.italic else 'normal'}; }}"
            for f in self.list()
            if f.family.lower() in wanted
        )


def _read(data: bytes) -> tuple[str, int, bool, str]:
    """(family, weight, italic, extension) of a font file, or InvalidError."""
    from fontTools.ttLib import TTFont, TTLibError

    try:
        font = TTFont(io.BytesIO(data), lazy=True)
        name = font["name"]
        family = str(name.getBestFamilyName() or "").strip()
        os2 = font.get("OS/2")
        weight = int(os2.usWeightClass) if os2 is not None else 400
        italic = bool(os2.fsSelection & 1) if os2 is not None else False
        if not italic and "head" in font:
            italic = bool(font["head"].macStyle & 2)
        flavor = font.flavor
        ext = (
            flavor
            if flavor in ("woff", "woff2")
            else "otf"
            if font.sfntVersion == "OTTO"
            else "ttf"
        )
    except (TTLibError, KeyError, AttributeError, ValueError, AssertionError, OSError) as e:
        raise InvalidError("That isn't a font file (TrueType, OpenType or WOFF)") from e
    # Family names reach stylesheets: keep them to the characters a layout may use.
    family = re.sub(r"[^\w .\-]", "", family)[:80].strip()
    if not family or not re.match(r"\w", family):
        raise InvalidError("The font has no usable family name")
    return family, min(900, max(100, int(weight / 100 + 0.5) * 100)), italic, ext


@lru_cache(maxsize=256)
def _describe(path: Path, _mtime: int) -> FontFile | None:
    try:
        data = path.read_bytes()
        family, weight, italic, _ext = _read(data)
    except (InvalidError, OSError):
        return None
    m = _FILE.fullmatch(path.name)
    assert m
    return FontFile(m.group(1), m.group(2), family, weight, italic, len(data))


@lru_cache(maxsize=1)
def system_families() -> tuple[str, ...]:
    """Font families fontconfig knows (empty when fontconfig isn't installed)."""
    exe = shutil.which("fc-list")
    if not exe:
        return ()
    try:
        out = subprocess.run(
            [exe, ":", "family"], capture_output=True, text=True, timeout=10, check=False
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return ()
    names = set()
    for line in out.splitlines():
        # "Name,Localized name": the first is the English name; fc-list escapes '-'.
        name = line.split(",")[0].replace("\\", "").strip()
        if name and re.fullmatch(r"[\w][\w .\-]{0,79}", name):
            names.add(name)
    return tuple(sorted(names, key=str.lower))
