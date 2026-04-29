"""
PANDOC_CONVERTER - Конвертация файлов между форматами

ЧТО ДЕЛАЕТ:
- Конвертирует файлы между различными форматами (Markdown, HTML, DOCX, PDF, и др.)
- Поддерживает все форматы входа/выхода, доступные в Pandoc
- Работает с содержимым файла как со строкой

ГДЕ ИСПОЛЬЗУЕТСЯ:
- f/prj_content_forge/flows/...
- Любые проекты где нужна конвертация документов

ИСПОЛЬЗУЕТ:
- External: pypandoc (требует установки pandoc на системе)
"""
import wmill
import pypandoc


def _ensure_pandoc() -> None:
    """
    Убеждается, что pandoc установлен и доступен.
    Если нет — скачивает встроенную версию.
    """
    try:
        pypandoc.get_pandoc_path()
    except Exception:
        # Pandoc не найден, скачиваем
        pypandoc.download_pandoc()


def main(
    content: str,
    from_format: str = "markdown",
    to_format: str = "html",
    extra_args: list[str] = []
) -> dict:
    """
    Конвертирует содержимое файла из одного формата в другой через Pandoc.

    @param content Содержимое файла для конвертации
    @param from_format Исходный формат (markdown, html, docx, pdf, etc.)
    @param to_format Целевой формат (markdown, html, docx, pdf, etc.)
    @param extra_args Дополнительные аргументы для pandoc (опционально)
    @return Словарь с полем output - сконвертированное содержимое

    Примеры форматов:
    - Входные: markdown, html, docx, pdf, odt, rtf, epub, json
    - Выходные: markdown, html, docx, pdf, odt, rtf, epub, json, plain

    Дополнительные аргументы:
    - ["--standalone"]  # Создать полноценный документ с заголовками
    - ["--wrap=none"]   # Без переноса строк
    - ["--extract-media=./media"]  # Извлечь медиа
    """
    try:
        # Убеждаемся, что pandoc доступен
        _ensure_pandoc()

        output = pypandoc.convert_text(
            source=content,
            to=to_format,
            format=from_format,
            extra_args=extra_args
        )

        return {"output": output}
    except Exception as e:
        return {
            "output": "",
            "error": f"Conversion failed: {str(e)}"
        }
