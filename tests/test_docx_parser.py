import docx_parser


def test_full_document_structure(sample_paragraphs):
    article = docx_parser.parse_paragraphs(sample_paragraphs)

    assert article.h1 == "Шумит ли рекуператор ночью"
    assert article.lead == ["Короткий лид-абзац о шуме рекуператора и спокойном сне."]
    assert article.conclusion == ["Современный рекуператор ночью практически не слышен."]
    assert article.cta == ["Подберите тихий рекуператор с нашим инженером."]


def test_docx_bytes_roundtrip(sample_docx_bytes):
    article = docx_parser.parse_docx_bytes(sample_docx_bytes)
    assert article.h1 == "Шумит ли рекуператор ночью"
    assert article.seo["slug"] == "face-zgomot-recuperatorul-noaptea"


def test_seo_block_mapping(sample_paragraphs):
    seo = docx_parser.parse_paragraphs(sample_paragraphs).seo
    assert seo["meta_title"] == "Шумит ли рекуператор ночью — разбор"
    assert seo["focus_keyword"] == "шум рекуператора"
    assert seo["secondary_keywords"] == ["тихий рекуператор", "рекуператор ночью"]
    assert seo["external_links"] == ["https://example.org/noise-standard"]
    assert seo["category"] == "Эксплуатация и сервис"
    assert seo["language"] == "ru"
    assert seo["date"] == "2026-07-XX"


def test_subheading_heuristic(sample_paragraphs):
    article = docx_parser.parse_paragraphs(sample_paragraphs)
    assert article.heading_candidates == ["Откуда берётся шум", "Как выбрать тихую модель"]
    body_texts = [i["text"] for i in article.body if not i["is_heading_candidate"]]
    assert "Вентилятор создаёт фоновый звук, который зависит от скорости." in body_texts


def test_warnings_for_placeholder_date_and_headings(sample_paragraphs):
    warnings = docx_parser.parse_paragraphs(sample_paragraphs).warnings
    codes = [w.code for w in warnings]
    assert "date_placeholder" in codes
    assert "subheadings_detected" in codes
    heading_warning = next(w for w in warnings if w.code == "subheadings_detected")
    assert heading_warning.rule_key == docx_parser.RULE_SUBHEADINGS


def test_images_parsed(sample_paragraphs):
    images = docx_parser.parse_paragraphs(sample_paragraphs).images
    assert len(images) == 1
    img = images[0]
    assert img.index == 1
    assert img.filename == "recuperator-noise-cover.jpg"
    assert img.ratio == "16:9"
    assert img.alt == "Рекуператор в спальне ночью"


def test_missing_seo_fields_warn():
    article = docx_parser.parse_paragraphs(["H1: Заголовок", "════", "Просто текст статьи."])
    codes = [w.code for w in article.warnings]
    assert "seo_missing:slug" in codes
    assert "seo_missing:meta_title" in codes


def test_unknown_seo_key_goes_to_extras():
    article = docx_parser.parse_paragraphs([
        "SEO-БЛОК:", "Slug: test", "Санта Барбара: да",
    ])
    assert article.seo["extras"]["Санта Барбара"] == "да"
    assert any(w.code == "seo_unknown_key" for w in article.warnings)
