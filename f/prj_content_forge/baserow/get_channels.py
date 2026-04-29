"""
GET_CHANNELS - получение списка каналов из Baserow

ЧТО ДЕЛАЕТ:
- Получает все записи из таблицы каналов (table/746)
- Возвращает список каналов с id, названием, адресом и статусом активности

ГДЕ ИСПОЛЬЗУЕТСЯ:
- OBS Recording Handler (локальный Python скрипт)
- Любые скрипты которым нужен список каналов

ИСПОЛЬЗУЕТ:
- Resource: u/theatmacreator/baserow_api
- External: Baserow API (https://content.nicksenin.com/api/database/rows/table/746/)
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


def main() -> dict:
    """
    Получает список всех каналов из Baserow.

    @return Список каналов с полями id, name, address, active
    """
    baserow_token = get_baserow_token()

    url = "https://content.nicksenin.com/api/database/rows/table/746/?user_field_names=true"

    headers = {
        "Authorization": f"Token {baserow_token}",
        "Content-Type": "application/json",
    }

    response = requests.get(
        url,
        params={"user_field_names": "true", "size": "100"},
        headers=headers
    )
    response.raise_for_status()

    data = response.json()

    channels = []
    for row in data.get("results", []):
        channels.append({
            "id": str(row.get("id", "")),
            "name": row.get("Name", ""),
            "address": row.get("Адрес", ""),
            "active": row.get("Active", False)
        })

    return {"channels": channels}
