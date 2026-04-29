#!/usr/bin/env python3
"""
ЛОКАЛЬНЫЙ скрипт для авторизации Telegram клиента.
Запусти это на СВОЁМ компьютере, а не в Windmill.

После успешной авторизации скопируй session_data в ресурс Windmill.

Установка зависимостей:
    pip install telethon

Использование:
    python LOCAL_authorize.py
"""

from telethon import TelegramClient
import base64
import os
import asyncio
import logging
from datetime import datetime

# Настройка логгирования
log_file = f"telegram_auth_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def main():
    logger.info("=" * 60)
    logger.info("ТЕЛЕГРАМ АВТОРИЗАЦИЯ - НАЧАЛО")
    logger.info(f"Лог-файл: {log_file}")
    logger.info("=" * 60)

    try:
        API_ID = int(input("Введите API_ID: "))
        logger.info(f"API_ID получен: {API_ID}")

        API_HASH = input("Введите API_HASH: ")
        logger.info(f"API_HASH получен: {API_HASH[:10]}... (скрыт)")

        PHONE = input("Введите номер телефона (с +, например +79831134634): ")
        logger.info(f"Номер телефона: {PHONE}")
    except Exception as e:
        logger.error(f"Ошибка при вводе данных: {e}", exc_info=True)
        return

    session_name = f"tg_session_{PHONE.replace('+', '')}"
    session_file = f"{session_name}.session"
    logger.info(f"Имя сессии: {session_name}")

    # Удаляем старую сессию если есть
    if os.path.exists(session_file):
        logger.info(f"Удаляю старую сессию: {session_file}")
        os.remove(session_file)
        journal_file = f"{session_name}.session-journal"
        if os.path.exists(journal_file):
            logger.info(f"Удаляю journal файл: {journal_file}")
            os.remove(journal_file)

    logger.info("Создаём TelegramClient...")
    try:
        client = TelegramClient(session_name, API_ID, API_HASH)
        logger.info("TelegramClient создан успешно")
    except Exception as e:
        logger.error(f"Ошибка при создании клиента: {e}", exc_info=True)
        return

    # Подключаемся
    logger.info("Подключаемся к Telegram...")
    try:
        await client.connect()
        logger.info("Подключение установлено успешно")
    except Exception as e:
        logger.error(f"Ошибка при подключении: {e}", exc_info=True)
        return

    # Проверяем авторизацию
    logger.info("Проверяем статус авторизации...")
    try:
        is_authorized = await client.is_user_authorized()
        logger.info(f"Статус авторизации: {is_authorized}")
    except Exception as e:
        logger.error(f"Ошибка при проверке авторизации: {e}", exc_info=True)
        return

    if is_authorized:
        logger.info("Уже авторизован!")
        print("\n✅ Уже авторизован!")
        try:
            me = await client.get_me()
            logger.info(f"Пользователь: {me.first_name} (@{me.username})")
            print(f"Авторизован как: {me.first_name} (@{me.username})")
        except Exception as e:
            logger.error(f"Ошибка при получении данных пользователя: {e}", exc_info=True)
    else:
        # Отправляем код
        logger.info(f"Отправляем код на номер {PHONE}...")
        print(f"\n➤ Отправляю код на номер {PHONE}...")
        print("➤ ПРОВЕРЬ TELEGRAM СЕЙЧАС!\n")

        try:
            result = await client.send_code_request(PHONE)
            logger.info(f"Код отправлен успешно!")
            logger.info(f"Тип результата: {type(result).__name__}")
            logger.info(f"phone_code_hash: {result.phone_code_hash[:30]}...")

            # Дополнительная информация о результате
            if hasattr(result, 'phone_code_hash'):
                logger.info(f"Полный phone_code_hash: {result.phone_code_hash}")
            if hasattr(result, 'type'):
                logger.info(f"Тип кода: {result.type}")

            print(f"✅ Код отправлен!")
            print(f"   phone_code_hash: {result.phone_code_hash[:30]}...")
            print(f"   type: {type(result).__name__}")
        except Exception as e:
            logger.error(f"Ошибка при отправке кода: {e}", exc_info=True)
            print(f"\n❌ Ошибка при отправке кода: {e}")
            print(f"   Детали в лог-файле: {log_file}")
            await client.disconnect()
            return

        code = input("\n➤ Введи код из Telegram: ")
        logger.info(f"Код получен от пользователя: {code}")

        try:
            logger.info("Пытаемся войти с кодом...")
            await client.sign_in(PHONE, code)
            logger.info("Вход выполнен успешно!")
            print("\n✅ Код принят!")
        except Exception as e:
            error_str = str(e)
            logger.error(f"Ошибка при входе: {error_str}", exc_info=True)
            print(f"\nОшибка: {error_str}")

            if "Session password needed" in error_str:
                logger.info("Требуется 2FA пароль")
                print("➤ Требуется двухфакторная аутентификация!")
                password = input("Введи пароль 2FA: ")
                logger.info("Пароль 2FA получен")

                try:
                    await client.sign_in(password=password)
                    logger.info("2FA пароль принят!")
                    print("\n✅ Пароль принят!")
                except Exception as e2:
                    logger.error(f"Ошибка при вводе 2FA: {e2}", exc_info=True)
                    raise
            else:
                raise

        try:
            me = await client.get_me()
            logger.info(f"Авторизация успешна! Пользователь: {me.first_name} (@{me.username})")
            print(f"\n✅ Авторизация успешна!")
            print(f"   Авторизован как: {me.first_name} (@{me.username})")
        except Exception as e:
            logger.error(f"Ошибка при получении данных после авторизации: {e}", exc_info=True)

    # Отключаемся
    logger.info("Отключаемся...")
    try:
        await client.disconnect()
        logger.info("Отключение выполнено")
    except Exception as e:
        logger.warning(f"Предупреждение при отключении: {e}")

    # Проверяем session файл
    logger.info(f"Проверяем наличие session файла: {session_file}")
    if not os.path.exists(session_file):
        logger.error(f"Session файл НЕ найден: {session_file}")
        print(f"\n❌ Ошибка: session файл не создан!")
        return

    # Читаем session файл
    logger.info("Читаем session файл...")
    try:
        with open(session_file, "rb") as f:
            session_data = f.read()
        logger.info(f"Session файл прочитан: {len(session_data)} байт")
    except Exception as e:
        logger.error(f"Ошибка при чтении session файла: {e}", exc_info=True)
        return

    # Кодируем в base64
    try:
        session_b64 = base64.b64encode(session_data).decode('utf-8')
        logger.info(f"Session закодирован в base64: {len(session_b64)} символов")
    except Exception as e:
        logger.error(f"Ошибка при кодировании: {e}", exc_info=True)
        return

    print(f"\n{'='*60}")
    print("SESSION DATA (base64):")
    print(f"{'='*60}")
    print(session_b64)
    print(f"{'='*60}")
    print(f"\nРазмер: {len(session_b64)} символов")

    # Сохраняем в файл
    output_file = "telegram_session.txt"
    try:
        with open(output_file, "w") as f:
            f.write(session_b64)
        logger.info(f"Session сохранён в {output_file}")
        print(f"\n✓ Session также сохранена в {output_file}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении в файл: {e}", exc_info=True)

    print("\nДалее:")
    print("1. Скопируй session_data выше")
    print("2. Открой ресурс u/theatmacreator/telegram_client_api в Windmill")
    print("3. Добавь поле 'session_data' со значением выше")
    print("4. Запусти: wmill sync push --yes")

    # Спрашиваем, удалить ли session файл
    delete = input("\nУдалить локальный session файл? (y/n): ").lower()
    if delete == 'y':
        os.remove(session_file)
        logger.info(f"Session файл удалён")
        print(f"✓ Локальный session файл удалён")

    logger.info("=" * 60)
    logger.info("ТЕЛЕГРАМ АВТОРИЗАЦИЯ - ЗАВЕРШЕНО УСПЕШНО")
    logger.info("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Прервано пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        print(f"\n❌ Критическая ошибка: {e}")
        print(f"   Детали в лог-файле: {log_file}")
