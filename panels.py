"""Publications panel: upload a .docx, see every article and its status."""

from __future__ import annotations

import base64

from imperal_sdk import ui

import handlers
from app import ext

# SKETCH — publications panel (each component verified against PRE-PANEL CHECKLIST)
# ui.Stack (v, gap=4)
#   ui.Header(text="WP Publisher", level=2, subtitle=...)
#   ui.Alert(...)                                  — only after an upload attempt
#   ui.Section(title="Upload article", children=[  — children REQUIRED
#     ui.FileUpload(accept=".docx", param_name="files",
#                   on_upload=ui.Call("__panel__publications"))  — b64 merged into kwargs["files"]
#     ui.Text(variant="caption")
#   ])
#   ui.Section(title="Articles", children=[
#     ui.DataTable(columns=[DataColumn dicts], rows=[plain dicts])  — DataColumn returns dict
#     | ui.Empty(message=...)                      — never return None
#   ])


def _decode_upload(files) -> list[tuple[str, bytes]]:
    """The panel host merges base64 file data under param_name; the exact shape
    (str / dict / list) is host-version dependent, so accept all of them.

    Raises ValueError with the entry's shape (type + keys) when no known key
    holds the payload — that description is surfaced to the user instead of a
    silently-skipped upload, since the exact host shape can't be verified
    ahead of time from this codebase alone."""
    entries = files if isinstance(files, list) else [files]
    out: list[tuple[str, bytes]] = []
    for entry in entries:
        if isinstance(entry, dict):
            name = entry.get("name") or entry.get("filename") or "article.docx"
            b64 = (entry.get("data_base64") or entry.get("data") or entry.get("content")
                   or entry.get("b64") or entry.get("base64") or entry.get("file") or "")
        elif isinstance(entry, str):
            name, b64 = "article.docx", entry
        else:
            raise ValueError(f"unrecognized upload entry type: {type(entry).__name__}")
        if "," in b64 and b64.lstrip().startswith("data:"):
            b64 = b64.split(",", 1)[1]
        if not b64:
            keys = sorted(entry.keys()) if isinstance(entry, dict) else None
            raise ValueError(f"no base64 payload found (entry type={type(entry).__name__}, keys={keys})")
        out.append((name, base64.b64decode(b64)))
    return out


@ext.panel("publications", slot="center", title="Publications", icon="Newspaper",
           center_overlay=True, refresh="manual")
async def publications(ctx, **kwargs):
    """Render the publications overview; also handles .docx uploads."""
    alert = None
    if kwargs.get("files"):
        parsed, errors = 0, []
        try:
            decoded = _decode_upload(kwargs["files"])
        except Exception as e:
            decoded, errors = [], [f"{type(e).__name__}: {e}"]
        for name, data in decoded:
            try:
                await handlers.ingest_document(ctx, data, name)
                parsed += 1
            except Exception as e:
                errors.append(f"{name}: {type(e).__name__}: {e}")
        if parsed and not errors:
            alert = ui.Alert(message=f"Parsed {parsed} document(s).", type="success")
        elif errors:
            alert = ui.Alert(
                message=f"Parsed {parsed}, failed {len(errors)} — " + "; ".join(errors),
                type="error" if not parsed else "warn")

    page = await ctx.store.query(handlers.ARTICLES_COLLECTION, limit=100)
    rows = []
    for d in page.data:
        r = d.data
        rows.append({
            "title": r["article"]["h1"] or r["filename"],
            "slug": r["id"],
            "language": r["article"]["seo"].get("language", ""),
            "category": r["article"]["seo"].get("category", ""),
            "status": r.get("status", ""),
            "questions": len(r.get("warnings", [])),
            "link": r.get("wp_link", ""),
        })

    columns = [
        ui.DataColumn(key="title", label="Title"),
        ui.DataColumn(key="slug", label="Slug"),
        ui.DataColumn(key="language", label="Lang", width="60px"),
        ui.DataColumn(key="category", label="Category"),
        ui.DataColumn(key="status", label="Status", width="100px"),
        ui.DataColumn(key="questions", label="Questions", width="90px"),
        ui.DataColumn(key="link", label="WP link"),
    ]
    articles_block = (
        ui.DataTable(columns=columns, rows=rows)
        if rows else
        ui.Empty(message="No articles yet — upload a .docx above.")
    )

    children = [
        ui.Header(text="WP Publisher", level=2,
                  subtitle="Structured .docx → WordPress draft with SEO fields"),
    ]
    if alert:
        children.append(alert)
    children += [
        ui.Section(title="Upload article", children=[
            ui.FileUpload(accept=".docx", max_size_mb=10, param_name="files",
                          on_upload=ui.Call("__panel__publications")),
            ui.Text(content="The document is parsed deterministically; open the chat to answer any questions and publish.",
                    variant="caption"),
        ]),
        ui.Section(title="Articles", children=[articles_block]),
    ]
    return ui.Stack(children=children, gap=4)
