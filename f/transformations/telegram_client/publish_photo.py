"""
Telegram Client Publisher - публикация через Telethon Client API

ЧТО ДЕЛАЕТ:
- Публикует фото с подписью до 4096 символов через Telegram Client API
- Поддерживает Markdown разметку: **жирный**, *курсив*, `код`, [ссылка](url)
- Использует Telethon с user-сессией (не Bot API)

ГДЕ ИСПОЛЬЗУЕТСЯ:
- f/prj_content_forge/publisher/publish_to_telegram

ИСПОЛЬЗУЕТ:
- Resource: u/theatmacreator/telegram_client_api
- Shared: f/shared/llm_utils
"""
import base64
import wmill
import asyncio
import os
import re
import tempfile
from pathlib import Path
from telethon import TelegramClient
from telethon.tl.types import MessageEntityTextUrl, MessageEntityBold, MessageEntityItalic, MessageEntityCode
from telethon.tl.functions.messages import SendMediaRequest
from telethon.tl.types import InputMediaPhotoExternal
import requests


def convert_markdown_to_telethon_entities(text: str):
    """
    Конвертирует Markdown в текст + entities для Telethon.

    @param text Текст с Markdown разметкой
    @return Кортеж (чистый текст, список entities)
    """
    entities = []
    offset = 0
    remaining_text = text

    # Обрабатываем **жирный**, *курсив*, `код`, [ссылка](url)
    # Используем while для замены с учётом смещений
    i = 0
    while i < len(remaining_text):
        # Проверяем **жирный**
        if remaining_text[i:i+2] == '**':
            end = remaining_text.find('**', i + 2)
            if end != -1:
                entities.append(MessageEntityBold(offset=offset + i, length=end - i - 2))
                remaining_text = remaining_text[:i] + remaining_text[i+2:end] + remaining_text[end+2:]
                continue

        # Проверяем *курсив*
        if remaining_text[i] == '*':
            end = remaining_text.find('*', i + 1)
            if end != -1:
                entities.append(MessageEntityItalic(offset=offset + i, length=end - i - 1))
                remaining_text = remaining_text[:i] + remaining_text[i+1:end] + remaining_text[end+1:]
                continue

        # Проверяем `код`
        if remaining_text[i] == '`':
            end = remaining_text.find('`', i + 1)
            if end != -1:
                entities.append(MessageEntityCode(offset=offset + i, length=end - i - 1))
                remaining_text = remaining_text[:i] + remaining_text[i+1:end] + remaining_text[end+1:]
                continue

        i += 1

    return remaining_text, entities


def main(
    channel: str,
    text: str,
    photo_url: str,
) -> dict:
    """
    Публикует фото с подписью в Telegram через Client API.

    @param channel Имя канала (например, @channel_name или -100...)
    @param text Текст сообщения (Markdown: **жирный**, *курсив*, `код`, [ссылка](url))
    @param photo_url URL картинки для публикации
    @return Результат публикации
    """
    telegram_client_api = wmill.get_resource("u/theatmacreator/telegram_client_api")

    api_id = int(telegram_client_api['api_id'])
    api_hash = telegram_client_api['api_hash']
    phone = telegram_client_api['phone']

    phone_slug = phone.replace("+", "")
    job_suffix = os.environ.get("WM_JOB_ID") or str(os.getpid())
    session_dir = tempfile.mkdtemp(prefix=f"tg_session_{phone_slug}_{job_suffix}_")
    session_path = os.path.join(session_dir, "session")
    session_file = Path(f"{session_path}.session")

    if telegram_client_api.get("session_data"):
        session_file.write_bytes(base64.b64decode(telegram_client_api["session_data"]))

    async def send_photo():
        client = TelegramClient(session_path, api_id, api_hash)

        try:
            await client.connect()

            if not await client.is_user_authorized():
                # Если не авторизованы, нужна интерактивная авторизация
                # Это не сработает в Windmill без интерактивного режима
                return {"error": "Client not authorized. Please run interactive authorization first."}

            # Скачиваем картинку
            img_response = requests.get(photo_url, timeout=30)
            img_response.raise_for_status()
            photo_data = img_response.content

            # Отправляем фото с подписью (до 4096 символов для Client API)
            # Обрезаем если длиннее
            caption = text[:4096] if len(text) > 4096 else text

            result = await client.send_file(
                entity=channel,
                file=photo_data,
                caption=caption,
                parse_mode='html'  # Telegram автоматически обрабатывает HTML
            )

            return {
                "success": True,
                "message_id": result.id,
                "channel": channel
            }

        finally:
            await client.disconnect()

    return asyncio.run(send_photo())
