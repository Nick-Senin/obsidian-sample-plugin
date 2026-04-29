"""
CREATE_POST - создание записи поста в Baserow

ЧТО ДЕЛАЕТ:
- Создаёт новую строку в таблице Baserow (table/269)
- Сохраняет все данные поста: сырой текст, идеи, названия, итог
- Загружает постеры по URL в Baserow storage
- Генерирует уникальный номер поста (timestamp + random)
- Устанавливает статус по умолчанию "На вычитку тезисов"
- Поддерживает дополнительные поля: channel_id, genre_id, date, poster_urls

Поля Baserow:
- Сырая расшифровка
- Статус
- Идеи для картинок
- Названия
- Итоговый текст
- Постеры (File field)
- Номер (автогенерируемый)

ГДЕ ИСПОЛЬЗУЕТСЯ:
- f/prj_content_forge/flows/create_posts_from_transcript__flow
- f/prj_content_forge/process_recording

ИСПОЛЬЗУЕТ:
- Resource: u/theatmacreator/baserow_api
- External: Baserow API (https://content.nicksenin.com/api/database/rows/table/269/)
"""
import wmill
from datetime import datetime, timezone
import random
import string
import json
import requests
import re
import os
from urllib.parse import quote


def load_resource(path: str):
    base_url = os.environ.get("BASE_INTERNAL_URL") or os.environ.get("BASE_URL")
    workspace = os.environ.get("WM_WORKSPACE")
    token = os.environ.get("WM_TOKEN")
    if base_url and workspace and token:
        encoded_path = quote(path, safe="/")
        url = f"{base_url}/api/w/{workspace}/resources/get_value/{encoded_path}"
        resp = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=30)
        resp.raise_for_status()
        return resp.json()
    return wmill.get_resource(path)


def get_baserow_token() -> str:
    baserow = load_resource("u/theatmacreator/baserow_api")
    if isinstance(baserow, str) and baserow.strip():
        return baserow.strip()
    if isinstance(baserow, dict) and (baserow.get("token") or "").strip():
        return str(baserow["token"]).strip()
    raise ValueError("Baserow token is missing in resource u/theatmacreator/baserow_api")


def generate_post_number() -> str:
    """Генерирует уникальный номер поста (timestamp + random)."""
    timestamp = datetime.now().strftime("%s")
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
    return f"{timestamp[-5:]}{random_str}"

def normalize_publication_date(value: str) -> str:
    """
    Normalizes a date for Baserow "Дата публикации".
    Preferred format: YYYY-MM-DD.
    Accepts:
    - YYYY-MM-DD
    - YYYY-MM-DDTHH:MM:SS...
    - DD.MM.YYYY
    """
    if not value:
        return ""
    s = str(value).strip()
    if not s:
        return ""
    if "T" in s:
        s = s.split("T", 1)[0].strip()
    if re.match(r"^\d{2}\.\d{2}\.\d{4}$", s):
        dt = datetime.strptime(s, "%d.%m.%Y")
        return dt.strftime("%Y-%m-%d")
    return s


def normalize_link_row_id(value) -> int | None:
    """
    Converts an incoming id into an int for Baserow link-row fields.
    Returns None if conversion is not possible.
    """
    if value is None:
        return None
    if isinstance(value, int):
        return value
    s = str(value).strip()
    if not s:
        return None
    if not re.match(r"^\d+$", s):
        return None
    return int(s)


def upload_file_via_url(baserow_token: str, file_url: str) -> dict:
    """
    Загружает файл в Baserow по URL.

    @param baserow_token API токен Baserow
    @param file_url URL файла для загрузки
    @return Ответ от Baserow с информацией о загруженном файле
    """
    url = "https://content.nicksenin.com/api/user-files/upload-via-url/"

    headers = {
        "Authorization": f"Token {baserow_token}",
        "Content-Type": "application/json",
    }

    payload = {"url": file_url}

    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()

    return response.json()


def main(
    raw_post: str,
    image_ideas: str,
    titles: str,
    final_text: str,
    status: str = "На вычитку тезисов",
    channel_id: str = None,
    genre_id: str = None,
    publication_date: str = None,
    date: str = None,
    poster_urls: list = None,
) -> dict:
    """
    Создает новый пост в Baserow.

    @param raw_post Сырая расшифровка поста
    @param image_ideas Идеи для картинок (JSON или текст)
    @param titles Названия поста (JSON или текст)
    @param final_text Итоговый текст поста (JSON или текст)
    @param status Статус поста (по умолчанию "На вычитку тезисов")
    @param channel_id ID канала публикации (опционально)
    @param genre_id ID жанра поста (опционально)
    @param publication_date Дата публикации (предпочтительно YYYY-MM-DD) (опционально)
    @param date Алиас для publication_date (backward-compatible)
    @param poster_urls Список URL постеров для загрузки (опционально)
    @return Результат запроса к Baserow
    """
    baserow_token = get_baserow_token()

    # Важно: `user_field_names=true` должен быть query-параметром без лишнего "/",
    # иначе Baserow не распознаёт режим и игнорирует имена полей в payload.
    url = "https://content.nicksenin.com/api/database/rows/table/269/"

    headers = {
        "Authorization": f"Token {baserow_token}",
        "Content-Type": "application/json",
    }

    # Дата добавления в формате YYYY-MM-DD (UTC)
    date_added = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    payload = {
        "Сырая расшифровка": raw_post,
        "Статус": status,
        "Идеи для картинок": image_ideas,
        "Названия": titles,
        "Итоговый текст": final_text,
        "Номер": generate_post_number(),
        "Дата добавления": date_added
    }

    # Добавляем дату публикации если указана
    pub_date = publication_date or date
    pub_date_norm = normalize_publication_date(pub_date) if pub_date else ""
    payload["Дата публикации"] = pub_date_norm or date_added

    # Link-row fields
    channel_row_id = normalize_link_row_id(channel_id)
    if channel_row_id is not None:
        payload["Канал публикации"] = [channel_row_id]

    genre_row_id = normalize_link_row_id(genre_id)
    if genre_row_id is not None:
        payload["Жанр"] = [genre_row_id]

    # Загружаем постеры по URL в Baserow storage
    if poster_urls:
        poster_files = []
        for poster_url in poster_urls:
            file_info = upload_file_via_url(baserow_token, poster_url)
            poster_files.append({"name": file_info["name"]})
        payload["Постеры"] = poster_files

    response = requests.post(
        url,
        params={"user_field_names": "true"},
        json=payload,
        headers=headers
    )

    response.raise_for_status()

    return response.json()
