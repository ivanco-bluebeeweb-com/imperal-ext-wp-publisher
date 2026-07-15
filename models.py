"""Pydantic parameter models and SDL return entities."""

from pydantic import BaseModel, Field
from imperal_sdk import sdl


# ─────────── parameters ───────────

class ParseArticleParams(BaseModel):
    filename: str = Field(description="Original .docx file name, e.g. 'article.docx'")
    file_b64: str | None = Field(
        None, description="Base64-encoded .docx content (use when the file came through chat/panel)")
    storage_path: str | None = Field(
        None, description="ctx.storage path of an already-uploaded .docx (alternative to file_b64)")


class ConfirmMappingParams(BaseModel):
    rule_key: str = Field(description="Rule being confirmed, e.g. 'subheading_heuristic'")
    accepted: bool = Field(True, description="True if the user confirmed the rule, False if rejected")


class PublishDraftParams(BaseModel):
    slug: str = Field(description="Slug of a previously parsed article to publish")
    resolved_date: str | None = Field(
        None, description="Real publication date (YYYY-MM-DD) when the document had a placeholder like 2026-07-XX")
    headings_confirmed: bool | None = Field(
        None, description="User's decision on the detected subheadings; omit if the rule is already in auto mode")


class ListArticlesParams(BaseModel):
    status: str | None = Field(None, description="Filter by status: 'parsed' or 'published'")


# ─────────── SDL return entities ───────────

class ArticleRecord(sdl.Entity):
    """One parsed or published article."""
    slug: str = ""
    language: str = ""
    category: str = ""
    warnings_count: int = 0
    wp_post_id: int | None = None
    wp_link: str = ""


class ArticleList(sdl.EntityList[ArticleRecord]):
    pass


class ParseReport(sdl.Entity):
    """Result of parsing one document: what was found and what needs a human answer."""
    slug: str = ""
    language: str = ""
    category: str = ""
    heading_candidates: list[str] = []
    warnings: list[str] = []


class RuleRecord(sdl.Entity):
    """State of one learned parsing rule."""
    rule_key: str = ""
    confirmations: int = 0
    auto: bool = False
