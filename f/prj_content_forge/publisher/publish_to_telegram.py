# /// script
# dependencies = [
#     "telethon>=1.42.0",
#     "wmill",
#     "requests"
# ]
# ///

"""
Скрипт для автоматической публикации постов в Telegram.
Находит посты с сегодняшней датой публикации и отправляет в указанный канал.

Использует ТОЛЬКО Telegram Client API (Telethon) для всех операций:
- Фото с caption до 4096 символов
- Текстовые сообщения до 4096 символов

Поля Baserow:
- Дата публикации: дата для фильтрации
- Пост для ТГ: текст поста
- Итоговый постер: URL картинки (опционально)
- Адрес в Channels: адрес канала для публикации
- Статус: меняется на "Опубликовано" после публикации
"""
import wmill
import requests
import re
import asyncio
import os
from datetime import datetime
from io import BytesIO
from urllib.parse import quote

from telethon import TelegramClient


def load_resource(path: str) -> dict:
    """
    Совместимое чтение ресурса:
    1) стандартный wmill.get_resource
    2) fallback на /resources/get_value, если get_value_interpolated недоступен
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
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()


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

    # Курсив: *text* или _text_ (но не внутри жирного)
    text = re.sub(r'(?<!<b>)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', text)
    text = re.sub(r'(?<!<b>)_(?!__)(.+?)(?<!_)_(?!__)', r'<i>\1</i>', text)

    # Инлайн код: `code`
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)

    # Ссылки: [text](url)
    text = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', text)

    # Восстанавливаем &amp; в ссылках
    text = text.replace('&amp;', '&')

    return text


def publish_post(channel: str, text: str, photo_url: str = None) -> dict:
    """
    Публикует пост в Telegram канал через Client API (Telethon).

    Лимит caption/текста: 4096 символов.

    @param channel Имя канала (например, @channel_name или ID)
    @param text Текст поста (с Markdown разметкой)
    @param photo_url URL картинки (опционально)
    @return Результат отправки
    """
    # Конвертируем Markdown в HTML
    text = convert_markdown_to_html(text)

    if photo_url:
        # Публикация фото с caption через Client API
        return publish_photo_client_api(channel, text, photo_url)
    else:
        # Публикация текста через Client API
        return publish_text_client_api(channel, text)


def publish_photo_client_api(channel: str, text: str, photo_url: str) -> dict:
    """Публикация фото через Client API (Telethon)."""
    telegram_client_api = load_resource("u/theatmacreator/telegram_client_api")

    api_id = int(telegram_client_api['api_id'])
    api_hash = telegram_client_api['api_hash']
    phone = telegram_client_api['phone']

    # Создаём директорию для сессий
    import tempfile
    import os
    import base64
    from pathlib import Path
    phone_slug = phone.replace("+", "")
    job_suffix = os.environ.get("WM_JOB_ID") or str(os.getpid())
    session_dir = tempfile.mkdtemp(prefix=f"tg_session_{phone_slug}_{job_suffix}_")
    session_path = os.path.join(session_dir, "session")
    session_file = Path(session_path + ".session")

    # Загружаем session из ресурса (всегда перезаписываем для актуальности)
    if 'session_data' in telegram_client_api and telegram_client_api['session_data']:
        session_b64 = telegram_client_api['session_data']
        session_data = base64.b64decode(session_b64)
        session_file.write_bytes(session_data)

    async def send_photo():
        client = TelegramClient(session_path, api_id, api_hash)

        try:
            await client.connect()

            if not await client.is_user_authorized():
                raise Exception(f"Telegram client not authorized for {phone}. Please run authorization first.")

            # Скачиваем картинку
            img_response = requests.get(photo_url, timeout=30)
            img_response.raise_for_status()
            photo_data = img_response.content

            # Обрезаем если длиннее 4096 символов
            caption = text[:4096] if len(text) > 4096 else text

            # Оборачиваем в BytesIO с расширением, чтобы Telegram распознал как изображение
            from io import BytesIO
            photo_bytesio = BytesIO(photo_data)
            # Определяем расширение из URL или используем .jpg по умолчанию
            if photo_url.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                ext = photo_url.rsplit('.', 1)[-1].lower()
                photo_bytesio.name = f'photo.{ext}'
            else:
                photo_bytesio.name = 'photo.jpg'

            # Отправляем фото как изображение
            result = await client.send_file(
                entity=channel,
                file=photo_bytesio,
                caption=caption,
                parse_mode='html'
            )

            return {
                "ok": True,
                "message_id": result.id,
                "chat_id": channel
            }

        finally:
            await client.disconnect()

    return asyncio.run(send_photo())


def publish_text_client_api(channel: str, text: str) -> dict:
    """Публикация текста через Client API (Telethon)."""
    telegram_client_api = load_resource("u/theatmacreator/telegram_client_api")

    api_id = int(telegram_client_api['api_id'])
    api_hash = telegram_client_api['api_hash']
    phone = telegram_client_api['phone']

    # Создаём директорию для сессий
    import tempfile
    import os
    import base64
    from pathlib import Path
    phone_slug = phone.replace("+", "")
    job_suffix = os.environ.get("WM_JOB_ID") or str(os.getpid())
    session_dir = tempfile.mkdtemp(prefix=f"tg_session_{phone_slug}_{job_suffix}_")
    session_path = os.path.join(session_dir, "session")
    session_file = Path(session_path + ".session")

    # Загружаем session из ресурса (всегда перезаписываем для актуальности)
    if 'session_data' in telegram_client_api and telegram_client_api['session_data']:
        session_b64 = telegram_client_api['session_data']
        session_data = base64.b64decode(session_b64)
        session_file.write_bytes(session_data)

    async def send_text():
        client = TelegramClient(session_path, api_id, api_hash)

        try:
            await client.connect()

            if not await client.is_user_authorized():
                raise Exception(f"Telegram client not authorized for {phone}. Please run authorization first.")

            # Обрезаем если длиннее 4096 символов
            message_text = text[:4096] if len(text) > 4096 else text

            # Отправляем текстовое сообщение
            result = await client.send_message(
                entity=channel,
                message=message_text,
                parse_mode='html'
            )

            return {
                "ok": True,
                "message_id": result.id,
                "chat_id": channel
            }

        finally:
            await client.disconnect()

    return asyncio.run(send_text())


def main() -> dict:
    """
    Основная функция: находит и публикует посты.

    @return Словарь с результатами (количество и ID опубликованных постов)
    """
    baserow = load_resource("u/theatmacreator/baserow_api")
    baserow_token = baserow if isinstance(baserow, str) else baserow.get("token")
    if not baserow_token:
        raise ValueError("Baserow token is missing in resource u/theatmacreator/baserow_api")

    # Получаем сегодняшнюю дату в формате YYYY-MM-DD
    today = datetime.now().strftime("%Y-%m-%d")
    url = "https://content.nicksenin.com/api/database/rows/table/269/?user_field_names=true"

    headers = {
        "Authorization": f"Token {baserow_token}",
        "Content-Type": "application/json",
    }

    # Фильтр по дате публикации и статусу
    params = {
        "user_field_names": "true",
        "filter__field_Дата публикации__equal": today,
        "filter__field_Статус__equal": "Готово к публикации",
    }

    # Получаем посты
    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()
    data = response.json()
    posts = data.get("results", [])

    if not posts:
        return {"published_count": 0, "published_ids": [], "message": "No posts found for today"}

    published = []
    errors = []

    for post in posts:
        row_id = post.get('id', 'unknown')

        # Двойная проверка даты публикации
        pub_date = post.get('Дата публикации', '')
        # Baserow может вернуть дату как объект или строку
        if isinstance(pub_date, dict):
            pub_date_str = pub_date.get('value', '')
        else:
            pub_date_str = str(pub_date) if pub_date else ''

        # Извлекаем только дату (без времени) из строки
        if pub_date_str:
            # Формат может быть "2025-01-15" или "2025-01-15T10:30:00+00:00"
            pub_date_str = pub_date_str.split('T')[0][:10]

        if pub_date_str != today:
            errors.append(f"Row {row_id}: Wrong publication date '{pub_date_str}', expected '{today}'")
            continue

        # Пропускаем посты с неправильным статусом (двойная проверка)
        status = post.get('Статус', '')
        # Baserow возвращает статус как объект: {'id': X, 'value': 'Название', 'color': '...'}
        status_value = status.get('value') if isinstance(status, dict) else status
        if status_value != 'Готово к публикации':
            errors.append(f"Row {row_id}: Wrong status '{status_value}', expected 'Готово к публикации'")
            continue
        try:

            # Получаем связь с таблицей Channels
            channel_link = post.get('Канал публикации')
            if not channel_link:
                errors.append(f"Row {row_id}: No channel link")
                continue

            # Baserow возвращает связь как список объектов с ID
            if isinstance(channel_link, list) and len(channel_link) > 0:
                channel_id = channel_link[0].get('id')
            elif isinstance(channel_link, dict):
                channel_id = channel_link.get('id')
            else:
                errors.append(f"Row {row_id}: Invalid channel link format")
                continue

            # Получаем данные канала из таблицы 746
            channel_url = f"https://content.nicksenin.com/api/database/rows/table/746/{channel_id}/?user_field_names=true"
            channel_response = requests.get(channel_url, headers=headers)
            channel_response.raise_for_status()
            channel_data = channel_response.json()

            # Получаем адрес канала из поля "Адрес"
            channel = channel_data.get('Адрес')
            if not channel:
                errors.append(f"Row {row_id}: No address in channel record")
                continue

            text = post.get('Пост для ТГ', '')
            poster_data = post.get('Итоговый постер')

            # Baserow возвращает файл как объект JSON с полем 'url'
            poster_url = None
            if poster_data:
                try:
                    if isinstance(poster_data, list) and len(poster_data) > 0:
                        poster_url = poster_data[0].get('url')
                    elif isinstance(poster_data, dict):
                        poster_url = poster_data.get('url')
                except Exception as e:
                    errors.append(f"Row {row_id}: Failed to parse poster URL: {str(e)}")
                    continue

            # Публикуем пост через Client API (Telethon)
            try:
                publish_post(channel, text, poster_url)
            except Exception as e:
                # Пробрасываем ошибку дальше с контекстом
                raise Exception(f"Telegram error (channel={channel}, photo={bool(poster_url)}): {str(e)}")

            # Обновляем статус на "Опубликован"
            update_url = f"https://content.nicksenin.com/api/database/rows/table/269/{row_id}/"
            update_response = requests.patch(
                update_url,
                params={"user_field_names": "true"},
                json={"Статус": "Опубликован"},
                headers=headers
            )
            try:
                update_response.raise_for_status()
            except requests.HTTPError as e:
                error_detail = ""
                try:
                    error_data = e.response.json()
                    if isinstance(error_data, dict):
                        error_detail = f" - {error_data}"
                except:
                    pass
                raise Exception(f"Baserow API error updating status{error_detail}")

            published.append(row_id)

        except Exception as e:
            errors.append(f"Row {post.get('id', 'unknown')}: {str(e)}")

    return {
        "published_count": len(published),
        "published_ids": published,
        "errors": errors,
        "message": f"Published {len(published)} posts, {len(errors)} errors"
    }
