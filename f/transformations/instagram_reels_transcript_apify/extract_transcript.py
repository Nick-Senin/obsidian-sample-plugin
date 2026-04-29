from __future__ import annotations

import re
import time
from typing import Any, TypedDict

from apify_client import ApifyClient


class apify_api_key(TypedDict):
    api_key: str


TRANSCRIPT_KEY_RE = re.compile(
    r"(transcript|subtitles?|closed[_\s-]?captions?|auto[_\s-]?captions?|speech[_\s-]?to[_\s-]?text)",
    re.IGNORECASE,
)


def _normalize_instagram_url(value: str) -> str:
    url = value.strip()
    if not url:
        return ""
    if url.startswith("http://") or url.startswith("https://"):
        return url
    username = url.strip("/@")
    return f"https://www.instagram.com/{username}/"


def _normalize_transcript_value(value: Any) -> str | None:
    if value is None:
        return None

    if isinstance(value, str):
        text = value.strip()
        return text or None

    if isinstance(value, (int, float, bool)):
        return None

    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            text = _normalize_transcript_value(item)
            if text:
                parts.append(text)
        if not parts:
            return None
        return "\n".join(parts)

    if isinstance(value, dict):
        ordered_keys = [
            "text",
            "transcript",
            "subtitle",
            "subtitles",
            "segments",
            "items",
            "chunks",
            "data",
        ]
        parts: list[str] = []

        for key in ordered_keys:
            if key in value:
                text = _normalize_transcript_value(value[key])
                if text:
                    parts.append(text)

        if parts:
            return "\n".join(parts)

        for nested in value.values():
            text = _normalize_transcript_value(nested)
            if text:
                parts.append(text)

        if parts:
            return "\n".join(parts)

    return None


def _extract_transcript(item: Any, path: str = "") -> tuple[str | None, str | None]:
    if isinstance(item, dict):
        if "transcript" in item:
            text = _normalize_transcript_value(item.get("transcript"))
            if text:
                next_path = f"{path}.transcript" if path else "transcript"
                return text, next_path

        for key, value in item.items():
            key_str = str(key)
            normalized = re.sub(r"[^a-z0-9]", "", key_str.lower())
            if normalized in {"caption", "captionisedited", "firstcomment"}:
                continue
            next_path = f"{path}.{key_str}" if path else key_str

            if TRANSCRIPT_KEY_RE.search(key_str):
                text = _normalize_transcript_value(value)
                if text:
                    return text, next_path

            nested_text, nested_path = _extract_transcript(value, next_path)
            if nested_text:
                return nested_text, nested_path

    if isinstance(item, list):
        for index, value in enumerate(item):
            next_path = f"{path}[{index}]" if path else f"[{index}]"
            nested_text, nested_path = _extract_transcript(value, next_path)
            if nested_text:
                return nested_text, nested_path

    return None, None


def _extract_reel_url(item: dict[str, Any]) -> str | None:
    url = item.get("url")
    if isinstance(url, str) and url:
        return url

    short_code = item.get("shortCode")
    if isinstance(short_code, str) and short_code:
        return f"https://www.instagram.com/reel/{short_code}/"

    return None


def _run_actor_with_retries(
    client: ApifyClient,
    actor_id: str,
    run_input: dict[str, Any],
    retries: int,
    timeout_secs: int,
) -> dict[str, Any]:
    attempt = 0
    while True:
        try:
            return client.actor(actor_id).call(run_input=run_input, timeout_secs=timeout_secs)
        except Exception:
            if attempt >= retries:
                raise
            time.sleep(2**attempt)
            attempt += 1


def _extract_item_rows(client: ApifyClient, run: dict[str, Any]) -> list[dict[str, Any]]:
    dataset_id = run.get("defaultDatasetId")
    if not dataset_id:
        return []

    rows: list[dict[str, Any]] = []
    for item in client.dataset(dataset_id).iterate_items():
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _find_best_transcript(rows: list[dict[str, Any]]) -> tuple[str | None, str | None, str | None]:
    for row in rows:
        transcript, transcript_path = _extract_transcript(row)
        if transcript:
            return transcript, transcript_path, _extract_reel_url(row)
    return None, None, None


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        output.append(item)
    return output


def _scrape_reel_transcript_with_fallback(
    client: ApifyClient,
    reel_url: str,
    retries: int,
    timeout_secs: int,
    primary_actor_id: str,
    transcript_actor_id: str,
) -> dict[str, Any]:
    first_error: str | None = None

    primary_input = {
        "directUrls": [reel_url],
        "resultsType": "reels",
        "resultsLimit": 1,
    }
    try:
        primary_run = _run_actor_with_retries(
            client=client,
            actor_id=primary_actor_id,
            run_input=primary_input,
            retries=retries,
            timeout_secs=timeout_secs,
        )
        primary_rows = _extract_item_rows(client, primary_run)
        transcript, transcript_path, item_url = _find_best_transcript(primary_rows)
        if transcript:
            return {
                "reel_url": item_url or reel_url,
                "transcript": transcript,
                "error": None,
                "source_actor": primary_actor_id,
                "source_field": transcript_path,
            }
    except Exception as exc:  # noqa: BLE001
        first_error = f"{primary_actor_id} failed: {exc}"

    transcript_input = {
        "username": [reel_url],
        "resultsLimit": 1,
        "includeTranscript": True,
    }
    try:
        transcript_run = _run_actor_with_retries(
            client=client,
            actor_id=transcript_actor_id,
            run_input=transcript_input,
            retries=retries,
            timeout_secs=timeout_secs,
        )
        transcript_rows = _extract_item_rows(client, transcript_run)
        transcript, transcript_path, item_url = _find_best_transcript(transcript_rows)
        if transcript:
            return {
                "reel_url": item_url or reel_url,
                "transcript": transcript,
                "error": None,
                "source_actor": transcript_actor_id,
                "source_field": transcript_path,
            }
        if first_error:
            return {
                "reel_url": reel_url,
                "transcript": None,
                "error": f"{first_error}; {transcript_actor_id} transcript_not_found",
                "source_actor": transcript_actor_id,
                "source_field": None,
            }
        return {
            "reel_url": reel_url,
            "transcript": None,
            "error": "transcript_not_found",
            "source_actor": transcript_actor_id,
            "source_field": None,
        }
    except Exception as exc:  # noqa: BLE001
        if first_error:
            return {
                "reel_url": reel_url,
                "transcript": None,
                "error": f"{first_error}; {transcript_actor_id} failed: {exc}",
                "source_actor": transcript_actor_id,
                "source_field": None,
            }
        return {
            "reel_url": reel_url,
            "transcript": None,
            "error": f"{transcript_actor_id} failed: {exc}",
            "source_actor": transcript_actor_id,
            "source_field": None,
        }


def _scrape_channel_transcripts(
    client: ApifyClient,
    channel_url: str,
    reels_limit: int,
    retries: int,
    timeout_secs: int,
    transcript_actor_id: str,
) -> list[dict[str, Any]]:
    run_input = {
        "username": [channel_url],
        "resultsLimit": reels_limit,
        "includeTranscript": True,
    }
    run = _run_actor_with_retries(
        client=client,
        actor_id=transcript_actor_id,
        run_input=run_input,
        retries=retries,
        timeout_secs=timeout_secs,
    )
    rows = _extract_item_rows(client, run)

    if not rows:
        return [
            {
                "reel_url": channel_url,
                "transcript": None,
                "error": "empty_dataset",
                "source_actor": transcript_actor_id,
                "source_field": None,
            }
        ]

    items: list[dict[str, Any]] = []
    for row in rows:
        transcript, transcript_path = _extract_transcript(row)
        items.append(
            {
                "reel_url": _extract_reel_url(row) or channel_url,
                "transcript": transcript,
                "error": None if transcript else "transcript_not_found",
                "source_actor": transcript_actor_id,
                "source_field": transcript_path,
            }
        )
    return items


def main(
    apify: apify_api_key,
    reel_url: str | None = None,
    reel_urls: list[str] | None = None,
    channel: str | None = None,
    reels_limit: int = 5,
    retries: int = 2,
    actor_id: str = "apify/instagram-scraper",
    transcript_actor_id: str = "apify/instagram-reel-scraper",
    timeout_secs: int = 300,
) -> dict[str, Any]:
    """
    Извлекает speech-to-text транскрипты из Instagram Reels через Apify.

    Поддерживаемый ввод:
    - reel_url: один URL рилса
    - reel_urls: несколько URL рилсов
    - channel: URL канала или username (получаются последние reels_limit рилсов)

    Стратегия:
    1) пытается через actor_id (по умолчанию apify/instagram-scraper),
    2) если transcript не найден, fallback на transcript_actor_id
       (по умолчанию apify/instagram-reel-scraper с includeTranscript=true).
    """
    api_key = (apify or {}).get("api_key")
    if not isinstance(api_key, str) or not api_key.strip():
        raise ValueError("apify.api_key is required")

    normalized_reel_urls: list[str] = []
    if isinstance(reel_url, str) and reel_url.strip():
        normalized_reel_urls.append(_normalize_instagram_url(reel_url))

    if isinstance(reel_urls, list):
        for value in reel_urls:
            if isinstance(value, str) and value.strip():
                normalized_reel_urls.append(_normalize_instagram_url(value))

    normalized_reel_urls = _dedupe(normalized_reel_urls)

    normalized_channel_url: str | None = None
    if isinstance(channel, str) and channel.strip():
        normalized_channel_url = _normalize_instagram_url(channel)

    if not normalized_reel_urls and not normalized_channel_url:
        raise ValueError("Provide reel_url, reel_urls or channel")

    retries = max(0, int(retries))
    timeout_secs = max(30, int(timeout_secs))
    reels_limit = max(1, int(reels_limit))

    client = ApifyClient(api_key)
    items: list[dict[str, Any]] = []

    for url in normalized_reel_urls:
        items.append(
            _scrape_reel_transcript_with_fallback(
                client=client,
                reel_url=url,
                retries=retries,
                timeout_secs=timeout_secs,
                primary_actor_id=actor_id,
                transcript_actor_id=transcript_actor_id,
            )
        )

    if normalized_channel_url:
        try:
            items.extend(
                _scrape_channel_transcripts(
                    client=client,
                    channel_url=normalized_channel_url,
                    reels_limit=reels_limit,
                    retries=retries,
                    timeout_secs=timeout_secs,
                    transcript_actor_id=transcript_actor_id,
                )
            )
        except Exception as exc:  # noqa: BLE001
            items.append(
                {
                    "reel_url": normalized_channel_url,
                    "transcript": None,
                    "error": f"{transcript_actor_id} failed: {exc}",
                    "source_actor": transcript_actor_id,
                    "source_field": None,
                }
            )

    total = len(items)
    with_transcript = sum(1 for item in items if item.get("transcript"))

    return {
        "items": items,
        "stats": {
            "total": total,
            "with_transcript": with_transcript,
            "without_transcript_or_error": total - with_transcript,
        },
    }
