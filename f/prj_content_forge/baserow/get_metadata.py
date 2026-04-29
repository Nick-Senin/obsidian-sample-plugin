"""
GET_BASEROW_METADATA - получение каналов и жанров из Baserow

ЧТО ДЕЛАЕТ:
- Получает все записи из таблицы каналов (table/746) и жанров (table/747)
- Возвращает обе структуры за один запрос

ГДЕ ИСПОЛЬЗУЕТСЯ:
- OBS Recording Handler (локальный Python скрипт)
- Любые скрипты которым нужен список каналов и жанров

ИСПОЛЬЗУЕТ:
- Resource: u/theatmacreator/baserow_api
- External: Baserow API
"""
import wmill
import requests
import os
from urllib.parse import quote


def load_resource(path: str):
    """
    Совместимое чтение ресурса:
    - через /resources/get_value (обходит сломанный get_value_interpolated)
    - fallback на wmill.get_resource, если env недоступны
    """
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


def main() -> dict:
    """
    Получает список всех каналов и жанров из Baserow.

    @return Списки channels и genres
    """
    baserow_token = get_baserow_token()

    headers = {
        "Authorization": f"Token {baserow_token}",
        "Content-Type": "application/json",
    }

    # Получаем каналы
    channels_response = requests.get(
        "https://content.nicksenin.com/api/database/rows/table/746/",
        params={"user_field_names": "true", "size": "100"},
        headers=headers
    )
    channels_response.raise_for_status()
    channels_data = channels_response.json()

    channels = []
    for row in channels_data.get("results", []):
        channels.append({
            "id": str(row.get("id", "")),
            "name": row.get("Name", ""),
            "address": row.get("Адрес", ""),
            "active": row.get("Active", False)
        })

    # Получаем жанры
    genres_response = requests.get(
        "https://content.nicksenin.com/api/database/rows/table/747/",
        params={"user_field_names": "true", "size": "100"},
        headers=headers
    )
    genres_response.raise_for_status()
    genres_data = genres_response.json()

    genres = []
    for row in genres_data.get("results", []):
        genres.append({
            "id": str(row.get("id", "")),
            "name": row.get("Название", ""),
            "description": row.get("Описание", "")
        })

    return {
        "channels": channels,
        "genres": genres
    }
