"""
Unit tests for X/Twitter Windmill publisher.
"""

from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from f.prj_content_forge.publisher import publish_to_x


@pytest.fixture
def x_resource() -> dict:
    return {
        "api_key": "api-key",
        "api_secret": "api-secret",
        "access_token": "access-token",
        "access_token_secret": "access-token-secret",
        "oauth2_access_token": "",
    }


def make_response(status_code: int, payload: dict, headers: dict | None = None) -> Mock:
    response = Mock()
    response.status_code = status_code
    response.headers = headers or {}
    response.json.return_value = payload
    response.text = str(payload)
    response.raise_for_status = Mock()
    return response


class TestAuth:
    def test_build_auth_uses_oauth2_token_when_present(self):
        headers, auth, auth_mode = publish_to_x._build_auth(
            {
                "oauth2_access_token": "oauth2-token",
                "api_key": "",
                "api_secret": "",
                "access_token": "",
                "access_token_secret": "",
            }
        )

        assert headers == {"Authorization": "Bearer oauth2-token"}
        assert auth is None
        assert auth_mode == "OAuth 2.0 user token"

    def test_build_auth_uses_oauth1_credentials(self, x_resource):
        headers, auth, auth_mode = publish_to_x._build_auth(x_resource)

        assert headers == {}
        assert auth is not None
        assert auth_mode == "OAuth 1.0a user context"

    def test_build_auth_resolves_variable_references(self, wmill):
        wmill.get_variable.side_effect = lambda path: f"value-for-{path}"

        headers, auth, auth_mode = publish_to_x._build_auth(
            {
                "api_key": "$var:u/test/api_key",
                "api_secret": "$var:u/test/api_secret",
                "access_token": "$var:u/test/access_token",
                "access_token_secret": "$var:u/test/access_token_secret",
                "oauth2_access_token": "",
            }
        )

        assert headers == {}
        assert auth is not None
        assert auth_mode == "OAuth 1.0a user context"
        assert wmill.get_variable.call_count == 4

    def test_build_auth_reports_missing_fields(self):
        with pytest.raises(publish_to_x.XApiError, match="api_secret"):
            publish_to_x._build_auth(
                {
                    "api_key": "api-key",
                    "api_secret": "",
                    "access_token": "access-token",
                    "access_token_secret": "secret",
                    "oauth2_access_token": "",
                }
            )


class TestImageInput:
    def test_read_image_bytes_from_base64(self):
        payload = base64.b64encode(b"image-bytes").decode("ascii")

        image_bytes, filename, media_type = publish_to_x._read_image_bytes(
            image_url=None,
            image_path=None,
            image_base64=payload,
        )

        assert image_bytes == b"image-bytes"
        assert filename == "image"
        assert media_type is None

    def test_read_image_bytes_from_path(self, tmp_path: Path):
        image = tmp_path / "photo.png"
        image.write_bytes(b"png-bytes")

        image_bytes, filename, media_type = publish_to_x._read_image_bytes(
            image_url=None,
            image_path=str(image),
            image_base64=None,
        )

        assert image_bytes == b"png-bytes"
        assert filename == "photo.png"
        assert media_type is None

    def test_read_image_bytes_from_url(self):
        response = make_response(
            200,
            {},
            headers={"content-type": "image/png; charset=binary"},
        )
        response.content = b"url-image"

        with patch.object(publish_to_x.requests, "get", return_value=response) as get:
            image_bytes, filename, media_type = publish_to_x._read_image_bytes(
                image_url="https://example.com/image.png?x=1",
                image_path=None,
                image_base64=None,
            )

        get.assert_called_once_with("https://example.com/image.png?x=1", timeout=60)
        assert image_bytes == b"url-image"
        assert filename == "image.png"
        assert media_type == "image/png"

    def test_read_image_bytes_rejects_multiple_sources(self, tmp_path: Path):
        image = tmp_path / "photo.png"
        image.write_bytes(b"png")

        with pytest.raises(publish_to_x.XApiError, match="only one image source"):
            publish_to_x._read_image_bytes(
                image_url="https://example.com/image.png",
                image_path=str(image),
                image_base64=None,
            )

    def test_detect_media_type_rejects_unknown_type(self):
        with pytest.raises(publish_to_x.XApiError, match="Unsupported image type"):
            publish_to_x._detect_media_type("file.txt", None)


class TestApiRequests:
    def test_upload_image_returns_media_id(self):
        response = make_response(200, {"data": {"id": "media-123"}})

        with patch.object(publish_to_x.requests, "request", return_value=response) as request:
            media_id = publish_to_x._upload_image(
                image_bytes=b"image",
                filename="image.png",
                media_type="image/png",
                headers={},
                auth=None,
            )

        assert media_id == "media-123"
        assert request.call_args.kwargs["data"] == {
            "media_category": "tweet_image",
            "media_type": "image/png",
        }
        assert "media" in request.call_args.kwargs["files"]

    def test_create_top_level_post_payload(self):
        response = make_response(201, {"data": {"id": "tweet-1", "text": "hello"}})

        with patch.object(publish_to_x.requests, "request", return_value=response) as request:
            post = publish_to_x._create_post(
                text="hello",
                media_id="media-1",
                reply_to_tweet_id=None,
                headers={},
                auth=None,
            )

        assert post["id"] == "tweet-1"
        assert request.call_args.kwargs["json"] == {
            "text": "hello",
            "media": {"media_ids": ["media-1"]},
        }

    def test_create_reply_payload(self):
        response = make_response(201, {"data": {"id": "reply-1", "text": "reply"}})

        with patch.object(publish_to_x.requests, "request", return_value=response) as request:
            post = publish_to_x._create_post(
                text="reply",
                media_id=None,
                reply_to_tweet_id="tweet-parent",
                headers={},
                auth=None,
            )

        assert post["id"] == "reply-1"
        assert request.call_args.kwargs["json"] == {
            "text": "reply",
            "reply": {"in_reply_to_tweet_id": "tweet-parent"},
        }

    def test_create_post_requires_text_or_media(self):
        with pytest.raises(publish_to_x.XApiError, match="needs text"):
            publish_to_x._create_post(
                text="",
                media_id=None,
                reply_to_tweet_id="tweet-parent",
                headers={},
                auth=None,
            )

    def test_request_json_formats_api_errors(self):
        response = make_response(
            401,
            {"errors": [{"title": "Unauthorized", "detail": "Bad token"}]},
            headers={"x-rate-limit-remaining": "0"},
        )

        with patch.object(publish_to_x.requests, "request", return_value=response):
            with pytest.raises(publish_to_x.XApiError) as exc_info:
                publish_to_x._request_json(
                    "POST",
                    "https://api.x.com/2/tweets",
                    headers={},
                    auth=None,
                    expected_status={201},
                    json={},
                )

        assert "HTTP 401" in str(exc_info.value)
        assert "Unauthorized: Bad token" in str(exc_info.value)
        assert "rate_limit_remaining=0" in str(exc_info.value)


class TestMain:
    def test_main_publishes_text_only_reply(self, x_resource):
        with patch.object(publish_to_x, "_load_resource_compat", return_value=x_resource), \
             patch.object(publish_to_x, "_upload_image") as upload_image, \
             patch.object(
                 publish_to_x,
                 "_create_post",
                 return_value={"id": "reply-1", "text": "reply"},
             ) as create_post:

            result = publish_to_x.main(
                text="reply",
                reply_to_tweet_id="tweet-parent",
                resource_path="u/test/x_api",
            )

        upload_image.assert_not_called()
        create_post.assert_called_once()
        assert create_post.call_args.kwargs["text"] == "reply"
        assert create_post.call_args.kwargs["media_id"] is None
        assert create_post.call_args.kwargs["reply_to_tweet_id"] == "tweet-parent"
        assert result["ok"] is True
        assert result["post"]["id"] == "reply-1"

    def test_main_publishes_reply_with_image(self, x_resource):
        with patch.object(publish_to_x, "_load_resource_compat", return_value=x_resource), \
             patch.object(publish_to_x, "_upload_image", return_value="media-1") as upload_image, \
             patch.object(
                 publish_to_x,
                 "_create_post",
                 return_value={"id": "reply-1", "text": "reply"},
             ) as create_post:

            result = publish_to_x.main(
                text="reply with image",
                reply_to_tweet_id="tweet-parent",
                image_base64=base64.b64encode(b"image").decode("ascii"),
                image_media_type="image/png",
                resource_path="u/test/x_api",
            )

        upload_image.assert_called_once()
        create_post.assert_called_once()
        assert create_post.call_args.kwargs["media_id"] == "media-1"
        assert create_post.call_args.kwargs["reply_to_tweet_id"] == "tweet-parent"
        assert result["media_id"] == "media-1"

