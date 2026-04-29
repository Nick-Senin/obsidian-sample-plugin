"""
GET_GENRE_IMAGE_PROMPT - получение промпта для картинки по жанру из Baserow

ЧТО ДЕЛАЕТ:
- Получает промпт из таблицы жанров (table/747) по genre_id
- Возвращает значение поля "Промпт/процесс для картинки"
- Возвращает значение поля "Модель для картинки" (если заполнено)
- Возвращает значение поля "Соотношение сторон для картинки" (если заполнено)

ГДЕ ИСПОЛЬЗУЕТСЯ:
- f/prj_content_forge/process_recording

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


def main(genre_id: str) -> dict:
    """
    Получает промпт для генерации изображения по жанру.

    @param genre_id ID жанра в Baserow
    @return Промпт и модель для генерации изображения
    """
    baserow_token = get_baserow_token()

    url = f"https://content.nicksenin.com/api/database/rows/table/747/{genre_id}/?user_field_names=true"

    headers = {
        "Authorization": f"Token {baserow_token}",
        "Content-Type": "application/json",
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    data = response.json()

    raw_model = data.get("Модель для картинки", "") or ""
    if isinstance(raw_model, dict):
        image_model = raw_model.get("value", "") or ""
    elif isinstance(raw_model, list) and raw_model and isinstance(raw_model[0], dict):
        image_model = raw_model[0].get("value", "") or ""
    else:
        image_model = str(raw_model) if raw_model is not None else ""

    raw_aspect_ratio = data.get("Соотношение сторон для картинки", "") or ""
    if isinstance(raw_aspect_ratio, dict):
        image_aspect_ratio = raw_aspect_ratio.get("value", "") or ""
    elif isinstance(raw_aspect_ratio, list) and raw_aspect_ratio and isinstance(raw_aspect_ratio[0], dict):
        image_aspect_ratio = raw_aspect_ratio[0].get("value", "") or ""
    else:
        image_aspect_ratio = str(raw_aspect_ratio) if raw_aspect_ratio is not None else ""

    return {
        "prompt": data.get("Промпт/процесс для картинки", ""),
        "image_model": image_model,
        "image_aspect_ratio": image_aspect_ratio,
    }
