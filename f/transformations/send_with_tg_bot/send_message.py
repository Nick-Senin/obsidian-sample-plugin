import re
import json
import os
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

try:
    import wmill  # type: ignore
except Exception:  # pragma: no cover
    class _WmillStub:
        def get_variable(self, *_args, **_kwargs):
            raise RuntimeError("wmill is not available")

    wmill = _WmillStub()  # type: ignore


def _derive_chat_id(chat_id_or_link: str) -> str:
    s = (chat_id_or_link or "").strip()
    if not s:
        raise ValueError("chat_id_or_link is required")

    # https://t.me/c/<internal_id>/<message_id>
    m = re.match(r"^https?://t\.me/c/(\d+)/(\d+)", s)
    if m:
        internal_id = m.group(1)
        return f"-100{internal_id}"

    # Already numeric chat id (e.g. -100...)
    if re.match(r"^-?\d+$", s):
        return s

    # e.g. @channelusername
    return s


def main(
    message: str,
    chat_id_or_link: str,
    token_variable_path: str = "u/theatmacreator/veto_tg_token",
    disable_web_page_preview: bool = True,
    photo_url: str | None = None,
) -> dict:
    """
    SEND_MESSAGE - отправляет сообщение в Telegram через Bot API.

    Токен бота берётся из secret variable Windmill (wmill.get_variable).

    @param message Текст сообщения
    @param chat_id_or_link chat_id (например -100...), @channelusername или ссылка вида https://t.me/c/<id>/<msg>
    @param token_variable_path Путь к secret variable c токеном бота
    @param disable_web_page_preview Отключить превью ссылок (по умолчанию True)
    @param photo_url URL картинки для отправки через sendPhoto
    """
    if not isinstance(message, str) or not message.strip():
        raise ValueError("message is required")

    if not isinstance(token_variable_path, str) or not token_variable_path.strip():
        raise ValueError("token_variable_path is required")

    token_variable_path = token_variable_path.strip()
    try:
        token = get_variable(token_variable_path)
    except Exception as e:
        msg = str(e)
        if "Variable" in msg and "not found" in msg:
            raise RuntimeError(
                f"Telegram bot token variable not found: {token_variable_path}. "
                f"Create it as a *secret variable* in Windmill."
            )
        raise

    if not isinstance(token, str) or not token.strip():
        raise ValueError(f"Telegram bot token is empty (variable: {token_variable_path})")

    chat_id = _derive_chat_id(chat_id_or_link)
    # Важно: токен находится в URL, поэтому при ошибках нельзя пробрасывать исключения requests "как есть",
    # иначе токен может оказаться в ошибке/логах.
    if isinstance(photo_url, str) and photo_url.strip():
        method = "sendPhoto"
        payload = {
            "chat_id": chat_id,
            "photo": photo_url.strip(),
            "caption": message[:1024],
        }
    else:
        method = "sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "disable_web_page_preview": bool(disable_web_page_preview),
        }
    req = Request(
        f"https://api.telegram.org/bot{token.strip()}/{method}",
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
    )

    try:
        with urlopen(req, timeout=30) as resp:
            body_text = resp.read().decode("utf-8")
    except HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegram HTTP error: {e.code}: {body_text[:500]}")
    except URLError as e:
        raise RuntimeError(f"Telegram request failed: {type(e).__name__}")

    try:
        data = json.loads(body_text)
    except Exception:
        raise RuntimeError(f"Telegram response is not JSON: {body_text[:500]}")

    if not data.get("ok", False):
        raise RuntimeError(f"Telegram API error: {data}")

    return {
        "ok": True,
        "chat_id": chat_id,
        "method": method,
        "message_id": (data.get("result") or {}).get("message_id"),
        "raw": data,
    }


def get_variable(path: str) -> str:
    try:
        return wmill.get_variable(path)
    except Exception:
        base_url = os.environ.get("BASE_INTERNAL_URL") or os.environ.get("BASE_URL")
        workspace = os.environ.get("WM_WORKSPACE")
        token = os.environ.get("WM_TOKEN")
        if not base_url or not workspace or not token:
            raise

        encoded_path = quote(path, safe="/")
        url = f"{base_url}/api/w/{workspace}/variables/get/{encoded_path}"
        req = Request(url, headers={"Authorization": f"Bearer {token}"})
        with urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
        if not body:
            return ""
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return body
        if isinstance(payload, dict) and "value" in payload:
            return payload["value"] or ""
        if isinstance(payload, str):
            return payload
        raise ValueError(f"Unexpected variable payload for {path}: {type(payload).__name__}")
