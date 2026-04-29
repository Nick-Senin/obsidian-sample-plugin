from __future__ import annotations

import re

import requests
import wmill


PASTEBIN_API_POST_URL = "https://pastebin.com/api/api_post.php"


def _is_pastebin_error(text: str) -> bool:
    return bool(re.match(r"^Bad API request", text.strip()))


def main(
    text: str,
    title: str | None = None,
    format: str = "text",
    expire: str = "N",
    privacy: int = 1,
    dev_key_variable_path: str = "u/theatmacreator/pastebin_dev_key",
) -> dict:
    """
    SEND_TO_PASTEBIN - создаёт unlisted paste в Pastebin по API.

    Ключ API берётся из secret variable в Windmill (wmill.get_variable).

    @param text Текст для вставки в Pastebin
    @param title Заголовок пасты (опционально)
    @param format Формат (api_paste_format), по умолчанию "text"
    @param expire Срок жизни (api_paste_expire_date), по умолчанию "N" (never)
    @param privacy Уровень приватности (api_paste_private): 0=public, 1=unlisted, 2=private
    @param dev_key_variable_path Путь к secret variable c api_dev_key
    @return JSON с ссылкой на pastebin
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text is required")

    try:
        dev_key = wmill.get_variable(dev_key_variable_path)
    except Exception as e:
        msg = str(e)
        if "Variable" in msg and "not found" in msg:
            raise RuntimeError(
                f"Pastebin dev key variable not found: {dev_key_variable_path}. "
                f"Create it as a *secret variable* in Windmill, or run "
                f"`f/transformations/pastebin/setup_pastebin_dev_key` once to create it."
            )
        raise
    if not isinstance(dev_key, str) or not dev_key.strip():
        raise ValueError(f"Pastebin dev key is empty (variable: {dev_key_variable_path})")

    payload: dict[str, str] = {
        "api_option": "paste",
        "api_dev_key": dev_key.strip(),
        "api_paste_code": text,
        "api_paste_private": str(int(privacy)),
        "api_paste_expire_date": expire,
        "api_paste_format": format,
    }
    if isinstance(title, str) and title.strip():
        payload["api_paste_name"] = title.strip()

    try:
        resp = requests.post(PASTEBIN_API_POST_URL, data=payload, timeout=30)
        status_code = resp.status_code
        body = (resp.text or "").strip()
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Pastebin request failed: {type(e).__name__}")

    # Pastebin часто возвращает текстовую ошибку с 200, но иногда может отвечать 4xx/5xx.
    if status_code >= 400:
        raise RuntimeError(f"Pastebin HTTP error: {status_code}: {body[:500]}")

    if _is_pastebin_error(body):
        raise RuntimeError(body)

    return {"url": body}
