from __future__ import annotations

from typing import Any


def _as_entities(extract_entities: dict[str, Any] | None) -> list[str]:
    if not isinstance(extract_entities, dict):
        return []
    entities = extract_entities.get("entities")
    if not isinstance(entities, list):
        return []
    return [str(x).strip() for x in entities if str(x).strip()]


def _as_image_rows(search_images: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(search_images, dict):
        return []
    rows = search_images.get("results")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _flatten_image_urls(rows: list[dict[str, Any]]) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for row in rows:
        images = row.get("images")
        if not isinstance(images, list):
            continue
        for image in images:
            if not isinstance(image, dict):
                continue
            url = image.get("url")
            if not isinstance(url, str) or not url or url in seen:
                continue
            seen.add(url)
            urls.append(url)
    return urls


def _telegram_text(transcript: str, entities: list[str], rows: list[dict[str, Any]]) -> str:
    entity_lines = "\n".join(f"- {entity}" for entity in entities) or "- не найдены"
    image_lines: list[str] = []
    for row in rows:
        entity = row.get("entity")
        images = row.get("images")
        if not isinstance(entity, str) or not isinstance(images, list):
            continue
        count = len([x for x in images if isinstance(x, dict) and x.get("url")])
        if count:
            image_lines.append(f"- {entity}: {count}")

    excerpt = transcript.strip()
    if len(excerpt) > 1200:
        excerpt = excerpt[:1197].rstrip() + "..."

    parts = [
        "**Entities extracted from transcript**",
        entity_lines,
        "",
        "**Images found**",
        "\n".join(image_lines) if image_lines else "- no images found",
    ]
    if excerpt:
        parts.extend(["", "**Transcript excerpt**", excerpt])
    return "\n".join(parts)


def main(
    transcript: str,
    extract_entities: dict[str, Any] | None = None,
    search_images: dict[str, Any] | None = None,
    title_prefix: str = "Transcript entities",
) -> dict[str, Any]:
    entities = _as_entities(extract_entities)
    rows = _as_image_rows(search_images)
    poster_urls = _flatten_image_urls(rows)
    telegram_text = _telegram_text(transcript, entities, rows)
    digest_title = f"{title_prefix}: {', '.join(entities[:5])}" if entities else title_prefix

    return {
        "title": digest_title,
        "entities": entities,
        "images_by_entity": rows,
        "poster_urls": poster_urls,
        "photo_url": poster_urls[0] if poster_urls else None,
        "telegram_text": telegram_text,
    }
