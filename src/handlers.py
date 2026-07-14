"""Chat functions: parse_article, confirm_mapping, publish_draft, list_articles."""

from __future__ import annotations

import base64
from datetime import datetime, timezone

from imperal_sdk import ActionResult

import docx_parser
import gutenberg
import rules
import wp_client
from app import chat
from models import (
    ArticleList,
    ArticleRecord,
    ConfirmMappingParams,
    ListArticlesParams,
    ParseArticleParams,
    ParseReport,
    PublishDraftParams,
    RuleRecord,
)

ARTICLES_COLLECTION = "articles"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug_fallback(filename: str) -> str:
    stem = filename.rsplit(".", 1)[0].lower()
    return "".join(c if c.isalnum() else "-" for c in stem).strip("-")


async def _find_article_doc(ctx, slug: str):
    page = await ctx.store.query(ARTICLES_COLLECTION, limit=100)
    return next((d for d in page.data if d.data.get("id") == slug), None)


async def ingest_document(ctx, data: bytes, filename: str) -> dict:
    """Shared parse-and-store path used by the chat function and the panel.

    Warnings whose rule is already in auto mode are dropped before storing —
    the user has taught the parser to trust them.
    """
    article = docx_parser.parse_docx_bytes(data)
    active_warnings = []
    for w in article.warnings:
        if w.rule_key and await rules.is_auto(ctx, w.rule_key):
            continue
        active_warnings.append({"code": w.code, "message": w.message,
                                "rule_key": w.rule_key, "context": w.context})

    slug = article.seo.get("slug") or _slug_fallback(filename)
    record = {
        "id": slug,
        "filename": filename,
        "article": article.to_dict(),
        "warnings": active_warnings,
        "status": "parsed",
        "wp_post_id": None,
        "wp_link": "",
        "parsed_at": _now_iso(),
    }
    existing = await _find_article_doc(ctx, slug)
    if existing:
        await ctx.store.update(ARTICLES_COLLECTION, existing.id, record)
    else:
        await ctx.store.create(ARTICLES_COLLECTION, record)
    return record


@chat.function(
    "parse_article",
    action_type="read",
    description="Parse a structured .docx article into title, body, SEO fields and images, reporting anything that needs a human answer.",
    data_model=ParseReport,
)
async def parse_article(ctx, params: ParseArticleParams) -> ActionResult:
    """Deterministically parse a .docx article and store the result."""
    if params.file_b64:
        try:
            data = base64.b64decode(params.file_b64)
        except Exception:
            return ActionResult.error("file_b64 is not valid base64.")
    elif params.storage_path:
        try:
            data = await ctx.storage.download(params.storage_path)
        except Exception:
            return ActionResult.error(f"Could not read '{params.storage_path}' from storage.")
    else:
        return ActionResult.error("Provide either file_b64 or storage_path.")

    try:
        record = await ingest_document(ctx, data, params.filename)
    except Exception:
        return ActionResult.error("Not a readable .docx file.")

    article = record["article"]
    warnings = [w["message"] for w in record["warnings"]]
    report = ParseReport(
        id=record["id"],
        title=article["h1"] or params.filename,
        slug=record["id"],
        language=article["seo"].get("language", ""),
        category=article["seo"].get("category", ""),
        heading_candidates=[i["text"] for i in article["body"] if i["is_heading_candidate"]],
        warnings=warnings,
    )
    summary = f"Parsed '{article['h1'] or params.filename}'"
    summary += f" — {len(warnings)} question(s) need answers." if warnings else " — no questions, ready to publish."
    return ActionResult.success(report, summary=summary)


@chat.function(
    "confirm_mapping",
    action_type="write",
    event="rule_confirmed",
    effects=["update:rule"],
    description="Record the user's confirmation (or rejection) of a parsing rule; after 3 confirmations the rule goes auto and the question disappears.",
    data_model=RuleRecord,
)
async def confirm_mapping(ctx, params: ConfirmMappingParams) -> ActionResult:
    """Persist one user decision about a parsing rule."""
    state = await rules.confirm(ctx, params.rule_key, params.accepted)
    record = RuleRecord(
        id=params.rule_key,
        title=params.rule_key,
        rule_key=params.rule_key,
        confirmations=state["confirmations"],
        auto=state["auto"],
    )
    if state["auto"]:
        summary = f"Rule '{params.rule_key}' is now automatic — no more questions about it."
    else:
        summary = (f"Recorded. Rule '{params.rule_key}': "
                   f"{state['confirmations']}/{rules.AUTO_THRESHOLD} confirmations toward auto mode.")
    return ActionResult.success(record, summary=summary)


@chat.function(
    "publish_draft",
    action_type="write",
    event="draft_created",
    effects=["create:post"],
    description="Create a WordPress draft from a parsed article: Gutenberg content, Rank Math SEO meta, Polylang language, category.",
    data_model=ArticleRecord,
)
async def publish_draft(ctx, params: PublishDraftParams) -> ActionResult:
    """Publish a previously parsed article to WordPress as a draft."""
    doc = await _find_article_doc(ctx, params.slug)
    if doc is None:
        return ActionResult.error(f"No parsed article with slug '{params.slug}'. Run parse_article first.")
    record = doc.data
    article = record["article"]
    seo = article["seo"]

    # Unresolved questions block publishing
    date = seo.get("date", "")
    if docx_parser.DATE_PLACEHOLDER_RE.search(date) and not params.resolved_date:
        return ActionResult.error(
            f"The document's date is a placeholder ('{date}') — pass resolved_date (YYYY-MM-DD).")
    publish_date = params.resolved_date or (date or None)

    has_candidates = any(i["is_heading_candidate"] for i in article["body"])
    headings_confirmed = params.headings_confirmed
    if has_candidates and headings_confirmed is None:
        if await rules.is_auto(ctx, docx_parser.RULE_SUBHEADINGS):
            headings_confirmed = True
        else:
            return ActionResult.error(
                "Subheadings were detected heuristically — ask the user and pass headings_confirmed.")
    if has_candidates and params.headings_confirmed is not None:
        # An explicit decision is also a training signal for the heuristic
        await rules.confirm(ctx, docx_parser.RULE_SUBHEADINGS, params.headings_confirmed)

    base_url = await ctx.secrets.get("wp_base_url")
    username = await ctx.secrets.get("wp_user")
    app_password = await ctx.secrets.get("wp_app_password")
    if not all([base_url, username, app_password]):
        return ActionResult.error(
            "WordPress credentials are not configured — set wp_base_url, wp_user and wp_app_password in the extension's Secrets tab.")
    try:
        base_url = wp_client.normalize_base_url(base_url)
    except ValueError as e:
        return ActionResult.error(str(e))
    headers = wp_client.basic_auth_header(username, app_password)

    lang = seo.get("language") or None
    category_note = ""
    category_id = None
    if seo.get("category"):
        category_id = await wp_client.find_category_id(ctx, base_url, headers, seo["category"], lang=lang)
        if category_id is None:
            category_note = f" Category '{seo['category']}' was not found on the site — draft created without it."

    content = gutenberg.article_to_content(article, headings_confirmed=bool(headings_confirmed))
    meta = {
        "rank_math_title": seo.get("meta_title", ""),
        "rank_math_description": seo.get("meta_description", ""),
        "rank_math_focus_keyword": seo.get("focus_keyword", ""),
    }
    result = await wp_client.create_draft(
        ctx, base_url, headers,
        title=article["h1"], slug=params.slug, content=content,
        meta=meta, category_id=category_id, lang=lang, date=publish_date,
    )
    if not result["ok"]:
        return ActionResult.error(result["error"], retryable=True)

    post = result["post"]
    record.update(status="published", wp_post_id=post.get("id"),
                  wp_link=post.get("link", ""), warnings=[])
    await ctx.store.update(ARTICLES_COLLECTION, doc.id, record)

    out = ArticleRecord(
        id=params.slug, title=article["h1"], slug=params.slug,
        language=lang or "", category=seo.get("category", ""),
        wp_post_id=post.get("id"), wp_link=post.get("link", ""), status="published",
    )
    return ActionResult.success(
        out, summary=f"Draft created: {post.get('link', post.get('id'))}.{category_note}")


@chat.function(
    "list_articles",
    action_type="read",
    description="List parsed and published articles with their statuses.",
    data_model=ArticleList,
)
async def list_articles(ctx, params: ListArticlesParams) -> ActionResult:
    """List articles known to WP Publisher."""
    page = await ctx.store.query(ARTICLES_COLLECTION, limit=100)
    items = []
    for d in page.data:
        r = d.data
        if params.status and r.get("status") != params.status:
            continue
        items.append(ArticleRecord(
            id=r["id"], title=r["article"]["h1"] or r["filename"], slug=r["id"],
            language=r["article"]["seo"].get("language", ""),
            category=r["article"]["seo"].get("category", ""),
            warnings_count=len(r.get("warnings", [])),
            wp_post_id=r.get("wp_post_id"), wp_link=r.get("wp_link", ""),
            status=r.get("status", ""),
        ))
    return ActionResult.success(
        ArticleList(items=items, total=len(items), has_more=False),
        summary=f"{len(items)} article(s).")
