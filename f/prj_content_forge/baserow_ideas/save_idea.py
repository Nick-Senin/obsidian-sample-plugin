"""
Скрипт для записи идеи поста в Baserow.

Отправляет идею в таблицу ideas (table/748) с полем "Описание".
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


def main(idea: str) -> dict:
    """
    Записывает идею в таблицу Baserow.

    @param idea Текст идеи для поста
    @return Результат запроса к Baserow
    """
    baserow_token = get_baserow_token()

    url = "https://content.nicksenin.com/api/database/rows/table/748/?user_field_names=true"

    headers = {
        "Authorization": f"Token {baserow_token}",
        "Content-Type": "application/json",
    }

    payload = {
        "Описание": idea
    }

    response = requests.post(
        url,
        params={"user_field_names": "true"},
        json=payload,
        headers=headers
    )
    response.raise_for_status()

    return response.json()
