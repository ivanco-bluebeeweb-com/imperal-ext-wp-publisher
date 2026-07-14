import base64

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
