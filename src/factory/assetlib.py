"""Asset library (M2): generated SVG props with provenance, dedupe and a strict sanitizer.

Layout (committed to git, so assets are reused across episodes and machines):
  library/assets/index.json         list of AssetRecord
  library/assets/svg/<asset_id>.svg

Generated SVG is untrusted model output: `sanitize_svg` re-serialises only an allowlist of
shape/gradient elements and attributes (no text, scripts, styles, links, images, foreign
objects, event handlers or external references) and checks the house style.
"""

from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET  # building/serialising only; parsing goes through defusedxml
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from defusedxml import ElementTree as SafeET

from factory.resources import ROOT
from factory.schemas.visual import AssetRecord

SVG_NS = "http://www.w3.org/2000/svg"
PALETTE_FILE = ROOT / "remotion" / "src" / "rig" / "palette.ts"
INK = "#2b2240"
MAX_BYTES = 60_000
MAX_ELEMENTS = 500

ALLOWED_TAGS = {
    "svg", "g", "path", "circle", "ellipse", "rect", "line", "polyline", "polygon",
    "defs", "linearGradient", "radialGradient", "stop", "clipPath",
}
ALLOWED_ATTRS = {
    "viewBox", "width", "height", "d", "cx", "cy", "r", "rx", "ry", "x", "y", "x1", "y1", "x2",
    "y2", "fx", "fy", "points", "fill", "stroke", "stroke-width", "stroke-linecap",
    "stroke-linejoin", "stroke-dasharray", "stroke-miterlimit", "opacity", "fill-opacity",
    "stroke-opacity", "fill-rule", "clip-rule", "transform", "id", "offset", "stop-color",
    "stop-opacity", "gradientUnits", "gradientTransform", "clip-path",
}
URL_ATTRS = {"fill", "stroke", "clip-path"}
_HEX = re.compile(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b")
_SAFE_VALUE = re.compile(r"^[\w\s#.,%()+\-:/]*$")


# ------------------------------------------------------------------ palette


@lru_cache(maxsize=1)
def palette() -> list[tuple[int, int, int]]:
    """House palette = the rig palette (single source of truth) plus pure white/black-ish ink."""
    hexes = set(_HEX.findall(PALETTE_FILE.read_text(encoding="utf-8"))) | {"#FFFFFF"}
    return [_rgb(h) for h in hexes]


def _rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _near_palette(h: str, tol: float = 70.0) -> bool:
    r, g, b = _rgb(h)
    return any(((r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2) ** 0.5 <= tol
               for pr, pg, pb in palette())


# ------------------------------------------------------------------ sanitizer


def _local(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def sanitize_svg(markup: str) -> tuple[str, list[str]]:
    """Return (clean svg, problems). Clean output contains only allowlisted elements/attrs.
    Problems are blocking (returned to the model for a retry)."""
    problems: list[str] = []
    text = markup.strip()
    if len(text.encode()) > MAX_BYTES:
        return "", [f"SVG is {len(text.encode())} bytes; keep it under {MAX_BYTES}."]
    if re.search(r"<!DOCTYPE|<!ENTITY|<\?xml-stylesheet", text, re.I):
        return "", ["No DOCTYPE, entities or stylesheets."]
    try:
        root = SafeET.fromstring(text)
    except (ET.ParseError, SafeET.ParseError, ValueError) as exc:
        return "", [f"SVG is not well-formed XML: {exc}"]
    if _local(root.tag) != "svg":
        return "", ["The root element must be <svg>."]
    if root.get("viewBox", "").split() != ["0", "0", "400", "400"]:
        problems.append('Use viewBox="0 0 400 400" exactly.')

    ids: set[str] = set()
    count = 0
    colors: list[str] = []
    has_ink_outline = False

    def clean(el: ET.Element) -> ET.Element | None:
        nonlocal count, has_ink_outline
        tag = _local(el.tag)
        if tag not in ALLOWED_TAGS:
            problems.append(f"<{tag}> is not allowed (shapes and gradients only; no text).")
            return None
        count += 1
        out = ET.Element(f"{{{SVG_NS}}}{tag}")
        for k, v in el.attrib.items():
            name = _local(k)
            if name not in ALLOWED_ATTRS:
                if name in {"style", "class", "href"} or name.startswith("on"):
                    problems.append(f"Attribute {name!r} is not allowed; use presentation "
                                    f"attributes (fill, stroke, ...).")
                continue
            if not _SAFE_VALUE.match(v):
                problems.append(f"Unsafe value in {name}.")
                continue
            if "url(" in v:
                ref = re.fullmatch(r"\s*url\(#([\w\-]+)\)\s*", v)
                if name not in URL_ATTRS or not ref:
                    problems.append(f"Only internal url(#id) references in fill/stroke/clip-path "
                                    f"({name}={v!r}).")
                    continue
            if name == "id":
                ids.add(v)
            if name in {"fill", "stroke", "stop-color"}:
                colors.extend(_HEX.findall(v))
                if name == "stroke" and v.lower() == INK:
                    has_ink_outline = True
            out.set(name, v)
        for child in el:
            c = clean(child)
            if c is not None:
                out.append(c)
        return out

    clean_root = clean(root)
    if clean_root is None:
        return "", problems
    clean_root.set("viewBox", "0 0 400 400")
    clean_root.attrib.pop("width", None)
    clean_root.attrib.pop("height", None)
    for el in clean_root.iter():
        for name in URL_ATTRS:
            m = re.fullmatch(r"\s*url\(#([\w\-]+)\)\s*", el.get(name, ""))
            if m and m.group(1) not in ids:
                problems.append(f"url(#{m.group(1)}) points to a missing id.")
    if count > MAX_ELEMENTS:
        problems.append(f"{count} elements; keep it under {MAX_ELEMENTS} (simpler shapes).")
    if count < 4:
        problems.append("Too simple: draw the object with several shapes and a shade.")
    if not has_ink_outline:
        problems.append(f'Outline the shapes with stroke="{INK.upper()}" (the house ink).')
    off = [c for c in colors if not _near_palette(c)]
    if colors and len(off) / len(colors) > 0.3:
        problems.append(f"Too many off-palette colours ({sorted(set(off))[:6]}); use the house "
                        f"palette.")
    ET.register_namespace("", SVG_NS)
    return ET.tostring(clean_root, encoding="unicode"), problems


# ------------------------------------------------------------------ library


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "prop"


def norm_name(text: str) -> str:
    return " ".join(sorted(set(re.findall(r"[a-z]+", text.lower())) - {"a", "an", "the", "of"}))


class AssetLibrary:
    def __init__(self, root: Path):
        self.root = Path(root) / "assets"
        self.index_file = self.root / "index.json"

    def records(self) -> list[AssetRecord]:
        if not self.index_file.exists():
            return []
        data = json.loads(self.index_file.read_text(encoding="utf-8"))
        return [AssetRecord(**r) for r in data]

    def get(self, asset_id: str) -> AssetRecord | None:
        return next((r for r in self.records() if r.asset_id == asset_id), None)

    def svg(self, asset_id: str) -> str:
        rec = self.get(asset_id)
        if rec is None:
            raise KeyError(asset_id)
        return (self.root.parent / rec.file).read_text(encoding="utf-8")

    def find(self, name: str) -> AssetRecord | None:
        """Reuse before generating: an asset with the same normalised name."""
        key = norm_name(name)
        return next((r for r in self.records() if norm_name(r.name) == key), None)

    def describe(self) -> str:
        recs = self.records()
        return "\n".join(f"- asset:{r.asset_id}: {r.name} (tags: {', '.join(r.tags)})"
                         for r in recs) or "(empty)"

    def add(self, name: str, tags: list[str], svg: str, generator: str, prompt: str,
            episode: str) -> AssetRecord:
        digest = hashlib.sha256(svg.encode()).hexdigest()
        records = self.records()
        same = next((r for r in records if r.sha256 == digest), None)
        if same:
            return same
        asset_id = f"{_slug(name)}-{digest[:8]}"
        path = self.root / "svg" / f"{asset_id}.svg"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(svg, encoding="utf-8", newline="\n")
        rec = AssetRecord(asset_id=asset_id, name=name, tags=tags,
                          file=path.relative_to(self.root.parent).as_posix(), sha256=digest,
                          created_at=datetime.now(UTC).isoformat(timespec="seconds"),
                          generator=generator,
                          prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
                          source_episode=episode)
        records.append(rec)
        self.index_file.write_text(json.dumps([r.model_dump() for r in records], indent=2),
                                   encoding="utf-8", newline="\n")
        return rec

    def index_sha256(self) -> str:
        return hashlib.sha256(self.index_file.read_bytes()).hexdigest() \
            if self.index_file.exists() else ""
