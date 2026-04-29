"""
SCRAPE_URL - Парсинг URL в markdown

ЧТО ДЕЛАЕТ:
- Парсит веб-страницу по URL
- Возвращает содержимое в формате markdown

ГДЕ ИСПОЛЬЗУЕТСЯ:
- Используется для извлечения контента из веб-страниц

ИСПОЛЬЗУЕТ:
- Resource: u/theatmacreator/firecrawl
- External: Firecrawl API (https://api.firecrawl.dev/v1/scrape)
"""
import wmill
import requests


def main(url: str) -> dict:
    """
    Парсит URL и возвращает содержимое в markdown.

    @param url URL страницы для парсинга
    @return Словарь с полем output - markdown содержимое
    """
    resource = wmill.get_resource("u/theatmacreator/firecrawl")

    response = requests.post(
        "https://api.firecrawl.dev/v1/scrape",
        headers={
            "Authorization": f"Bearer {resource['apiKey']}",
            "Content-Type": "application/json"
        },
        json={
            "url": url,
            "formats": ["markdown"]
        },
        timeout=60
    )

    response.raise_for_status()
    data = response.json()

    return {"output": data.get("data", {}).get("markdown", "")}
