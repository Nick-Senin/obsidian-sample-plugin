"""
Обработчик webhook для Content Forge Telegram бота.
Принимает входящие сообщения от пользователей и отправляет подтверждение с полученной идеей.
"""
# /// script
# dependencies = [
#   "wmill",
#   "requests>=2.32.0"
# ]
# ///

from __future__ import annotations

import json
import os
from typing import Any, Optional
from urllib.parse import quote

import requests
import wmill


def _normalize_update(update: Any, body: Any) -> dict:
    """
    Windmill HTTP routes могут передавать payload по-разному:
    - dict (уже распарсенный JSON)
    - str/bytes (сырой JSON)
    - обёртка вида {"body": {...}, ...} при включённом wrap_body
    """
    data = body if body is not None else update
    if data is None:
        return {}

    if isinstance(data, (bytes, bytearray)):
        try:
            data = data.decode("utf-8")
        except Exception:
            data = data.decode("utf-8", errors="replace")

    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            return {}

    if isinstance(data, dict):
        # Если включён wrap_body, Telegram update может оказаться внутри ключа body
        if "message" not in data and isinstance(data.get("body"), dict):
            inner = data.get("body")
            if isinstance(inner, dict):
                return inner
        return data

    return {}


def _extract_message_and_chat(update_data: dict) -> tuple[dict, Optional[int]]:
    """
    Telegram update может приходить в разных вариантах:
    message / edited_message / callback_query.message и т.д.
    Возвращаем message-объект и chat_id (если есть).
    """
    message: dict = (
        update_data.get("message")
        or update_data.get("edited_message")
        or update_data.get("channel_post")
        or update_data.get("edited_channel_post")
        or (update_data.get("callback_query") or {}).get("message")
        or {}
    )
    chat_id = (message.get("chat") or {}).get("id")
    if isinstance(chat_id, int):
        return message, chat_id
    return message, None


def _get_resource_compat(path: str) -> dict:
    """
    Читает ресурс с fallback на /get_value, если /get_value_interpolated недоступен.
    """
    try:
        return wmill.get_resource(path)
    except Exception as e:
        if "get_value_interpolated" not in str(e):
            raise

        base_url = os.environ.get("BASE_INTERNAL_URL") or os.environ.get("BASE_URL")
        workspace = os.environ.get("WM_WORKSPACE")
        token = os.environ.get("WM_TOKEN")
        if not base_url or not workspace or not token:
            raise

        encoded_path = quote(path, safe="/")
        url = f"{base_url}/api/w/{workspace}/resources/get_value/{encoded_path}"
        response = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=30)
        response.raise_for_status()
        return response.json() if response.text else {}


def main(update: dict = None, body: dict = None) -> dict:
    """
    Обрабатывает webhook от Telegram и отправляет подтверждение пользователю.

    @param update Входящий объект update от Telegram (опционально)
    @param body Прямой JSON от Telegram (опционально)
    @return Информация о полученном сообщении
    """
    telegram = _get_resource_compat("u/theatmacreator/content_forge_bot")
    token = telegram['token']

    # Поддержка обоих форматов: прямой JSON (body) или обёрнутый (update)
    update_data = _normalize_update(update=update, body=body)

    # Извлекаем информацию из update
    message, chat_id = _extract_message_and_chat(update_data)
    text = message.get("text", "") if isinstance(message, dict) else ""
    caption = message.get("caption", "") if isinstance(message, dict) else ""
    user = {}
    if isinstance(message, dict):
        user = message.get("from") or message.get("sender_chat") or {}

    # Идея может быть в text или в caption (например, если прислали фото с подписью)
    idea = (text or caption or "").strip()

    # Формируем ответ пользователю
    if (text or "").strip().startswith("/start"):
        reply_text = (
            "Привет! Я Content Forge бот.\n\n"
            "Пришли мне текстом идею для поста — я сохраню её и подтвержу получение.\n"
            "Можно также прислать фото с подписью (caption) — я возьму подпись как идею."
        )
    elif idea:
        reply_text = f"✅ Ваша идея получена:\n\n{idea}"
    else:
        reply_text = (
            "Я получил сообщение, но не вижу текста идеи.\n\n"
            "Пришли, пожалуйста, идею текстом (или фото/видео с подписью)."
        )

    # Отвечаем в Telegram (если удалось определить chat_id)
    if chat_id is not None:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        # Не валим обработчик, даже если Telegram API временно недоступен
        try:
            requests.post(url, json={"chat_id": chat_id, "text": reply_text}, timeout=5)
        except Exception:
            pass

    # Сохраняем идею в Baserow асинхронно (в фоне), но только если это не /start
    if idea and not (idea.startswith("/start")):
        wmill.run_script_by_path_async(
            "f/prj_content_forge/baserow_ideas/save_idea",
            args={"idea": idea},
        )

    return {
        "idea": idea,
        "reply_text": reply_text,
        "user_id": user.get("id") if isinstance(user, dict) else None,
        "username": user.get("username") if isinstance(user, dict) else None,
        "chat_id": chat_id,
    }
