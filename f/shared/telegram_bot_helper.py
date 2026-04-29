"""
Хелпер для создания Telegram webhook-бота под Windmill GitSync.

Основано на текущем сетапе из диалога:
- Входящие апдейты Telegram должны приходить на HTTP Route Windmill.
- В route должен быть включён `wrap_body: true`, иначе апдейт часто приходит в "не том" формате.
- Webhook в Telegram должен указывать на публичный endpoint Windmill вида:
  `{BASE_URL}/api/r/<route_path>`
  Пример: `{BASE_URL}/api/r/telegram/content_forge_bot`

⚠️ Важно про токен:
Не записывайте токены в репозиторий. Этот хелпер по умолчанию НЕ создаёт resource.yaml с токеном.
Секреты лучше хранить как ресурсы/секреты в Windmill (а в git — только schema/resource-type).

⚠️ Важно про HTTP Route:
На некоторых инстансах HTTP Routes можно синхронизировать из YAML, на некоторых — нужно создать route в UI.
Этот хелпер создаёт route YAML в папке бота (как "инфраструктурный" файл) и может обновить `http_routes.yaml`
только как справочник (в вашем `wmill.yaml` root-файлы не включены, так что он не будет пушиться, если не поменять includes).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import requests


def _repo_root() -> Path:
    """
    Вычисляем корень репозитория относительно этого файла (f/shared/telegram_bot_helper.py).
    """
    p = Path(__file__).resolve()
    # .../f/shared/telegram_bot_helper.py -> .../f/shared -> .../f -> repo root
    try:
        return p.parents[2]
    except Exception:
        return Path.cwd()


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _run_cli(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True)


def create_bot_script(
    project_folder: str,
    bot_name: str,
    resource_path: str
) -> str:
    """
    Создаёт скрипт-обработчик для Telegram webhook.

    Ключевые моменты из диалога:
    - `wmill` должен быть в зависимостях, иначе скрипт может не стартовать на воркере.
    - payload должен парситься устойчиво (dict/str/bytes + wrap_body).
    """

    script_content = f'''"""
{bot_name} — Telegram webhook handler.

Resource: {resource_path}
HTTP Route path (рекомендация): telegram/{bot_name}
Webhook URL (рекомендация): {{BASE_URL}}/api/r/telegram/{bot_name}
"""
# /// script
# dependencies = [
#   "wmill",
#   "requests>=2.32.0"
# ]
# ///

from __future__ import annotations

import json
from typing import Any, Optional

import requests
import wmill


def _normalize_update(update: Any, body: Any) -> dict:
    data = body if body is not None else update
    if data is None:
        return {{}}

    if isinstance(data, (bytes, bytearray)):
        try:
            data = data.decode("utf-8")
        except Exception:
            data = data.decode("utf-8", errors="replace")

    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            return {{}}

    if isinstance(data, dict):
        # при wrap_body update может быть внутри ключа body
        if "message" not in data and isinstance(data.get("body"), dict):
            inner = data.get("body")
            if isinstance(inner, dict):
                return inner
        return data

    return {{}}


def _extract_message_and_chat(update_data: dict) -> tuple[dict, Optional[int]]:
    message: dict = (
        update_data.get("message")
        or update_data.get("edited_message")
        or (update_data.get("callback_query") or {{}}).get("message")
        or {{}}
    )
    chat_id = (message.get("chat") or {{}}).get("id")
    return (message, chat_id) if isinstance(chat_id, int) else (message, None)


def main(update: dict = None, body: dict = None) -> dict:
    telegram = wmill.get_resource("{resource_path}")
    token = telegram["token"]

    update_data = _normalize_update(update=update, body=body)
    message, chat_id = _extract_message_and_chat(update_data)

    text = message.get("text", "") if isinstance(message, dict) else ""
    caption = message.get("caption", "") if isinstance(message, dict) else ""
    idea = (text or caption or "").strip()

    if (text or "").strip().startswith("/start"):
        reply_text = (
            "Привет! Пришли идею текстом — я подтвержу получение. "
            "Можно прислать фото с подписью — я возьму подпись как идею."
        )
    elif idea:
        reply_text = f"✅ Получено:\\n\\n{{idea}}"
    else:
        reply_text = "Я получил сообщение, но не вижу текста идеи. Пришли идею текстом."

    if chat_id is not None:
        url = f"https://api.telegram.org/bot{{token}}/sendMessage"
        try:
            requests.post(url, json={{"chat_id": chat_id, "text": reply_text}}, timeout=5)
        except Exception:
            pass

    return {{
        "idea": idea,
        "chat_id": chat_id,
        "reply_text": reply_text,
    }}
'''

    script_rel = f"f/{project_folder}/{bot_name}.py"
    full_path = _repo_root() / script_rel
    _write_text(full_path, script_content)
    return script_rel


def create_flow(project_folder: str, bot_name: str) -> str:
    """Создаёт flow для обработки webhook."""

    flow_content = f'''summary: Telegram Webhook handler for {bot_name}
description: >
  Обрабатывает входящие сообщения от Telegram бота {bot_name}.

value:
  modules:
    - id: handle_update
      value:
        type: script
        path: f/{project_folder}/{bot_name}
      inputs:
        update: ${{inputs}}

schema:
  $schema: 'https://json-schema.org/draft/2020-12/schema'
  type: object
  properties: {{}}

ws_error_handler_muted: false
'''

    flow_rel = f"f/{project_folder}/{bot_name}__flow/flow.yaml"
    full_path = _repo_root() / flow_rel
    _write_text(full_path, flow_content)

    return flow_rel


def create_http_routes(project_folder: str, bot_name: str) -> list[str]:
    """
    Создаёт локальные route YAML файлы:
    - `f/<project>/<bot_name>.route.yaml` (удобно как "плоский" шаблон)
    - `f/<project>/<bot_name>/h.route.yaml` (как infra-файл внутри проекта)

    Важно: `wrap_body: true` обязателен для стабильной обработки payload.
    """

    route_content_flat = f'''path: telegram/{bot_name}
method: POST
summary: Telegram Webhook for {bot_name}
description: Receives updates from Telegram bot
script_path: f/{project_folder}/{bot_name}
extra:
  wrap_body: true
auth:
  kind: none
'''

    route_content_folder = f'''http_routes:
  - path: telegram/{bot_name}
    method: POST
    summary: Telegram Webhook for {bot_name}
    description: Receives updates from Telegram bot
    script_path: f/{project_folder}/{bot_name}
    extra:
      wrap_body: true
    auth:
      kind: none
'''

    root = _repo_root()
    flat_rel = f"f/{project_folder}/{bot_name}.route.yaml"
    folder_rel = f"f/{project_folder}/{bot_name}/h.route.yaml"
    _write_text(root / flat_rel, route_content_flat)
    _write_text(root / folder_rel, route_content_folder)
    return [flat_rel, folder_rel]


def create_resource_type(
    bot_name: str,
    user_folder: str = "theatmacreator"
) -> str:
    """Создаёт resource-type.yaml для токена бота."""

    resource_content = f'''description: Telegram bot token for {bot_name}
properties:
  token:
    type: string
    description: Bot token from @BotFather
    required: true
resource_type: http/generic
'''

    resource_rel = f"u/{user_folder}/{bot_name}.resource-type.yaml"
    _write_text(_repo_root() / resource_rel, resource_content)
    return resource_rel


def create_resource_example(
    bot_name: str,
    bot_token: str,
    user_folder: str = "theatmacreator"
) -> str:
    """
    Создаёт пример ресурса с токеном.

    ⚠️ По умолчанию лучше НЕ вызывать (не коммитить токены в git).
    """

    resource_content = f'''description: Telegram bot token for {bot_name}
value:
  token: {bot_token}
resource_type: http/generic
'''

    resource_rel = f"u/{user_folder}/{bot_name}.resource.yaml"
    _write_text(_repo_root() / resource_rel, resource_content)
    return resource_rel


def test_bot(
    webhook_url: str,
    test_message: str = "test_message"
) -> dict:
    """Тестирует бот отправкой тестового сообщения."""

    test_payload = {
        "update_id": 999999,
        "message": {
            "message_id": 1,
            "from": {
                "id": 123456,
                "is_bot": False,
                "first_name": "Test",
                "username": "test_user"
            },
            "chat": {
                "id": 123456,
                "first_name": "Test",
                "username": "test_user",
                "type": "private"
            },
            "date": 1704067200,
            "text": test_message
        }
    }

    try:
        response = requests.post(webhook_url, json=test_payload, timeout=10)

        if response.status_code == 200:
            return {
                "success": True,
                "status_code": response.status_code,
                "response": response.json(),
                "message": "✅ Бот отвечает корректно"
            }
        else:
            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.text,
                "message": f"❌ Ошибка HTTP {response.status_code}"
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"❌ Ошибка подключения: {str(e)}"
        }


def get_webhook_info(bot_token: str) -> dict:
    """Получает информацию о webhook из Telegram."""

    try:
        response = requests.get(
            f"https://api.telegram.org/bot{bot_token}/getWebhookInfo",
            timeout=10
        )

        data = response.json()

        if data.get('ok'):
            result = data.get('result', {})
            return {
                "success": True,
                "url": result.get('url'),
                "pending_updates": result.get('pending_update_count', 0),
                "last_error": result.get('last_error_message'),
                "connected": result.get('pending_update_count', 0) == 0
            }
        else:
            return {
                "success": False,
                "error": data.get('description', 'Unknown error')
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def sync_to_windmill() -> bool:
    """Синхронизирует изменения с Windmill."""
    root = _repo_root()
    result = _run_cli(["wmill", "sync", "push", "--yes"], cwd=root)
    return result.returncode == 0


def set_telegram_webhook(
    bot_token: str,
    route_path: str,
    base_url: str = "https://hub.nicksenin.com"
) -> bool:
    """Устанавливает webhook в Telegram."""
    route_path = route_path.lstrip("/")
    webhook_url = f"{base_url.rstrip('/')}/api/r/{route_path}"
    response = requests.post(
        f"https://api.telegram.org/bot{bot_token}/setWebhook",
        data={"url": webhook_url},
        timeout=10,
    )
    data = response.json()
    return bool(data.get("ok"))


def main(
    project_folder: str,
    bot_name: str,
    bot_token: str | None = None,
    user_folder: str = "theatmacreator",
    auto_test: bool = True,
    base_url: str = "https://hub.nicksenin.com",
    write_resource_value: bool = False,
    set_webhook: bool = True,
    do_sync_push: bool = True
) -> dict:
    """
    Создаёт полный Telegram бот на Windmill.

    @param project_folder Папка проекта (например: prj_content_forge)
    @param bot_name Имя бота (например: content_forge_bot)
    @param bot_token Токен бота от @BotFather (опционально — нужен для setWebhook/проверок)
    @param user_folder Папка пользователя (например: theatmacreator)
    @param auto_test Запустить автоматическое тестирование
    @param base_url Базовый URL Windmill instance
    @param write_resource_value Если True — запишет resource.yaml с токеном в репозиторий (не рекомендуется)
    @param set_webhook Если True — попытается выставить webhook в Telegram на /api/r/<route_path>
    @param do_sync_push Если True — выполнит `wmill sync push --yes`
    @return Результат создания
    """

    result = {
        "steps": [],
        "success": False,
        "files": [],
        "tests": {}
    }

    # Формируем путь к ресурсу
    resource_path = f"u/{user_folder}/{bot_name}"

    # 1. Создаём resource-type
    resource_type_path = create_resource_type(bot_name, user_folder)
    result["files"].append(resource_type_path)
    result["steps"].append(f"✅ Resource-type создан: {resource_type_path}")

    # 2. (Опционально) создаём пример ресурса с токеном (НЕ рекомендуется для git)
    if write_resource_value and bot_token:
        resource_path_yaml = create_resource_example(bot_name, bot_token, user_folder)
        result["files"].append(resource_path_yaml)
        result["steps"].append(f"⚠️ Ресурс с токеном записан в repo: {resource_path_yaml}")
    else:
        result["steps"].append("✅ Пропущено создание resource.yaml с токеном (безопаснее для git)")

    # 3. Создаём скрипт
    script_path = create_bot_script(project_folder, bot_name, resource_path)
    result["files"].append(script_path)
    result["steps"].append(f"✅ Скрипт создан: {script_path}")

    # 4. Создаём flow
    flow_path = create_flow(project_folder, bot_name)
    result["files"].append(flow_path)
    result["steps"].append(f"✅ Flow создан: {flow_path}")

    # 5. Создаём HTTP Route YAML (локально)
    route_files = create_http_routes(project_folder, bot_name)
    result["files"].extend(route_files)
    result["steps"].append(f"📄 Route YAML создан: {', '.join(route_files)}")

    # 6. Генерируем метаданные только для созданного скрипта
    root = _repo_root()
    md = _run_cli(["wmill", "script", "generate-metadata", script_path, "--yes"], cwd=root)
    if md.returncode == 0:
        result["steps"].append("✅ Метаданные сгенерированы")
    else:
        result["steps"].append(f"❌ Ошибка generate-metadata: {md.stderr.strip() or md.stdout.strip()}")

    # 7. Синхронизируем (опционально)
    if do_sync_push:
        if sync_to_windmill():
            result["steps"].append("✅ Синхронизировано с Windmill (sync push)")
        else:
            result["steps"].append("❌ Ошибка синхронизации (sync push)")
            return result

    # 8. Выставляем webhook в Telegram на /api/r/... (опционально)
    route_path = f"telegram/{bot_name}"
    webhook_url = f"{base_url.rstrip('/')}/api/r/{route_path}"
    if set_webhook:
        if not bot_token:
            result["steps"].append("⚠️ setWebhook пропущен: не передан bot_token")
        else:
            ok = set_telegram_webhook(bot_token=bot_token, route_path=route_path, base_url=base_url)
            result["steps"].append("✅ Webhook выставлен в Telegram" if ok else "❌ Не удалось выставить webhook в Telegram")

    result["steps"].append(f"🔗 Рекомендуемый webhook URL: {webhook_url}")

    # 9. Автоматическое тестирование (опционально)
    if auto_test:
        result["steps"].append("🧪 Запуск автоматического тестирования...")

        # Тестируем HTTP endpoint
        test_result = test_bot(webhook_url)
        result["tests"]["http_test"] = test_result
        result["steps"].append(test_result["message"])

        # Проверяем webhook info (если есть токен)
        if bot_token:
            webhook_info = get_webhook_info(bot_token)
            result["tests"]["webhook_info"] = webhook_info

            if webhook_info.get("success"):
                if webhook_info.get("connected"):
                    result["steps"].append("✅ Telegram webhook подключён (pending_updates=0)")
                else:
                    result["steps"].append(f"⚠️ Telegram webhook: {webhook_info.get('last_error', 'pending updates')}")
            else:
                result["steps"].append(f"⚠️ Не удалось проверить webhook: {webhook_info.get('error')}")

    result["success"] = True
    return result
