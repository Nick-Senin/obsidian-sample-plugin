"""
LIST_GENRES - получение списка всех жанров из Baserow

ЧТО ДЕЛАЕТ:
- Получает все записи из таблицы жанров (table/747)
- Возвращает список жанров с ID, названием и промптом

ГДЕ ИСПОЛЬЗУЕТСЯ:
- Временный скрипт для тестирования

ИСПОЛЬЗУЕТ:
- Resource: u/theatmacreator/baserow_api
- External: Baserow API (https://content.nicksenin.com/api/database/rows/table/747/)
"""
import wmill
import requests
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


def main(**kwargs) -> dict:
    """
    Получает список всех жанров из Baserow.

    @return Список жанров с ID, названием и промптом
    """
    baserow_token = get_baserow_token()

    url = "https://content.nicksenin.com/api/database/rows/table/747/?user_field_names=true"

    headers = {
        "Authorization": f"Token {baserow_token}",
        "Content-Type": "application/json",
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    data = response.json()

    genres = []
    for row in data.get("results", []):
        genres.append({
            "id": row.get("id"),
            "name": row.get("Жанр", ""),
            "prompt": row.get("Промпт/процесс для картинки", ""),
        })

    return {"genres": genres}
