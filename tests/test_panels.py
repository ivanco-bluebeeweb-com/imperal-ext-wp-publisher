import base64

import pytest

import handlers
import panels
from conftest import make_docx_bytes, SAMPLE_PARAGRAPHS


async def test_panel_renders_empty_state(ctx):
    node = await panels.publications(ctx)
    assert node is not None


async def test_panel_ingests_upload(ctx):
    b64 = base64.b64encode(make_docx_bytes(SAMPLE_PARAGRAPHS)).decode()
    node = await panels.publications(ctx, files=[{"name": "article.docx", "data": b64}])
    assert node is not None
    page = await ctx.store.query(handlers.ARTICLES_COLLECTION, limit=10)
    assert len(page.data) == 1
    assert page.data[0].data["id"] == "face-zgomot-recuperatorul-noaptea"


def test_decode_upload_tolerates_shapes():
    b64 = base64.b64encode(b"hello").decode()
    assert panels._decode_upload(b64) == [("article.docx", b"hello")]
    assert panels._decode_upload({"name": "x.docx", "data": b64}) == [("x.docx", b"hello")]
    assert panels._decode_upload([f"data:application/octet-stream;base64,{b64}"]) == [
        ("article.docx", b"hello")]


def test_decode_upload_raises_on_unknown_shape():
    with pytest.raises(ValueError, match="no base64 payload found"):
        panels._decode_upload({"name": "x.docx", "url": "https://example.com/x.docx"})


async def test_panel_reports_upload_error_instead_of_silently_dropping(ctx):
    node = await panels.publications(ctx, files=[{"name": "x.docx", "url": "https://example.com/x.docx"}])
    alert = node.props["children"][1]
    assert alert.type == "Alert"
    assert "no base64 payload found" in alert.props["message"]
