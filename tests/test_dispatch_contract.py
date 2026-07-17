"""The platform dispatch boundary runs validate_against(data_model) on every
result. An error result carrying data={} fails Entity validation (id/title
required) — documented as "warn-only in v5.0.1; hard fail post-soak" — so
every error our handlers return must carry data=None, the only value
validate_against skips.
"""

import base64

import handlers
from models import ArticleRecord, ParseArticleParams, ParseReport, PublishDraftParams


async def test_error_results_carry_none_data(ctx, sample_docx_bytes):
    # parse_article error path
    result = await handlers.parse_article(ctx, ParseArticleParams(filename="a.docx"))
    assert result.status == "error"
    assert result.data is None
    assert result.validate_against(ParseReport) is result

    # publish_draft error path (placeholder date blocks publishing)
    await handlers.parse_article(ctx, ParseArticleParams(
        filename="article.docx",
        file_b64=base64.b64encode(sample_docx_bytes).decode()))
    result = await handlers.publish_draft(
        ctx, PublishDraftParams(slug="face-zgomot-recuperatorul-noaptea"))
    assert result.status == "error"
    assert result.data is None
    assert result.validate_against(ArticleRecord) is result


async def test_crash_wrapper_error_carries_none_data(ctx, sample_docx_bytes):
    await handlers.parse_article(ctx, ParseArticleParams(
        filename="article.docx",
        file_b64=base64.b64encode(sample_docx_bytes).decode()))

    async def _raise(key):
        raise RuntimeError("boom")
    ctx.secrets.get = _raise

    result = await handlers.publish_draft(ctx, PublishDraftParams(
        slug="face-zgomot-recuperatorul-noaptea",
        resolved_date="2026-07-20", headings_confirmed=True))
    assert result.status == "error"
    assert result.data is None


async def test_success_results_pass_boundary_validation(ctx, sample_docx_bytes):
    result = await handlers.parse_article(ctx, ParseArticleParams(
        filename="article.docx",
        file_b64=base64.b64encode(sample_docx_bytes).decode()))
    assert result.status == "success"
    assert result.validate_against(ParseReport) is result
