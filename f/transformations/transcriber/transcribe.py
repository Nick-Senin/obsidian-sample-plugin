"""
TRANSCRIBE - транскрибация аудио/видео через Deepgram API

ЧТО ДЕЛАЕТ:
- Преобразует аудио/видео в текст с помощью Deepgram Whisper
- Поддерживает диаризацию (определение говорящих)
- Работает с URL и base64-кодированными файлами
- Возвращает текст + метаданные (длительность, язык, модель)

ГДЕ ИСПОЛЬЗУЕТСЯ:
- f/prj_content_forge/flows/create_posts_from_transcript__flow

ИСПОЛЬЗУЕТ:
- Resource: u/theatmacreator/deepgram
- External: Deepgram API (https://api.deepgram.com/v1/listen)
"""
import base64
import json
import time
import typing as t
from urllib.parse import quote, urlparse

import requests
import wmill


def _validate_url(url: str) -> bool:
    """Проверяет валидность URL."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def _is_deepgram_base64(data: str) -> bool:
    """
    Проверяет, является ли строка base64-кодированными данными от Windmill.

    Windmill может передавать файлы как base64 строки с префиксом.
    """
    # Если есть префикс Windmill или это выглядит как base64
    if data.startswith("data:"):
        return True

    # Проверяем, что строка не слишком коротка и содержит только base64 символы
    if len(data) < 100:
        return False

    try:
        # Пробуем декодировать, чтобы проверить валидность
        decoded = base64.b64decode(data, validate=True)
        # Декодированные данные не должны быть валидным ASCII текстом
        # (иначе это не аудио-файл)
        try:
            decoded.decode('ascii')
            # Если декодируется как ASCII, это вряд ли аудио
            return False
        except UnicodeDecodeError:
            # Не декодируется как ASCII - вероятно бинарные данные (аудио)
            return True
    except Exception:
        return False


def _process_audio_data(audio_input: str) -> tuple[str, str]:
    """
    Определяет тип входных данных и подготавливает их для Deepgram.

    @param audio_input URL или base64-кодированные данные аудио
    @return Кортеж (url_or_content, content_type) где:
            - url_or_content: URL для remote или сырые данные для multipart
            - content_type: "url" или "multipart"
    """
    # Сначала проверяем URL
    if _validate_url(audio_input):
        return audio_input, "url"

    # Проверяем base64
    if _is_deepgram_base64(audio_input):
        # Windmill может передавать префикс, убираем его
        if audio_input.startswith("data:"):
            # Формат: "data:audio/mpeg;base64,..."
            parts = audio_input.split(",", 1)
            if len(parts) == 2:
                return base64.b64decode(parts[1]), "multipart"
        else:
            return base64.b64decode(audio_input), "multipart"

    # Если ни URL ни base64 - попробуем как URL (может быть относительным или с протоколом)
    return audio_input, "url"


def _extract_audio_input(
    *,
    audio_file: t.Any | None,
    audio_url: str | None,
) -> str:
    """
    Нормализует вход для транскрибации из App:
    - `audio_url`: строка (если указана и не пустая)
    - `audio_file`: результат File input из App editor (обычно array[{name, data}])
    """
    if isinstance(audio_url, str) and audio_url.strip():
        return audio_url.strip()

    # File input из Apps возвращает array[{ name, data }]
    if audio_file is None:
        raise ValueError("Нужно указать URL или загрузить файл")

    if isinstance(audio_file, list) and audio_file:
        first = audio_file[0]
        if isinstance(first, dict):
            data = first.get("data")
            if isinstance(data, str) and data.strip():
                return data.strip()

    # На всякий случай поддержим и dict{data}
    if isinstance(audio_file, dict):
        data = audio_file.get("data")
        if isinstance(data, str) and data.strip():
            return data.strip()

    raise ValueError("Не удалось прочитать файл из File input (ожидается array[{name, data}])")


def _get_resource_compat(path: str) -> dict:
    """
    Чтение ресурса с fallback на /get_value, если /get_value_interpolated недоступен.
    """
    try:
        return wmill.get_resource(path)
    except Exception as e:
        if "get_value_interpolated" not in str(e):
            raise

        import os

        base_url = os.environ.get("BASE_INTERNAL_URL") or os.environ.get("BASE_URL")
        workspace = os.environ.get("WM_WORKSPACE")
        token = os.environ.get("WM_TOKEN")
        if not base_url or not workspace or not token:
            raise

        encoded_path = quote(path, safe="/")
        url = f"{base_url}/api/w/{workspace}/resources/get_value/{encoded_path}"
        response = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=30)
        response.raise_for_status()
        return response.json() if response.text else {}


def transcribe_audio(
    api_key: str,
    audio_input: str,
    model: str = "whisper-medium",
    language: str = "ru",
    diarize: bool = True,
    smart_format: bool = False,
    timeout: int = 120
) -> dict:
    """
    Выполняет транскрибацию аудио через Deepgram API.

    @param api_key API ключ Deepgram
    @param audio_input URL или base64-кодированные данные аудио
    @param model Модель транскрибации (по умолчанию nova-2)
    @param language Язык аудио (по умолчанию ru)
    @param diarize Включить диаризацию/определение говорящих (по умолчанию True)
    @param smart_format Умное форматирование чисел, дат и т.д. (по умолчанию False)
    @param timeout Таймаут запроса в секундах (по умолчанию 120)
    @return Словарь с результатом транскрибации
    @raise ValueError При ошибках API или невалидных входных данных
    """
    url = "https://api.deepgram.com/v1/listen"

    # Параметры запроса
    params = {
        "model": model,
        "language": language,
        "diarize": str(diarize).lower(),
        "smart_format": str(smart_format).lower(),
    }

    headers = {
        "Authorization": f"Token {api_key}",
    }

    audio_data, content_type = _process_audio_data(audio_input)

    try:
        if content_type == "url":
            headers["Content-Type"] = "application/json"
            payload = {"url": audio_data}
            response = requests.post(
                url,
                params=params,
                headers=headers,
                json=payload,
                timeout=timeout
            )
        else:
            # Для base64-данных отправляем сырые байты
            headers["Content-Type"] = "application/octet-stream"
            response = requests.post(
                url,
                params=params,
                headers=headers,
                data=audio_data,
                timeout=timeout
            )

        response.raise_for_status()

        result = response.json()

        # Проверяем наличие результата
        if "results" not in result:
            raise ValueError("Deepgram вернул пустой ответ")

        return result

    except requests.exceptions.Timeout:
        raise ValueError(f"Таймаут при транскрибации ({timeout} сек). Попробуйте меньший файл или увеличьте таймаут.")
    except requests.exceptions.HTTPError as e:
        error_msg = f"HTTP ошибка: {e.response.status_code}"
        try:
            error_detail = e.response.json()
            error_msg += f" | Ответ: {error_detail}"
        except Exception:
            error_msg += f" | Текст: {e.response.text}"
        raise ValueError(error_msg)
    except requests.exceptions.RequestException as e:
        raise ValueError(f"Ошибка запроса: {e}")
    except json.JSONDecodeError:
        raise ValueError("Не удалось распарсить ответ Deepgram")


def main(
    audio_file: t.Any | None = None,
    audio_url: str | None = None,
    model: str = "whisper-medium",
    language: str = "ru",
    diarize: bool = True,
    smart_format: bool = False,
    timeout: int = 300,
) -> dict:
    """
    Основная функция для транскрибации аудио.

    @param audio_file Файл из компонента File input (обычно array[{name, data}])
    @param audio_url URL аудио/видео файла
    @param model Модель транскрибации (по умолчанию whisper-medium)
    @param language Язык аудио (по умолчанию ru)
    @param diarize Включить определение говорящих (по умолчанию True)
    @param smart_format Умное форматирование (по умолчанию False)
    @param timeout Таймаут запроса в секундах (по умолчанию 300)
    @return Словарь с транскрипцией, включающий текст и метаданные
    """
    deepgram_resource = _get_resource_compat("u/theatmacreator/deepgram")
    api_key = deepgram_resource.get("apiKey", "")

    if not api_key:
        raise ValueError("API ключ Deepgram не найден в ресурсе")

    audio_input = _extract_audio_input(audio_file=audio_file, audio_url=audio_url)

    result = transcribe_audio(
        api_key=api_key,
        audio_input=audio_input,
        model=model,
        language=language,
        diarize=diarize,
        smart_format=smart_format,
        timeout=timeout,
    )

    # Извлекаем полезные данные из ответа
    deepgram_result = result.get("results", {})
    metadata = deepgram_result.get("metadata", {})
    channels = deepgram_result.get("channels", [])

    # Формируем транскрипт
    transcripts = []
    speaker_transcripts = {}

    for channel in channels:
        alternatives = channel.get("alternatives", [])
        if not alternatives:
            continue

        alt = alternatives[0]
        transcript = alt.get("transcript", "")
        paragraphs = alt.get("paragraphs", {})
        words = alt.get("words", [])

        # Основной текст
        if transcript:
            transcripts.append(transcript)

        # Транскрипция по говорящим (если включена диаризация)
        if "paragraphs" in alt and alt["paragraphs"].get("paragraphs"):
            for para in alt["paragraphs"]["paragraphs"]:
                speaker = para.get("speaker", 0)
                text = para.get("sentences", [])
                speaker_text = " ".join(s.get("text", "") for s in text)

                if speaker_text:
                    if speaker not in speaker_transcripts:
                        speaker_transcripts[speaker] = []
                    speaker_transcripts[speaker].append(speaker_text)

    # Собираем итоговый результат
    return {
        "text": "\n".join(transcripts),
        "full_result": result,
        "metadata": metadata,
        "speaker_transcripts": {
            f"Speaker {k}": " ".join(v)
            for k, v in speaker_transcripts.items()
        },
        "duration": metadata.get("duration"),
        "language_detected": metadata.get("language"),
        "model_used": metadata.get("model_info", {}).get("name"),
    }
