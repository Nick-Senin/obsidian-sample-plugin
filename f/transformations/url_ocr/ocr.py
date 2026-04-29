"""
URL_OCR - Извлечение текста из изображений по URL

ЧТО ДЕЛАЕТ:
- Отправляет URL в Mistral OCR API
- Получает распознанный текст в формате markdown
- Объединяет текст со всех страниц

ГДЕ ИСПОЛЬЗУЕТСЯ:
- Используется для OCR изображений, PDF документов по URL

ИСПОЛЬЗУЕТ:
- Resource: u/theatmacreator/mistral_ocr
- External: Mistral OCR API (https://api.mistral.ai/v1/ocr)
"""
import wmill
import requests


def main(url: str, max_pages: int = 5, max_chars: int = 10000) -> dict:
    """
    Извлекает текст из изображения по URL через Mistral OCR API.

    @param url URL изображения или PDF документа
    @param max_pages Максимальное количество страниц для обработки (по умолчанию 5)
    @param max_chars Максимальное количество символов в выводе (по умолчанию 10000)
    @return Словарь с полем output - распознанный markdown текст
    """
    resource = wmill.get_resource("u/theatmacreator/mistral_ocr")
    api_key = resource["apiKey"]

    # Формируем запрос к Mistral OCR API
    # Используем document_url подход - Mistral сам скачает файл
    api_url = "https://api.mistral.ai/v1/ocr"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "mistral-ocr-2505",
        "document": {
            "type": "document_url",
            "document_url": url
        },
        "include_image_base64": False
    }

    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=60)

        # Если ошибка, выводим детали
        if response.status_code != 200:
            error_detail = response.text[:500] if response.text else response.status_code
            return {
                "output": "",
                "error": f"Mistral API error {response.status_code}: {error_detail}"
            }

        # Получаем ответ и проверяем размер перед JSON парсингом
        response_size = len(response.content)
        if response_size > 2 * 1024 * 1024:  # Если ответ > 2MB
            return {
                "output": "",
                "error": f"Response too large: {response_size / 1024 / 1024:.1f}MB (try smaller document or fewer pages)"
            }

        result = response.json()

        # Объединяем markdown со всех страниц (с ограничением)
        markdown_parts = []
        if "pages" in result:
            for i, page in enumerate(result["pages"]):
                if i >= max_pages:
                    break
                if "markdown" in page:
                    markdown_parts.append(page["markdown"])

        output = "\n\n".join(markdown_parts)

        if not output.strip():
            return {
                "output": "",
                "error": "No text extracted from the image"
            }

        # Ограничиваем размер вывода
        if len(output) > max_chars:
            output = output[:max_chars] + "\n\n... (truncated)"

        return {"output": output}

    except Exception as e:
        return {
            "output": "",
            "error": f"Error: {str(e)}"
        }
