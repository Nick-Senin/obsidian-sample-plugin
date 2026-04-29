"""
Общие утилиты для работы с LLM (OpenRouter) в Windmill.

Централизует логику инициализации клиента, типы и обработку ошибок.

ВАЖНО: Импорт openai делается внутри функций, чтобы избежать проблем
с зависимостями при импорте этого модуля.
"""
import time
from typing import Optional, TypedDict
import json
import os
from urllib.parse import quote
from urllib.request import Request, urlopen
from openai import OpenAI

try:
    import wmill  # type: ignore
except Exception:  # pragma: no cover
    class _WmillStub:
        def get_variable(self, *_args, **_kwargs):
            raise RuntimeError("wmill is not available")

        def get_resource(self, *_args, **_kwargs):
            raise RuntimeError("wmill is not available")

    wmill = _WmillStub()  # type: ignore


class OpenRouterResource(TypedDict):
    """Единый TypedDict для ресурса OpenRouter."""
    apiKey: str
    X_Title: str


def _get_variable_compat(path: str) -> str:
    """Читает secret variable и fallback'ом идёт в REST API, если SDK не сработал."""
    try:
        return wmill.get_variable(path)
    except Exception:
        base_url = os.environ.get("BASE_INTERNAL_URL") or os.environ.get("BASE_URL")
        workspace = os.environ.get("WM_WORKSPACE")
        token = os.environ.get("WM_TOKEN")
        if not base_url or not workspace or not token:
            raise

        encoded_path = quote(path, safe="/")
        url = f"{base_url}/api/w/{workspace}/variables/get/{encoded_path}"
        request = Request(url, headers={"Authorization": f"Bearer {token}"})
        with urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
        if not body:
            return ""
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return body
        if isinstance(payload, dict) and "value" in payload:
            return payload["value"] or ""
        if isinstance(payload, str):
            return payload
        raise ValueError(f"Unexpected variable payload for {path}: {type(payload).__name__}")


def _resolve_secret_refs(value):
    """Рекурсивно разворачивает $var: ссылки внутри resource payload."""
    if isinstance(value, str) and value.startswith("$var:"):
        return _get_variable_compat(value[len("$var:"):])
    if isinstance(value, dict):
        return {k: _resolve_secret_refs(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_secret_refs(item) for item in value]
    return value


def create_llm_client(resource: OpenRouterResource) -> OpenAI:
    """
    Создает и возвращает настроенный OpenAI клиент для OpenRouter.

    @param resource Ресурс OpenRouter с apiKey и X_Title
    @return Настроенный OpenAI клиент
    """
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=resource["apiKey"],
        default_headers={
            "HTTP-Referer": "https://hub.nicksenin.com",
            "X-Title": resource.get("X_Title") or resource.get("X-Title") or "Windmill",
        }
    )


def get_resource_compat(path: str) -> dict:
    """
    Читает ресурс с fallback на /get_value, если /get_value_interpolated недоступен.
    Это нужно для инстансов, где get_resource() падает с 404 на interpolated endpoint.
    """
    try:
        return wmill.get_resource(path)
    except Exception as e:
        base_url = os.environ.get("BASE_INTERNAL_URL") or os.environ.get("BASE_URL")
        workspace = os.environ.get("WM_WORKSPACE")
        token = os.environ.get("WM_TOKEN")
        if not base_url or not workspace or not token:
            raise

        encoded_path = quote(path, safe="/")
        url = f"{base_url}/api/w/{workspace}/resources/get_value/{encoded_path}"
        request = Request(url, headers={"Authorization": f"Bearer {token}"})
        with urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
        value = json.loads(body) if body else {}
        return _resolve_secret_refs(value)


def generate_completion(
    client: OpenAI,
    prompt: str,
    model: str,
    temperature: float = 0.7,
    max_tokens: Optional[int] = 300,
    max_retries: int = 3
) -> str:
    """
    Обертка над chat.completions с автоматическими повторами при ошибках.

    @param client Настроенный OpenAI клиент
    @param prompt Пользовательский промпт
    @param model Модель для использования
    @param temperature Температура генерации (по умолчанию 0.7)
    @param max_tokens Максимальное количество токенов (по умолчанию 300)
    @param max_retries Количество попыток при ошибке (по умолчанию 3)
    @return Сгенерированный текст
    @raise ValueError Если получен пустой ответ после всех попыток
    """
    messages = [{"role": "user", "content": prompt}]

    for attempt in range(max_retries):
        try:
            create_kwargs = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
            }
            if max_tokens is not None:
                create_kwargs["max_tokens"] = max_tokens

            response = client.chat.completions.create(**create_kwargs)

            if not response.choices:
                raise ValueError("Нет ответов от модели")

            content = response.choices[0].message.content

            if not content or not content.strip():
                raise ValueError("Получен пустой ответ от API")

            return content.strip()

        except Exception as e:
            if attempt == max_retries - 1:
                raise ValueError(
                    f"Не удалось получить ответ после {max_retries} попыток. Ошибка: {e}"
                )
            time.sleep(2)

    return ""  # Не должно доходить сюда


# Main функция (не используется, нужна для зависимостей Windmill)
def main():
    """Этот скрипт используется как общий модуль, не запускайте напрямую."""
    pass
