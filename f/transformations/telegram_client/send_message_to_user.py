"""
Отправка личного сообщения пользователю Telegram через Client API (MTProto).

Входные параметры:
- user_id: Telegram user_id получателя (опционально, если передан username)
- message: текст сообщения
- username: username получателя (опционально, fallback для резолва)

Использует ресурс Windmill:
- u/theatmacreator/telegram_client_api
  - api_id
  - api_hash
  - phone
  - session_data (base64, опционально, но обычно обязателен для неинтерактивного запуска)
"""

import asyncio
import base64
import os
import tempfile
from pathlib import Path
from urllib.parse import quote

import requests
import wmill
from telethon import TelegramClient


RESOURCE_PATH = "u/theatmacreator/telegram_client_api"
TELEGRAM_MESSAGE_LIMIT = 4096


def _load_resource(path: str) -> dict:
    """
    Читает ресурс через wmill.get_resource с fallback на /resources/get_value.
    """
    try:
        return wmill.get_resource(path)
    except Exception as exc:
        if "get_value_interpolated" not in str(exc):
            raise

        base_url = os.environ.get("BASE_INTERNAL_URL") or os.environ.get("BASE_URL")
        workspace = os.environ.get("WM_WORKSPACE")
        token = os.environ.get("WM_TOKEN")
        if not base_url or not workspace or not token:
            raise

        encoded_path = quote(path, safe="/")
        response = requests.get(
            f"{base_url}/api/w/{workspace}/resources/get_value/{encoded_path}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()


def _prepare_session_file(phone: str, session_b64: str | None) -> str:
    """
    Готовит уникальный для job путь к session-файлу Telethon и пишет session_data.
    """
    phone_slug = phone.replace("+", "")
    job_suffix = os.environ.get("WM_JOB_ID") or str(os.getpid())
    session_dir = tempfile.mkdtemp(prefix=f"tg_session_{phone_slug}_{job_suffix}_")
    session_path = os.path.join(session_dir, "session")
    session_file = Path(f"{session_path}.session")

    if session_b64:
        session_file.write_bytes(base64.b64decode(session_b64))

    return session_path


async def _resolve_recipient(
    client: TelegramClient,
    user_id: int | None,
    username: str | None,
):
    """
    Резолвит получателя через username (предпочтительно) и/или user_id.
    """
    errors: list[str] = []

    if username and username.strip():
        normalized = username.strip()
        if not normalized.startswith("@"):
            normalized = f"@{normalized}"

        try:
            return await client.get_input_entity(normalized), f"username:{normalized}"
        except Exception as exc:
            errors.append(f"username failed: {exc}")

        try:
            entity = await client.get_entity(normalized)
            return entity, f"username:{normalized}:get_entity"
        except Exception as exc:
            errors.append(f"username get_entity failed: {exc}")

    if user_id is not None:
        numeric_user_id = int(user_id)
        try:
            return await client.get_input_entity(numeric_user_id), f"user_id:{numeric_user_id}"
        except Exception as exc:
            errors.append(f"user_id failed: {exc}")

        try:
            await client.get_dialogs()
            return await client.get_input_entity(numeric_user_id), f"user_id:{numeric_user_id}:after_dialogs"
        except Exception as exc:
            errors.append(f"user_id after get_dialogs failed: {exc}")

    details = " | ".join(errors) if errors else "no identifiers provided"
    raise ValueError(
        "Could not resolve recipient. Provide a valid username (preferred) or ensure "
        "this account has already encountered the user before using user_id. "
        f"Details: {details}"
    )


def main(user_id: int | None = None, message: str = "", username: str | None = None) -> dict:
    """
    Отправляет личное сообщение пользователю, резолвя получателя по username/user_id.
    """
    if not message or not message.strip():
        raise ValueError("message must be a non-empty string")
    if user_id is None and not (username and username.strip()):
        raise ValueError("Provide either user_id or username")

    telegram_client_api = _load_resource(RESOURCE_PATH)

    try:
        api_id = int(telegram_client_api["api_id"])
        api_hash = str(telegram_client_api["api_hash"])
        phone = str(telegram_client_api["phone"])
    except KeyError as exc:
        raise ValueError(f"Missing key in resource {RESOURCE_PATH}: {exc}") from exc

    session_path = _prepare_session_file(phone, telegram_client_api.get("session_data"))
    text = message[:TELEGRAM_MESSAGE_LIMIT]

    async def _send() -> dict:
        client = TelegramClient(session_path, api_id, api_hash)
        try:
            await client.connect()
            if not await client.is_user_authorized():
                raise RuntimeError(
                    f"Telegram client is not authorized for {phone}. "
                    "Add valid session_data to the resource or authorize the session."
                )

            recipient, resolved_via = await _resolve_recipient(client, user_id, username)
            result = await client.send_message(entity=recipient, message=text, parse_mode="html")
            return {
                "ok": True,
                "to_user_id": int(user_id) if user_id is not None else None,
                "to_username": username.strip() if username else None,
                "resolved_via": resolved_via,
                "message_id": result.id,
                "sent_length": len(text),
                "truncated": len(message) > TELEGRAM_MESSAGE_LIMIT,
            }
        finally:
            await client.disconnect()

    return asyncio.run(_send())
