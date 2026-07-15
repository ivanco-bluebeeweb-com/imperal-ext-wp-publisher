"""WordPress REST helpers: draft creation with Rank Math meta and Polylang
language. Requires the WP Publisher Bridge plugin on the site — without it
WordPress silently ignores the rank_math_* meta fields.
"""

from __future__ import annotations

import base64
from urllib.parse import urlparse

_ERROR_MESSAGES = {
    401: "WordPress rejected the credentials — create a fresh Application Password.",
    403: "That WordPress user lacks permission for this request.",
    404: "WordPress REST API not found — is the REST API enabled?",
    429: "WordPress is rate-limiting requests — try again shortly.",
}


def basic_auth_header(username: str, app_password: str) -> dict:
    token = base64.b64encode(f"{username}:{app_password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def normalize_base_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme != "https":
        raise ValueError("Site URL must use https://")
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def wp_error_message(status_code: int) -> str:
    if status_code in _ERROR_MESSAGES:
        return _ERROR_MESSAGES[status_code]
    if 500 <= status_code < 600:
        return "WordPress returned a server error — try again shortly."
    return f"WordPress request failed (HTTP {status_code})."


async def find_category_id(ctx, base_url: str, headers: dict, name: str,
                           lang: str | None = None) -> int | None:
    """Resolve a category name to its term id (case-insensitive exact match).

    Unreachable site / network errors are treated the same as "not found" —
    the caller already falls back to publishing without a category."""
    params = {"search": name, "per_page": 100}
    if lang:
        params["lang"] = lang
    try:
        resp = await ctx.http.get(f"{base_url}/wp-json/wp/v2/categories",
                                  headers=headers, params=params)
    except Exception:
        return None
    if resp.status_code >= 400 or not isinstance(resp.body, list):
        return None
    wanted = name.strip().lower()
    for term in resp.body:
        if str(term.get("name", "")).strip().lower() == wanted:
            return term.get("id")
    return None


async def create_draft(ctx, base_url: str, headers: dict, *, title: str, slug: str,
                       content: str, meta: dict, category_id: int | None = None,
                       lang: str | None = None, date: str | None = None) -> dict:
    """Create a draft post. Returns {"ok", "post" | "error"}."""
    payload: dict = {
        "title": title,
        "slug": slug,
        "content": content,
        "status": "draft",
        "meta": meta,
    }
    if category_id:
        payload["categories"] = [category_id]
    if date:
        payload["date"] = date if "T" in date else f"{date}T10:00:00"
    url = f"{base_url}/wp-json/wp/v2/posts"
    if lang:
        # Polylang reads the language from the query string on create
        url = f"{url}?lang={lang}"
    try:
        resp = await ctx.http.post(url, headers=headers, json=payload)
    except Exception as e:
        return {"ok": False, "error": f"Could not reach WordPress at {base_url} ({type(e).__name__}: {e})."}
    if resp.status_code >= 400:
        return {"ok": False, "error": wp_error_message(resp.status_code)}
    try:
        post = resp.json() if not isinstance(resp.body, dict) else resp.body
    except Exception:
        return {"ok": False, "error": (
            "WordPress returned a 2xx status but the response body wasn't valid JSON — "
            "a plugin or theme is likely printing a PHP warning/notice before the REST "
            "API output. Check the site's PHP error log.")}
    if not isinstance(post, dict):
        return {"ok": False, "error": "WordPress returned an unexpected response shape for the created post."}
    return {"ok": True, "post": post}


async def ping(ctx, base_url: str, headers: dict) -> bool:
    """Cheap reachability probe of the WP REST API."""
    resp = await ctx.http.get(f"{base_url}/wp-json/wp/v2/categories",
                              headers=headers, params={"per_page": 1})
    return resp.status_code < 400
