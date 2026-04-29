# /// script
# dependencies = [
#     "telethon>=1.42.0",
#     "wmill"
# ]
# ///

"""
Скрипт для авторизации Telegram клиента через Telethon.
После успешной авторизации сохраняет session файл в ресурс Windmill.

Запусти этот скрипт один раз, чтобы авторизовать клиент.
"""
import wmill
import asyncio
import tempfile
import os
import base64
from pathlib import Path

from telethon import TelegramClient
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    PhoneCodeHashEmptyError,
)


def main(phone: str = None, force_sms: bool = False) -> dict:
    """
    Авторизует Telegram клиент.

    @param phone Номер телефона (опционально, берётся из ресурса)
    @param force_sms Принудительно отправить код по SMS
    @return Результат авторизации
    """
    telegram_client_api = wmill.get_resource("u/theatmacreator/telegram_client_api")

    api_id = int(telegram_client_api['api_id'])
    api_hash = telegram_client_api['api_hash']
    phone = phone or telegram_client_api['phone']

    # Используем временную директорию для session
    session_dir = tempfile.gettempdir()
    session_name = f"tg_session_{phone.replace('+', '')}"
    session_path = os.path.join(session_dir, session_name)

    client = TelegramClient(session_path, api_id, api_hash)

    async def authorize():
        await client.connect()

        try:
            if not await client.is_user_authorized():
                # Первый этап: отправка кода
                print(f"Отправка кода на номер {phone} (SMS={force_sms})...")
                result = await client.send_code_request(phone, force_sms=force_sms)
                
                # Диагностика типа отправки
                code_type = "Неизвестно"
                if hasattr(result, 'type'):
                    code_type = str(result.type)
                
                next_code_type = "Нет"
                timeout = 0
                if hasattr(result, 'next_type'):
                    next_code_type = str(result.next_type)
                if hasattr(result, 'timeout'):
                    timeout = result.timeout

                message = (
                    f"Код отправлен. Тип: {code_type}. "
                    f"Можно запросить другой тип ({next_code_type}) через {timeout} сек.\n"
                    "Перезапусти скрипт с параметрами code='12345' и phone_code_hash из ответа."
                )

                return {
                    "status": "code_sent",
                    "phone": phone,
                    "phone_code_hash": result.phone_code_hash,
                    "sent_type": code_type,
                    "next_type": next_code_type,
                    "timeout": timeout,
                    "message": message,
                }

            # Уже авторизован - сохраняем session
            session_file = Path(session_path + ".session")
            if not session_file.exists():
                return {"error": "Session file not found"}

            session_data = session_file.read_bytes()
            session_b64 = base64.b64encode(session_data).decode("utf-8")

            return {
                "status": "authorized",
                "session_b64": session_b64,
                "message": "Session saved! Добавь это в resource как поле 'session_data'",
            }
        finally:
            await client.disconnect()

    return asyncio.run(authorize())


def main_with_code(code: str, phone_code_hash: str = None, phone: str = None) -> dict:
    """
    Второй этап авторизации: ввод кода.

    @param code Код из Telegram
    @param phone_code_hash Хэш кода из первого шага
    @param phone Номер телефона
    @return Результат с session данными
    """
    telegram_client_api = wmill.get_resource("u/theatmacreator/telegram_client_api")

    api_id = int(telegram_client_api['api_id'])
    api_hash = telegram_client_api['api_hash']
    phone = phone or telegram_client_api['phone']

    session_dir = tempfile.gettempdir()
    session_name = f"tg_session_{phone.replace('+', '')}"
    session_path = os.path.join(session_dir, session_name)

    client = TelegramClient(session_path, api_id, api_hash)

    async def sign_in():
        await client.connect()

        try:
            await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
        except SessionPasswordNeededError:
            return {
                "status": "2fa_required",
                "message": "Требуется двухфакторная аутентификация. Перезапусти с password='ваш_пароль'",
            }
        except (PhoneCodeInvalidError, PhoneCodeExpiredError, PhoneCodeHashEmptyError) as e:
            return {"status": "code_error", "message": str(e)}
        finally:
            await client.disconnect()

        # Сохраняем session
        session_file = Path(session_path + ".session")
        if not session_file.exists():
            return {"status": "error", "message": "Session file not found"}

        session_data = session_file.read_bytes()
        session_b64 = base64.b64encode(session_data).decode("utf-8")

        return {
            "status": "success",
            "session_b64": session_b64,
            "message": (
                "Session создан! Добавь в ресурс telegram_client_api поле: "
                f"session_data='{session_b64[:100]}...'"
            ),
            "session_length": len(session_b64),
        }

    return asyncio.run(sign_in())


def main_with_password(password: str, phone: str = None, code: str = None) -> dict:
    """
    Третий этап авторизации: двухфакторная аутентификация.

    @param password Пароль 2FA
    @param phone Номер телефона
    @param code Код из Telegram
    @return Результат с session данными
    """
    telegram_client_api = wmill.get_resource("u/theatmacreator/telegram_client_api")

    api_id = int(telegram_client_api['api_id'])
    api_hash = telegram_client_api['api_hash']
    phone = phone or telegram_client_api['phone']

    session_dir = tempfile.gettempdir()
    session_name = f"tg_session_{phone.replace('+', '')}"
    session_path = os.path.join(session_dir, session_name)

    client = TelegramClient(session_path, api_id, api_hash)

    async def sign_in_with_password():
        await client.connect()

        try:
            await client.sign_in(password=password)
        except Exception as e:
            raise Exception(f"Ошибка ввода пароля: {e}")
        finally:
            await client.disconnect()

        # Сохраняем session
        session_file = Path(session_path + ".session")
        if not session_file.exists():
            return {"status": "error", "message": "Session file not found"}

        session_data = session_file.read_bytes()
        session_b64 = base64.b64encode(session_data).decode("utf-8")

        return {
            "status": "success",
            "session_b64": session_b64,
            "message": (
                "Session создан с 2FA! Добавь в ресурс telegram_client_api поле: "
                f"session_data='{session_b64[:100]}...'"
            ),
            "session_length": len(session_b64),
        }

    return asyncio.run(sign_in_with_password())


# Для первого запуска - отправка кода
def main_1(force_sms: bool = False) -> dict:
    return main(force_sms=force_sms)


# Для второго запуска - ввод кода
def main_2(code: str, phone_code_hash: str = None) -> dict:
    return main_with_code(code, phone_code_hash=phone_code_hash)


# Для третьего запуска - ввод пароля 2FA
def main_3(password: str) -> dict:
    return main_with_password(password)
