"""
HUMAN_IN_LOOP / TELEGRAM_CHOICE

Отправляет вопрос в личный чат Telegram через Bot API, показывает inline-кнопки
с вариантами ответа, ждёт нажатия и возвращает выбранный вариант.

Важно: этот вариант использует Telegram getUpdates polling. Для этого у бота не
должен быть активен webhook. Используйте отдельного бота/токен для approvals,
если другой бот уже подключён к Windmill HTTP Route через webhook.
"""
# /// script
# dependencies = [
#   "wmill"
# ]
# ///

from __future__ import annotations

import json
import os
import re
import time
import uuid
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

import wmill


MAX_CALLBACK_DATA_BYTES = 64


class TelegramPollingConflict(RuntimeError):
    """Raised when Telegram rejects getUpdates because another poll is active."""


def _derive_chat_id(chat_id_or_link: str) -> str:
    s = (chat_id_or_link or "").strip()
    if not s:
        raise ValueError("chat_id_or_link is required")

    m = re.match(r"^https?://t\.me/c/(\d+)/(\d+)", s)
    if m:
        return f"-100{m.group(1)}"

    if re.match(r"^-?\d+$", s):
        return s

    return s


def _get_variable(path: str) -> str:
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


def _telegram_request(
    token: str,
    method: str,
    payload: dict[str, Any] | None = None,
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    req = Request(
        f"https://api.telegram.org/bot{token}/{method}",
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload or {}).encode("utf-8"),
        method="POST",
    )

    try:
        with urlopen(req, timeout=timeout_seconds) as resp:
            body_text = resp.read().decode("utf-8")
    except HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        if method == "getUpdates" and e.code == 409:
            raise TelegramPollingConflict(body_text[:500])
        raise RuntimeError(f"Telegram HTTP error in {method}: {e.code}: {body_text[:500]}")
    except URLError as e:
        raise RuntimeError(f"Telegram request failed in {method}: {type(e).__name__}")

    try:
        data = json.loads(body_text)
    except Exception:
        raise RuntimeError(f"Telegram response is not JSON in {method}: {body_text[:500]}")

    if not data.get("ok", False):
        description = str(data.get("description", data))[:500]
        raise RuntimeError(f"Telegram API error in {method}: {description}")

    result = data.get("result")
    return result if isinstance(result, dict) else {"result": result}


def _normalize_options(options: list[Any]) -> list[dict[str, Any]]:
    if not isinstance(options, list) or not options:
        raise ValueError("options must be a non-empty array")

    normalized: list[dict[str, Any]] = []
    for index, option in enumerate(options):
        if isinstance(option, str):
            label = option.strip()
            value: Any = option
        elif isinstance(option, dict):
            raw_label = (
                option.get("label")
                or option.get("text")
                or option.get("title")
                or option.get("name")
                or option.get("value")
            )
            label = str(raw_label or "").strip()
            value = option.get("value", label)
        else:
            label = str(option).strip()
            value = option

        if not label:
            raise ValueError(f"options[{index}] has empty label")

        normalized.append({"label": label, "value": value, "index": index})

    return normalized


def _build_inline_keyboard(
    request_id: str,
    options: list[dict[str, Any]],
    columns: int,
) -> list[list[dict[str, str]]]:
    columns = max(1, min(int(columns or 1), 4))
    buttons = []

    for option in options:
        callback_data = f"hitl:{request_id}:{option['index']}"
        if len(callback_data.encode("utf-8")) > MAX_CALLBACK_DATA_BYTES:
            raise ValueError("Generated callback_data is too long")
        buttons.append({"text": option["label"], "callback_data": callback_data})

    return [buttons[i : i + columns] for i in range(0, len(buttons), columns)]


def _ensure_polling_allowed(token: str, delete_webhook_if_set: bool) -> dict[str, Any]:
    webhook_info = _telegram_request(token, "getWebhookInfo")
    webhook_url = str(webhook_info.get("url") or "").strip()

    if webhook_url and delete_webhook_if_set:
        _telegram_request(token, "deleteWebhook", {"drop_pending_updates": False})
        return {"had_webhook": True, "webhook_url": webhook_url, "deleted": True}

    if webhook_url:
        raise RuntimeError(
            "This Telegram bot has an active webhook, so getUpdates polling cannot be used. "
            "Use a dedicated approval bot token, disable the webhook, or run this script with "
            "delete_webhook_if_set=True if you intentionally want to disconnect the webhook."
        )

    return {"had_webhook": False, "webhook_url": "", "deleted": False}


def _get_initial_offset(token: str) -> int | None:
    try:
        result = _telegram_request(
            token,
            "getUpdates",
            {"timeout": 0, "allowed_updates": ["callback_query"]},
            timeout_seconds=30,
        )
    except TelegramPollingConflict:
        return None

    updates = result.get("result") if isinstance(result.get("result"), list) else []
    if not updates:
        return None
    return max(int(update.get("update_id", 0)) for update in updates) + 1


def _wait_for_callback(
    token: str,
    request_id: str,
    valid_indexes: set[int],
    offset: int | None,
    timeout_seconds: int,
    poll_timeout_seconds: int,
) -> dict[str, Any]:
    deadline = time.monotonic() + max(1, int(timeout_seconds))
    current_offset = offset

    while time.monotonic() < deadline:
        remaining = max(1, int(deadline - time.monotonic()))
        poll_timeout = min(max(1, int(poll_timeout_seconds)), remaining)
        payload: dict[str, Any] = {
            "timeout": poll_timeout,
            "allowed_updates": ["callback_query"],
        }
        if current_offset is not None:
            payload["offset"] = current_offset

        try:
            result = _telegram_request(
                token,
                "getUpdates",
                payload,
                timeout_seconds=poll_timeout + 10,
            )
        except TelegramPollingConflict:
            # Telegram allows only one active getUpdates request per bot token.
            # A previous long-poll can remain open briefly after a canceled job.
            time.sleep(min(2, max(1, remaining)))
            continue

        updates = result.get("result") if isinstance(result.get("result"), list) else []

        for update in updates:
            update_id = update.get("update_id")
            if isinstance(update_id, int):
                current_offset = update_id + 1

            callback = update.get("callback_query") or {}
            data = str(callback.get("data") or "")
            prefix = f"hitl:{request_id}:"
            if not data.startswith(prefix):
                continue

            raw_index = data[len(prefix) :]
            try:
                option_index = int(raw_index)
            except ValueError:
                continue

            if option_index not in valid_indexes:
                continue

            return {
                "callback": callback,
                "option_index": option_index,
                "offset": current_offset,
            }

    raise TimeoutError(f"No Telegram answer received within {timeout_seconds} seconds")


def main(
    message: str,
    options: list[Any],
    chat_id_or_link: str,
    token_variable_path: str = "u/theatmacreator/veto_tg_token",
    timeout_seconds: int = 36000,
    poll_timeout_seconds: int = 20,
    columns: int = 1,
    delete_webhook_if_set: bool = False,
    remove_keyboard_after_answer: bool = True,
) -> dict[str, Any]:
    """
    @param message Текст вопроса/сообщения для Telegram
    @param options Массив вариантов: строки или объекты {"label": "...", "value": ...}
    @param chat_id_or_link Telegram chat_id, @username или ссылка t.me/c/<id>/<msg>
    @param token_variable_path Путь к secret variable с Telegram bot token
    @param timeout_seconds Сколько секунд ждать ответ
    @param poll_timeout_seconds Длительность одного Telegram long-poll запроса
    @param columns Количество кнопок в строке, от 1 до 4
    @param delete_webhook_if_set Удалить webhook бота перед polling, если он установлен
    @param remove_keyboard_after_answer Убрать inline-клавиатуру после выбора
    """
    if not isinstance(message, str) or not message.strip():
        raise ValueError("message is required")
    if not isinstance(token_variable_path, str) or not token_variable_path.strip():
        raise ValueError("token_variable_path is required")

    token = _get_variable(token_variable_path.strip())
    if not isinstance(token, str) or not token.strip():
        raise ValueError(f"Telegram bot token is empty (variable: {token_variable_path})")

    chat_id = _derive_chat_id(chat_id_or_link)
    normalized_options = _normalize_options(options)
    request_id = uuid.uuid4().hex[:16]
    keyboard = _build_inline_keyboard(request_id, normalized_options, columns)
    webhook_status = _ensure_polling_allowed(token.strip(), bool(delete_webhook_if_set))
    initial_offset = _get_initial_offset(token.strip())

    sent = _telegram_request(
        token.strip(),
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": message.strip(),
            "reply_markup": {"inline_keyboard": keyboard},
            "disable_web_page_preview": True,
        },
    )

    callback_result = _wait_for_callback(
        token=token.strip(),
        request_id=request_id,
        valid_indexes={int(option["index"]) for option in normalized_options},
        offset=initial_offset,
        timeout_seconds=timeout_seconds,
        poll_timeout_seconds=poll_timeout_seconds,
    )

    callback = callback_result["callback"]
    callback_id = callback.get("id")
    selected_index = int(callback_result["option_index"])
    selected = normalized_options[selected_index]

    if callback_id:
        _telegram_request(
            token.strip(),
            "answerCallbackQuery",
            {"callback_query_id": callback_id, "text": f"Выбрано: {selected['label']}"},
        )

    sent_message_id = sent.get("message_id")
    if remove_keyboard_after_answer and sent_message_id is not None:
        try:
            _telegram_request(
                token.strip(),
                "editMessageReplyMarkup",
                {
                    "chat_id": chat_id,
                    "message_id": sent_message_id,
                    "reply_markup": {"inline_keyboard": []},
                },
            )
        except Exception:
            pass

    user = callback.get("from") if isinstance(callback, dict) else {}
    return {
        "ok": True,
        "request_id": request_id,
        "message": message.strip(),
        "selected": {
            "index": selected_index,
            "label": selected["label"],
            "value": selected["value"],
        },
        "chat_id": chat_id,
        "telegram": {
            "message_id": sent_message_id,
            "callback_query_id": callback_id,
            "user_id": user.get("id") if isinstance(user, dict) else None,
            "username": user.get("username") if isinstance(user, dict) else None,
        },
        "webhook_status": webhook_status,
    }
