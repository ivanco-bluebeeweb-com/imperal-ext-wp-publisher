"""Article structure → Gutenberg block markup.

The H1 never enters the content — it is the post title and the theme renders
it. Everything else becomes standard core blocks (paragraph / heading level 2).
"""

from __future__ import annotations

import html


def paragraph_block(text: str) -> str:
    return f"<!-- wp:paragraph --><p>{html.escape(text)}</p><!-- /wp:paragraph -->"


def heading_block(text: str, level: int = 2) -> str:
    escaped = html.escape(text)
    return (
        f'<!-- wp:heading {{"level":{level}}} -->'
        f'<h{level} class="wp-block-heading">{escaped}</h{level}>'
        f"<!-- /wp:heading -->"
    )


def article_to_content(article: dict, *, headings_confirmed: bool) -> str:
    """Render the parsed article dict (Article.to_dict()) into post_content.

    headings_confirmed=False renders heading *candidates* as plain paragraphs —
    used when the user rejected the subheading heuristic for this document.
    """
    blocks: list[str] = []
    for line in article.get("lead", []):
        blocks.append(paragraph_block(line))
    for item in article.get("body", []):
        if headings_confirmed and item.get("is_heading_candidate"):
            blocks.append(heading_block(item["text"]))
        else:
            blocks.append(paragraph_block(item["text"]))
    for line in article.get("conclusion", []):
        blocks.append(paragraph_block(line))
    for line in article.get("cta", []):
        blocks.append(paragraph_block(line))
    return "\n".join(blocks)
