import io
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


SAMPLE_PARAGRAPHS = [
    "H1: Шумит ли рекуператор ночью",
    "════════════════",
    "LID:",
    "Короткий лид-абзац о шуме рекуператора и спокойном сне.",
    "════════════════",
    "Откуда берётся шум",
    "Вентилятор создаёт фоновый звук, который зависит от скорости.",
    "На малых скоростях уровень сравним с шелестом листвы.",
    "Как выбрать тихую модель",
    "Смотрите на уровень шума в паспорте устройства.",
    "════════════════",
    "ВЫВОД:",
    "Современный рекуператор ночью практически не слышен.",
    "════════════════",
    "CTA:",
    "Подберите тихий рекуператор с нашим инженером.",
    "════════════════",
    "SEO-БЛОК:",
    "Meta Title: Шумит ли рекуператор ночью — разбор",
    "Meta Description: Разбираемся, шумит ли рекуператор ночью и как выбрать тихую модель.",
    "Slug: face-zgomot-recuperatorul-noaptea",
    "Основной ключ: шум рекуператора",
    "Вторичные ключи: тихий рекуператор, рекуператор ночью",
    "Внешняя ссылка: https://example.org/noise-standard",
    "Автор: Vlad",
    "Дата: 2026-07-XX",
    "Рубрика: Эксплуатация и сервис",
    "Формат: Статья",
    "Язык: RU",
    "════════════════",
    "ИЗОБРАЖЕНИЯ:",
    "[Image 1]",
    "Тип: обложка",
    "Соотношение: 16:9",
    "Имя файла: recuperator-noise-cover.jpg",
    "Промт (EN): a quiet bedroom at night with a wall-mounted ventilation unit",
    "Alt: Рекуператор в спальне ночью",
    "Title: Тихий рекуператор",
    "Caption: Современные модели почти бесшумны",
]


def make_docx_bytes(paragraphs: list[str]) -> bytes:
    """Build a real .docx in memory (python-docx is a dev-only dependency)."""
    import docx  # noqa: PLC0415

    document = docx.Document()
    for text in paragraphs:
        document.add_paragraph(text)
    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()


@pytest.fixture
def sample_paragraphs():
    return list(SAMPLE_PARAGRAPHS)


@pytest.fixture
def sample_docx_bytes():
    return make_docx_bytes(SAMPLE_PARAGRAPHS)


@pytest.fixture
def ctx():
    from imperal_sdk.testing import MockContext, MockSecretStore

    mock = MockContext()
    mock.secrets = MockSecretStore({})
    return mock
