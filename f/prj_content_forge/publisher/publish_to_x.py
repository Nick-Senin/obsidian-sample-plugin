# /// script
# dependencies = [
#     "requests>=2.32.0",
#     "requests-oauthlib>=2.0.0",
#     "wmill"
# ]
# ///

"""
Publish a post or reply to X/Twitter, optionally with an image.

Supports:
- top-level post with text
- reply/comment using reply_to_tweet_id
- image upload from image_url, image_path, or image_base64

Uses Windmill resource: u/theatmacreator/x_api
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
import wmill
from requests_oauthlib import OAuth1


MEDIA_UPLOAD_URL = "https://api.x.com/2/media/upload"
CREATE_POST_URL = "https://api.x.com/2/tweets"
DEFAULT_RESOURCE_PATH = "u/theatmacreator/x_api"
SUPPORTED_IMAGE_TYPES = {
    "image/jpeg",
    "image/pjpeg",
    "image/png",
    "image/webp",
    "image/bmp",
    "image/tiff",
}


class XApiError(RuntimeError):
    pass


def _load_resource_compat(path: str) -> dict[str, Any]:
    if path == "__env__":
        return {
            "api_key": os.environ.get("X_API_KEY", ""),
            "api_secret": os.environ.get("X_API_SECRET", ""),
            "access_token": os.environ.get("X_ACCESS_TOKEN", ""),
            "access_token_secret": os.environ.get("X_ACCESS_TOKEN_SECRET", ""),
            "oauth2_access_token": os.environ.get("X_OAUTH2_ACCESS_TOKEN", ""),
        }

    try:
        return wmill.get_resource(path)
    except Exception as exc:
        if "get_value_interpolated" not in str(exc):
            raise

        base_url = os.environ.get("BASE_INTERNAL_URL") or os.environ.get("BASE_URL")
        workspace = os.environ.get("WM_WORKSPACE")
        token = os.environ.get("WM_TOKEN")
        if not base_url or not workspace or not token:
            raise

        encoded_path = quote(path, safe="/")
        url = f"{base_url}/api/w/{workspace}/resources/get_value/{encoded_path}"
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        response.raise_for_status()
        return response.json() if response.text else {}


def _resolve_var_ref(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    if not value.startswith("$var:"):
        return value
    variable_path = value.removeprefix("$var:")
    return wmill.get_variable(variable_path)


def _resolve_resource_vars(resource: dict[str, Any]) -> dict[str, Any]:
    return {key: _resolve_var_ref(value) for key, value in resource.items()}


def _build_auth(resource: dict[str, Any]) -> tuple[dict[str, str], OAuth1 | None, str]:
    resource = _resolve_resource_vars(resource)
    oauth2_token = str(resource.get("oauth2_access_token") or "").strip()
    if oauth2_token:
        return {"Authorization": f"Bearer {oauth2_token}"}, None, "OAuth 2.0 user token"

    required = {
        "api_key": resource.get("api_key"),
        "api_secret": resource.get("api_secret"),
        "access_token": resource.get("access_token"),
        "access_token_secret": resource.get("access_token_secret"),
    }
    missing = [key for key, value in required.items() if not str(value or "").strip()]
    if missing:
        raise XApiError(
            "Missing X API credential field(s) in resource: " + ", ".join(missing)
        )

    auth = OAuth1(
        str(required["api_key"]),
        str(required["api_secret"]),
        str(required["access_token"]),
        str(required["access_token_secret"]),
    )
    return {}, auth, "OAuth 1.0a user context"


def _format_api_error(
    status_code: int,
    payload: dict[str, Any],
    headers: requests.structures.CaseInsensitiveDict[str],
) -> str:
    parts = [f"X API request failed with HTTP {status_code}."]
    for item in payload.get("errors", []):
        title = item.get("title") or "Error"
        detail = item.get("detail") or item.get("message") or item.get("type")
        parts.append(f"{title}: {detail}" if detail else title)
    if "detail" in payload:
        parts.append(str(payload["detail"]))
    if "title" in payload and "detail" not in payload:
        parts.append(str(payload["title"]))

    remaining = headers.get("x-rate-limit-remaining")
    reset = headers.get("x-rate-limit-reset")
    if remaining is not None:
        parts.append(f"rate_limit_remaining={remaining}")
    if reset is not None:
        parts.append(f"rate_limit_reset_epoch={reset}")
    return " ".join(parts)


def _parse_json_response(response: requests.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        body = response.text[:500]
        raise XApiError(
            f"X API returned non-JSON response ({response.status_code}): {body}"
        ) from exc

    if response.status_code >= 400:
        raise XApiError(_format_api_error(response.status_code, payload, response.headers))
    return payload


def _request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    auth: OAuth1 | None,
    expected_status: set[int],
    **kwargs: Any,
) -> dict[str, Any]:
    try:
        response = requests.request(
            method,
            url,
            headers=headers,
            auth=auth,
            timeout=60,
            **kwargs,
        )
    except requests.RequestException as exc:
        raise XApiError(f"Network error while calling X API: {exc}") from exc

    payload = _parse_json_response(response)
    if response.status_code not in expected_status:
        raise XApiError(_format_api_error(response.status_code, payload, response.headers))
    if payload.get("errors"):
        raise XApiError(_format_api_error(response.status_code, payload, response.headers))
    return payload


def _detect_media_type(filename: str | None, explicit_media_type: str | None) -> str:
    media_type = explicit_media_type or mimetypes.guess_type(filename or "")[0]
    if media_type not in SUPPORTED_IMAGE_TYPES:
        supported = ", ".join(sorted(SUPPORTED_IMAGE_TYPES))
        raise XApiError(
            f"Unsupported image type: {media_type or 'unknown'}. "
            f"Supported media_type values: {supported}"
        )
    return media_type


def _read_image_bytes(
    image_url: str | None,
    image_path: str | None,
    image_base64: str | None,
) -> tuple[bytes | None, str | None, str | None]:
    sources = [bool(image_url), bool(image_path), bool(image_base64)]
    if sum(sources) == 0:
        return None, None, None
    if sum(sources) > 1:
        raise XApiError("Provide only one image source: image_url, image_path, or image_base64")

    if image_url:
        response = requests.get(image_url, timeout=60)
        response.raise_for_status()
        filename = image_url.rsplit("/", 1)[-1].split("?", 1)[0] or "image"
        media_type = response.headers.get("content-type", "").split(";", 1)[0] or None
        return response.content, filename, media_type

    if image_path:
        path = Path(image_path).expanduser()
        if not path.is_file():
            raise XApiError(f"Image file does not exist: {path}")
        return path.read_bytes(), path.name, None

    assert image_base64 is not None
    try:
        return base64.b64decode(image_base64), "image", None
    except Exception as exc:
        raise XApiError("image_base64 is not valid base64") from exc


def _wait_for_media_processing(
    media_id: str,
    processing_info: dict[str, Any],
    headers: dict[str, str],
    auth: OAuth1 | None,
) -> None:
    for _ in range(20):
        state = processing_info.get("state")
        if state == "succeeded":
            return
        if state == "failed":
            error = processing_info.get("error") or processing_info
            raise XApiError(f"Media processing failed for media_id={media_id}: {error}")

        wait_seconds = int(processing_info.get("check_after_secs") or 2)
        time.sleep(max(1, min(wait_seconds, 15)))
        payload = _request_json(
            "GET",
            MEDIA_UPLOAD_URL,
            headers=headers,
            auth=auth,
            expected_status={200},
            params={"command": "STATUS", "media_id": media_id},
        )
        processing_info = (payload.get("data") or {}).get("processing_info") or {}

    raise XApiError(f"Timed out waiting for media processing for media_id={media_id}")


def _upload_image(
    image_bytes: bytes,
    filename: str,
    media_type: str,
    headers: dict[str, str],
    auth: OAuth1 | None,
) -> str:
    payload = _request_json(
        "POST",
        MEDIA_UPLOAD_URL,
        headers=headers,
        auth=auth,
        expected_status={200},
        data={"media_category": "tweet_image", "media_type": media_type},
        files={"media": (filename, image_bytes, media_type)},
    )

    data = payload.get("data") or {}
    media_id = data.get("id")
    if not media_id:
        raise XApiError(f"Upload response did not include data.id: {json.dumps(payload)}")

    processing_info = data.get("processing_info")
    if processing_info:
        _wait_for_media_processing(str(media_id), processing_info, headers, auth)

    return str(media_id)


def _create_post(
    text: str,
    media_id: str | None,
    reply_to_tweet_id: str | None,
    headers: dict[str, str],
    auth: OAuth1 | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if text:
        payload["text"] = text
    if media_id:
        payload["media"] = {"media_ids": [media_id]}
    if reply_to_tweet_id:
        payload["reply"] = {"in_reply_to_tweet_id": reply_to_tweet_id}

    if not payload.get("text") and not payload.get("media"):
        raise XApiError("A post or reply needs text, media, or both")

    response = _request_json(
        "POST",
        CREATE_POST_URL,
        headers={**headers, "Content-Type": "application/json"},
        auth=auth,
        expected_status={201},
        json=payload,
    )
    data = response.get("data")
    if not data or not data.get("id"):
        raise XApiError(f"Create Post response did not include data.id: {json.dumps(response)}")
    return data


def main(
    text: str = "",
    reply_to_tweet_id: str | None = None,
    image_url: str | None = None,
    image_path: str | None = None,
    image_base64: str | None = None,
    image_media_type: str | None = None,
    resource_path: str = "u/theatmacreator/x_api",
) -> dict[str, Any]:
    """
    Publish a top-level X post or a reply/comment, optionally with an image.

    @param text Post/reply text. Optional if image is provided.
    @param reply_to_tweet_id Existing Post ID to reply/comment to.
    @param image_url Public image URL to download and attach.
    @param image_path Local image path. Useful for local tests; server path must exist in Windmill.
    @param image_base64 Base64-encoded image bytes.
    @param image_media_type Explicit MIME type for image_base64 or ambiguous URLs.
    @param resource_path Windmill resource path with X API credentials.
    @return Created post info and uploaded media ID if any.
    """
    resource = _load_resource_compat(resource_path)
    headers, auth, auth_mode = _build_auth(resource)

    image_bytes, filename, detected_media_type = _read_image_bytes(
        image_url=image_url,
        image_path=image_path,
        image_base64=image_base64,
    )

    media_id = None
    if image_bytes is not None:
        media_type = _detect_media_type(filename, image_media_type or detected_media_type)
        media_id = _upload_image(
            image_bytes=image_bytes,
            filename=filename or "image",
            media_type=media_type,
            headers=headers,
            auth=auth,
        )

    post = _create_post(
        text=text,
        media_id=media_id,
        reply_to_tweet_id=reply_to_tweet_id,
        headers=headers,
        auth=auth,
    )

    return {
        "ok": True,
        "auth_mode": auth_mode,
        "media_id": media_id,
        "post": post,
        "reply_to_tweet_id": reply_to_tweet_id,
    }
