"""
Проверяет, что Telegram session авторизован.
"""
import wmill
import asyncio
import tempfile
import os
import base64
import json
import urllib.request
from pathlib import Path
from urllib.parse import quote
from telethon import TelegramClient


def load_resource(path: str) -> dict:
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
        req = urllib.request.Request(
            f"{base_url}/api/w/{workspace}/resources/get_value/{encoded_path}",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.load(response)

def main() -> dict:
    """Проверка авторизации Telegram"""
    telegram_client_api = load_resource("u/theatmacreator/telegram_client_api")

    api_id = int(telegram_client_api['api_id'])
    api_hash = telegram_client_api['api_hash']
    phone = telegram_client_api['phone']

    phone_slug = phone.replace("+", "")
    job_suffix = os.environ.get("WM_JOB_ID") or str(os.getpid())
    session_dir = tempfile.mkdtemp(prefix=f"tg_session_{phone_slug}_{job_suffix}_")
    session_path = os.path.join(session_dir, "session")
    session_file = Path(session_path + ".session")

    # Для проверки всегда создаём отдельную копию session из ресурса.
    if 'session_data' in telegram_client_api and telegram_client_api['session_data']:
        session_b64 = telegram_client_api['session_data']
        session_data = base64.b64decode(session_b64)
        session_file.write_bytes(session_data)

    async def check_auth():
        client = TelegramClient(session_path, api_id, api_hash)
        await client.connect()
        
        is_authorized = await client.is_user_authorized()
        
        if is_authorized:
            me = await client.get_me()
            result = {
                "status": "success",
                "authorized": True,
                "phone": phone,
                "user_id": me.id,
                "username": me.username,
                "first_name": me.first_name
            }
        else:
            result = {
                "status": "error",
                "authorized": False,
                "message": "Session not authorized"
            }
        
        await client.disconnect()
        return result

    return asyncio.run(check_auth())
