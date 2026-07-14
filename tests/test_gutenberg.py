import docx_parser
import gutenberg


def test_headings_confirmed_render_h2(sample_paragraphs):
    article = docx_parser.parse_paragraphs(sample_paragraphs).to_dict()
    content = gutenberg.article_to_content(article, headings_confirmed=True)
    assert '<h2 class="wp-block-heading">Откуда берётся шум</h2>' in content
    assert "<!-- wp:heading" in content
    # H1 never enters the content — it is the post title
    assert "Шумит ли рекуператор ночью" not in content


def test_headings_rejected_render_paragraphs(sample_paragraphs):
    article = docx_parser.parse_paragraphs(sample_paragraphs).to_dict()
    content = gutenberg.article_to_content(article, headings_confirmed=False)
    assert "<h2" not in content
    assert "<p>Откуда берётся шум</p>" in content


def test_html_is_escaped():
    block = gutenberg.paragraph_block('Текст с <b>тегами</b> & "кавычками"')
    assert "<b>" not in block
    assert "&lt;b&gt;" in block
