"""Deterministic parser for structured article .docx files.

No AI here: source documents follow a strict layout (sections separated by
lines of ═, labelled blocks, key-value SEO block), so everything is parsed by
rules. Anything ambiguous becomes a warning the agent asks the user about.

Format nuance: the .docx carries no Word styles (subheadings are plain
paragraphs), so subheadings are detected heuristically — a short line with no
sentence-ending punctuation. Each detection is only a *candidate* until the
user confirms (see rules.py for the learning loop).
"""

from __future__ import annotations

import io
import re
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, asdict

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

SECTION_DIVIDER_RE = re.compile(r"^[═=]{4,}\s*$")
DATE_PLACEHOLDER_RE = re.compile(r"XX", re.IGNORECASE)
IMAGE_BLOCK_RE = re.compile(r"^\[Image\s+(\d+)\]", re.IGNORECASE)

# Section labels as they appear in the source documents (Russian editorial
# convention — the documents themselves are RU/RO content).
LABEL_H1 = "H1:"
LABEL_LEAD = "LID:"
LABEL_CONCLUSION = "ВЫВОД:"
LABEL_CTA = "CTA:"
LABEL_SEO = "SEO-БЛОК:"
LABEL_IMAGES = "ИЗОБРАЖЕНИЯ:"
ALL_LABELS = (LABEL_H1, LABEL_LEAD, LABEL_CONCLUSION, LABEL_CTA, LABEL_SEO, LABEL_IMAGES)

# SEO-block key → canonical field. Matched by lowercase prefix so minor
# wording drift ("Внутренние ссылки" vs "Внутренняя ссылка") still maps.
_SEO_KEY_PREFIXES = [
    ("meta title", "meta_title"),
    ("meta description", "meta_description"),
    ("slug", "slug"),
    ("основной ключ", "focus_keyword"),
    ("вторичные ключи", "secondary_keywords"),
    ("внутренн", "internal_links"),
    ("внешн", "external_links"),
    ("автор", "author"),
    ("дата", "date"),
    ("рубрика", "category"),
    ("формат", "format"),
    ("язык", "language"),
    ("зеркало", "mirror"),
]

_IMAGE_FIELD_PREFIXES = [
    ("тип", "type"),
    ("соотношение", "ratio"),
    ("имя файла", "filename"),
    ("промт", "prompt_en"),
    ("alt", "alt"),
    ("title", "title"),
    ("caption", "caption"),
]

_LANGUAGE_MAP = {
    "ru": "ru", "русский": "ru", "russian": "ru",
    "ro": "ro", "румынский": "ro", "romanian": "ro", "română": "ro",
    "en": "en", "английский": "en", "english": "en",
}

HEADING_MAX_LEN = 80
_SENTENCE_END = (".", "!", "?", ":", ";", ",", "…")

# Warning rule keys (rules.py learns on these; None = always ask)
RULE_SUBHEADINGS = "subheading_heuristic"


@dataclass
class ImageSpec:
    index: int = 0
    type: str = ""
    ratio: str = ""
    filename: str = ""
    prompt_en: str = ""
    alt: str = ""
    title: str = ""
    caption: str = ""


@dataclass
class ParseWarning:
    code: str
    message: str
    rule_key: str | None = None
    context: dict = field(default_factory=dict)


@dataclass
class Article:
    h1: str = ""
    lead: list[str] = field(default_factory=list)
    # body items: {"text": str, "is_heading_candidate": bool}
    body: list[dict] = field(default_factory=list)
    conclusion: list[str] = field(default_factory=list)
    cta: list[str] = field(default_factory=list)
    seo: dict = field(default_factory=dict)
    images: list[ImageSpec] = field(default_factory=list)
    warnings: list[ParseWarning] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def heading_candidates(self) -> list[str]:
        return [i["text"] for i in self.body if i["is_heading_candidate"]]


def paragraphs_from_docx_bytes(data: bytes) -> list[str]:
    """Extract paragraph texts from raw .docx bytes (stdlib only — a .docx is
    a zip whose word/document.xml holds w:p/w:t runs)."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        document = z.read("word/document.xml")
    root = ET.fromstring(document)
    paragraphs = []
    for p in root.iter(f"{_W}p"):
        text = "".join(t.text or "" for t in p.iter(f"{_W}t"))
        paragraphs.append(text.strip())
    return paragraphs


def parse_docx_bytes(data: bytes) -> Article:
    return parse_paragraphs(paragraphs_from_docx_bytes(data))


def parse_paragraphs(paragraphs: list[str]) -> Article:
    article = Article()
    for section in _split_sections(paragraphs):
        _consume_section(article, section)
    _emit_warnings(article)
    return article


# ─────────────────────────── internals ───────────────────────────


def _split_sections(paragraphs: list[str]) -> list[list[str]]:
    sections: list[list[str]] = [[]]
    for line in paragraphs:
        if SECTION_DIVIDER_RE.match(line):
            sections.append([])
        else:
            sections[-1].append(line)
    return [s for s in sections if any(line.strip() for line in s)]


def _section_label(section: list[str]) -> tuple[str | None, list[str]]:
    """Return (label, content lines). The label may sit on its own line or be
    inline with the first content ("H1: Заголовок")."""
    lines = [l for l in section]
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        for label in ALL_LABELS:
            if line.upper().startswith(label.upper()):
                inline_rest = line[len(label):].strip()
                content = ([inline_rest] if inline_rest else []) + lines[i + 1:]
                return label, content
        return None, lines[i:]
    return None, []


def _consume_section(article: Article, section: list[str]) -> None:
    label, content = _section_label(section)
    text_lines = [l.strip() for l in content if l.strip()]
    if label == LABEL_H1:
        article.h1 = " ".join(text_lines)
    elif label == LABEL_LEAD:
        article.lead = text_lines
    elif label == LABEL_CONCLUSION:
        article.conclusion = text_lines
    elif label == LABEL_CTA:
        article.cta = text_lines
    elif label == LABEL_SEO:
        article.seo = _parse_seo(text_lines, article)
    elif label == LABEL_IMAGES:
        article.images = _parse_images(text_lines)
    else:
        article.body.extend(
            {"text": line, "is_heading_candidate": _is_heading_candidate(line)}
            for line in text_lines
        )


def _is_heading_candidate(line: str) -> bool:
    return 0 < len(line) <= HEADING_MAX_LEN and not line.endswith(_SENTENCE_END)


def _parse_seo(lines: list[str], article: Article) -> dict:
    seo: dict = {}
    for line in lines:
        if ":" not in line:
            continue
        raw_key, _, raw_value = line.partition(":")
        key, value = raw_key.strip().lower(), raw_value.strip()
        canonical = next((c for prefix, c in _SEO_KEY_PREFIXES if key.startswith(prefix)), None)
        if canonical is None:
            article.warnings.append(ParseWarning(
                code="seo_unknown_key",
                message=f"Unknown SEO-block key: '{raw_key.strip()}' — value kept under extras.",
                context={"key": raw_key.strip(), "value": value},
            ))
            seo.setdefault("extras", {})[raw_key.strip()] = value
        elif canonical in ("secondary_keywords", "internal_links", "external_links"):
            seo[canonical] = [v.strip() for v in value.split(",") if v.strip()]
        elif canonical == "language":
            seo[canonical] = _LANGUAGE_MAP.get(value.strip().lower(), value.strip().lower()[:2])
        else:
            seo[canonical] = value
    return seo


def _parse_images(lines: list[str]) -> list[ImageSpec]:
    images: list[ImageSpec] = []
    current: ImageSpec | None = None
    for line in lines:
        block = IMAGE_BLOCK_RE.match(line)
        if block:
            current = ImageSpec(index=int(block.group(1)))
            images.append(current)
            continue
        if current is None or ":" not in line:
            continue
        raw_key, _, raw_value = line.partition(":")
        key = raw_key.strip().lower()
        canonical = next((c for prefix, c in _IMAGE_FIELD_PREFIXES if key.startswith(prefix)), None)
        if canonical:
            setattr(current, canonical, raw_value.strip())
    return images


def _emit_warnings(article: Article) -> None:
    date = article.seo.get("date", "")
    if date and DATE_PLACEHOLDER_RE.search(date):
        article.warnings.append(ParseWarning(
            code="date_placeholder",
            message=f"Publication date is a placeholder ('{date}') — ask the user for the real date.",
            context={"date": date},
        ))
    candidates = article.heading_candidates
    if candidates:
        article.warnings.append(ParseWarning(
            code="subheadings_detected",
            message=(
                "Detected subheadings by heuristic (short line, no trailing punctuation) — "
                "confirm before publishing: " + "; ".join(candidates)
            ),
            rule_key=RULE_SUBHEADINGS,
            context={"headings": candidates},
        ))
    for required in ("slug", "meta_title", "meta_description", "category", "language"):
        if not article.seo.get(required):
            article.warnings.append(ParseWarning(
                code=f"seo_missing:{required}",
                message=f"SEO block is missing '{required}'.",
                context={"field": required},
            ))
    if not article.h1:
        article.warnings.append(ParseWarning(
            code="h1_missing",
            message="No H1 section found in the document.",
        ))
