import base64

import handlers
import rules
from models import (
    ConfirmMappingParams,
    ListArticlesParams,
    ParseArticleParams,
    PublishDraftParams,
)

SLUG = "face-zgomot-recuperatorul-noaptea"


async def _parse(ctx, sample_docx_bytes):
    params = ParseArticleParams(
        filename="article.docx",
        file_b64=base64.b64encode(sample_docx_bytes).decode(),
    )
    return await handlers.parse_article(ctx, params)


def _configure_wp(ctx):
    ctx.http.mock_get(
        "https://climtec.md/wp-json/wp/v2/categories",
        [{"id": 7, "name": "Эксплуатация и сервис"}], 200)
    ctx.http.mock_post(
        "https://climtec.md/wp-json/wp/v2/posts",
        {"id": 123, "link": f"https://climtec.md/?p=123"}, 201)


async def _set_secrets(ctx):
    await ctx.secrets.set("wp_base_url", "https://climtec.md")
    await ctx.secrets.set("wp_user", "editor")
    await ctx.secrets.set("wp_app_password", "abcd efgh")


async def test_parse_article_reports_warnings(ctx, sample_docx_bytes):
    result = await _parse(ctx, sample_docx_bytes)
    assert result.status == "success"
    assert result.data.slug == SLUG
    assert result.data.language == "ru"
    assert len(result.data.warnings) == 2  # placeholder date + subheadings
    assert result.data.heading_candidates == ["Откуда берётся шум", "Как выбрать тихую модель"]


async def test_parse_article_requires_source(ctx):
    result = await handlers.parse_article(ctx, ParseArticleParams(filename="a.docx"))
    assert result.status == "error"


async def test_confirm_mapping_learns(ctx):
    for _ in range(3):
        result = await handlers.confirm_mapping(
            ctx, ConfirmMappingParams(rule_key="subheading_heuristic", accepted=True))
    assert result.status == "success"
    assert result.data.auto is True


async def test_publish_blocked_by_placeholder_date(ctx, sample_docx_bytes):
    await _parse(ctx, sample_docx_bytes)
    result = await handlers.publish_draft(ctx, PublishDraftParams(slug=SLUG))
    assert result.status == "error"
    assert "resolved_date" in result.error


async def test_publish_blocked_without_heading_decision(ctx, sample_docx_bytes):
    await _parse(ctx, sample_docx_bytes)
    result = await handlers.publish_draft(
        ctx, PublishDraftParams(slug=SLUG, resolved_date="2026-07-20"))
    assert result.status == "error"
    assert "headings_confirmed" in result.error


async def test_publish_happy_path(ctx, sample_docx_bytes):
    await _parse(ctx, sample_docx_bytes)
    await _set_secrets(ctx)
    _configure_wp(ctx)
    result = await handlers.publish_draft(ctx, PublishDraftParams(
        slug=SLUG, resolved_date="2026-07-20", headings_confirmed=True))
    assert result.status == "success", result.error
    assert result.data.wp_post_id == 123
    # an explicit heading decision is recorded as a training signal
    rule = await rules.get_rule(ctx, "subheading_heuristic")
    assert rule["confirmations"] == 1


async def test_publish_auto_headings_after_training(ctx, sample_docx_bytes):
    await _parse(ctx, sample_docx_bytes)
    await _set_secrets(ctx)
    _configure_wp(ctx)
    for _ in range(3):
        await rules.confirm(ctx, "subheading_heuristic", True)
    result = await handlers.publish_draft(ctx, PublishDraftParams(
        slug=SLUG, resolved_date="2026-07-20"))
    assert result.status == "success", result.error


async def test_publish_reports_network_failure_instead_of_crashing(ctx, sample_docx_bytes):
    await _parse(ctx, sample_docx_bytes)
    await _set_secrets(ctx)

    async def _raise_post(url, **kwargs):
        raise ConnectionError("Connection refused")
    ctx.http.post = _raise_post

    result = await handlers.publish_draft(ctx, PublishDraftParams(
        slug=SLUG, resolved_date="2026-07-20", headings_confirmed=True))
    assert result.status == "error"
    assert "climtec.md" in result.error


async def test_publish_reports_non_json_response_instead_of_crashing(ctx, sample_docx_bytes):
    # A 2xx status with a body that isn't valid JSON — e.g. a PHP warning/notice
    # printed before the REST API output — must not raise json.JSONDecodeError.
    from imperal_sdk.types.models import HTTPResponse

    await _parse(ctx, sample_docx_bytes)
    await _set_secrets(ctx)

    async def _garbled_post(url, **kwargs):
        return HTTPResponse(status_code=201, body="<b>Warning</b>{\"id\":123}", headers={})
    ctx.http.post = _garbled_post

    result = await handlers.publish_draft(ctx, PublishDraftParams(
        slug=SLUG, resolved_date="2026-07-20", headings_confirmed=True))
    assert result.status == "error"
    assert "valid JSON" in result.error


async def test_publish_succeeds_even_if_local_bookkeeping_fails(ctx, sample_docx_bytes):
    # The WordPress draft is already created by this point — a failure saving
    # our own record afterward must not be reported as a publish failure.
    await _parse(ctx, sample_docx_bytes)
    await _set_secrets(ctx)
    _configure_wp(ctx)

    async def _raise_update(*args, **kwargs):
        raise RuntimeError("store unavailable")
    ctx.store.update = _raise_update

    result = await handlers.publish_draft(ctx, PublishDraftParams(
        slug=SLUG, resolved_date="2026-07-20", headings_confirmed=True))
    assert result.status == "success", result.error
    assert result.data.wp_post_id == 123


async def test_publish_requires_credentials(ctx, sample_docx_bytes):
    await _parse(ctx, sample_docx_bytes)
    result = await handlers.publish_draft(ctx, PublishDraftParams(
        slug=SLUG, resolved_date="2026-07-20", headings_confirmed=True))
    assert result.status == "error"
    assert "Secrets" in result.error


async def test_list_articles(ctx, sample_docx_bytes):
    await _parse(ctx, sample_docx_bytes)
    result = await handlers.list_articles(ctx, ListArticlesParams())
    assert result.status == "success"
    assert result.data.total == 1
    assert result.data.items[0].slug == SLUG
    assert result.data.items[0].warnings_count == 2
    assert len(result.data.items[0].warnings) == 2
    assert any("placeholder" in w for w in result.data.items[0].warnings)
