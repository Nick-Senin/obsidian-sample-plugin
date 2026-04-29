"""
Telegram Publisher - публикация сообщения в Telegram канал

ЧТО ДЕЛАЕТ:
- Публикует текстовое сообщение с опциональной картинкой в Telegram канал
- Конвертирует Markdown разметку в HTML для Telegram
- Поддерживает жирный шрифт **текст**, курсив *текст*, код `код`, ссылки [текст](url)

ГДЕ ИСПОЛЬЗУЕТСЯ:
- f/prj_content_forge/publisher/publish_to_telegram

ИСПОЛЬЗУЕТ:
- Resource: u/theatmacreator/content_forge_bot
- Shared: f/transformations/telegram_publisher/publish_to_channel.py
"""
import wmill
import requests
import re
from io import BytesIO


def convert_markdown_to_html(text: str) -> str:
    """
    Конвертирует базовый Markdown в HTML для Telegram.

    Поддерживает:
    - **текст** или __текст__ → <b>текст</b>
    - *текст* или _текст_ → <i>текст</i>
    - `код` → <code>код</code>
    - [текст](url) → <a href="url">текст</a>

    @param text Текст с Markdown разметкой
    @return Текст с HTML разметкой
    """
    # Сначала экранируем существующие HTML теги
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    # Жирный текст: **text** или __text__
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.+?)__', r'<b>\1</b>', text)

    # Курсив: *text* или _text_
    text = re.sub(r'\*(?!\*)(.+?)\*(?!\*)', r'<i>\1</i>', text)
    text = re.sub(r'(?<!_)_(?!__)(.+?)(?<!_)_(?!__)', r'<i>\1</i>', text)

    # Инлайн код: `code`
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)

    # Ссылки: [text](url)
    text = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', text)

    # Восстанавливаем &amp; в ссылках
    text = text.replace('&amp;', '&')

    return text


def main(
    channel: str,
    text: str,
    photo_url: str = None,
) -> dict:
    """
    Публикует сообщение в Telegram канал.

    @param channel Имя канала (например, @channel_name)
    @param text Текст сообщения (поддерживается Markdown: **жирный**, *курсив*, `код`, [ссылка](url))
    @param photo_url URL картинки для публикации (опционально)
    @return Результат публикации
    """
    telegram_bot = wmill.get_resource("u/theatmacreator/content_forge_bot")
    bot_token = telegram_bot['token']

    api_url = f"https://api.telegram.org/bot{bot_token}"

    # Конвертируем Markdown в HTML
    text = convert_markdown_to_html(text)

    if photo_url:
        # Скачиваем картинку
        try:
            img_response = requests.get(photo_url, timeout=30)
            img_response.raise_for_status()
        except Exception as e:
            raise Exception(f"Failed to download image from {photo_url}: {str(e)}")

        # Client API (Telethon/Pyrogram) поддерживает caption до 4096 символов
        # Обрезаем текст если он длиннее лимита
        caption = text[:4096] if len(text) > 4096 else text

        # Отправка картинки с подписью
        url = f"{api_url}/sendPhoto"
        files = {
            "photo": ("image.jpg", BytesIO(img_response.content), "image/jpeg")
        }
        data = {
            "chat_id": channel,
            "caption": caption,
            "parse_mode": "HTML"
        }
        response = requests.post(url, files=files, data=data)
        response.raise_for_status()
    else:
        # Отправка только текста
        url = f"{api_url}/sendMessage"
        data = {
            "chat_id": channel,
            "text": text,
            "parse_mode": "HTML"
        }
        response = requests.post(url, json=data)
        response.raise_for_status()

    return response.json()
