"""
GIGAAM_TRANSCRIBE - транскрибация аудио через GigaAM-v3 на Modal

ЧТО ДЕЛАЕТ:
- Преобразует аудио в текст с помощью GigaAM-v3 модели на Modal
- Использует долгий эндпоинт (/full/submit) для качественной транскрибации
- Поддерживает URL и base64-кодированные файлы
- Асинхронная обработка с поллингом результата

ГДЕ ИСПОЛЬЗУЕТСЯ:
- f/prj_content_forge/flows/create_posts_from_transcript__flow

ИСПОЛЬЗУЕТ:
- External: Modal GigaAM-v3 API (/full/submit, /full/result/{job_id})
"""
import base64
import time
import typing as t
from urllib.parse import urlparse

import requests
import wmill


# Интервал поллинга результата (секунды)
POLL_INTERVAL = 5
# Максимальное время ожидания (секунды) - 24 часа для длинных аудио
MAX_POLL_TIME = 60 * 60 * 24
# Сколько подряд сетевых ошибок допускаем при poll_result, прежде чем падать
MAX_CONSECUTIVE_POLL_ERRORS = 5
URL_MODE_RECOVERABLE_ERROR_MARKERS = (
    "No such file or directory",
    "input.mp3",
    "input.wav",
)


def _validate_url(url: str) -> bool:
    """Проверяет валидность URL."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def _is_base64_audio(data: str) -> bool:
    """
    Проверяет, является ли строка base64-кодированными аудио данными.
    """
    if data.startswith("data:"):
        return True

    if len(data) < 100:
        return False

    try:
        decoded = base64.b64decode(data, validate=True)
        try:
            decoded.decode('ascii')
            return False
        except UnicodeDecodeError:
            return True
    except Exception:
        return False


def _prepare_audio_data(audio_input: str | bytes) -> tuple[bytes | str, str]:
    """
    Подготавливает аудио данные для отправки в Modal.

    @param audio_input URL или base64-кодированные данные аудио
    @return Кортеж (data, input_type) где:
            - data: bytes для файла или str для URL
            - input_type: "url" или "file"
    """
    if isinstance(audio_input, (bytes, bytearray)):
        return bytes(audio_input), "file"

    if _validate_url(audio_input):
        return audio_input, "url"

    if _is_base64_audio(audio_input):
        if audio_input.startswith("data:"):
            parts = audio_input.split(",", 1)
            if len(parts) == 2:
                return base64.b64decode(parts[1]), "file"
        return base64.b64decode(audio_input), "file"

    return audio_input, "url"


def _extract_audio_input(
    *,
    audio_file: t.Any | None,
    audio_url: str | None,
) -> str | bytes:
    """
    Нормализует вход для транскрибации из App.
    """
    if isinstance(audio_url, str) and audio_url.strip():
        return audio_url.strip()

    if audio_file is None:
        raise ValueError("Нужно указать URL или загрузить файл")

    if isinstance(audio_file, list) and audio_file:
        first = audio_file[0]
        if isinstance(first, dict):
            data = first.get("data")
            if isinstance(data, str) and data.strip():
                return data.strip()
            if isinstance(data, (bytes, bytearray)) and data:
                return bytes(data)
            s3_path = first.get("s3")
            if isinstance(s3_path, str) and s3_path.strip():
                content = wmill.load_s3_file({"s3": s3_path})
                if content:
                    return content
        if isinstance(first, str) and first.strip():
            return first.strip()

    if isinstance(audio_file, dict):
        data = audio_file.get("data")
        if isinstance(data, str) and data.strip():
            return data.strip()
        if isinstance(data, (bytes, bytearray)) and data:
            return bytes(data)
        s3_path = audio_file.get("s3")
        if isinstance(s3_path, str) and s3_path.strip():
            content = wmill.load_s3_file({"s3": s3_path})
            if content:
                return content

    raise ValueError("Не удалось прочитать файл из File input (ожидается array[{name, data}] или S3Object)")


def submit_audio(
    base_url: str,
    audio_input: str | bytes,
    input_type: str,
    timeout: int = 180,
) -> dict:
    """
    Отправляет аудио на обработку в Modal.

    @param base_url Базовый URL Modal приложения
    @param audio_input URL или bytes аудио данных
    @param input_type Тип ввода: "url" или "file"
    @param timeout Таймаут запроса
    @return Ответ с job_id
    """
    submit_url = f"{base_url.rstrip('/')}/full/submit"

    try:
        if input_type == "url":
            files = None
            data = {"url": audio_input}
        else:
            # Для файла отправляем как multipart
            files = {"file": ("audio.mp3", audio_input, "audio/mpeg")}
            data = None

        response = requests.post(submit_url, files=files, data=data, timeout=timeout)
        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as e:
        raise ValueError(f"Ошибка отправки аудио: {e}")


def _download_audio_url(audio_url: str, timeout: int = 180) -> bytes:
    """
    Скачивает аудио по URL, чтобы отправить его как multipart-файл.
    Это fallback для случаев, когда backend URL-mode ломается на стороне Modal.
    """
    try:
        response = requests.get(audio_url, timeout=timeout)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise ValueError(f"Ошибка скачивания аудио по URL: {e}")

    content = response.content
    if not content:
        raise ValueError("Скачанный аудиофайл пустой")
    return content


def poll_result(
    base_url: str,
    job_id: str,
    poll_interval: int = POLL_INTERVAL,
    max_time: int = MAX_POLL_TIME,
) -> dict:
    """
    Поллит результат транскрибации.

    @param base_url Базовый URL Modal приложения
    @param job_id ID задачи
    @param poll_interval Интервал поллинга в секундах
    @param max_time Максимальное время ожидания в секундах
    @return Результат транскрибации
    """
    result_url = f"{base_url.rstrip('/')}/full/result/{job_id}"
    start_time = time.time()
    consecutive_poll_errors = 0

    while True:
        elapsed = time.time() - start_time
        if elapsed > max_time:
            raise ValueError(f"Таймаут ожидания результата ({max_time} сек)")

        try:
            response = requests.get(result_url, timeout=30)
            response.raise_for_status()
            result = response.json()
            consecutive_poll_errors = 0

            status = result.get("status")

            if status == "done":
                return result
            elif status == "running":
                time.sleep(poll_interval)
            elif "error" in result:
                raise ValueError(f"Ошибка транскрибации: {result.get('message', result.get('error'))}")
            else:
                # Неизвестный статус, ждём
                time.sleep(poll_interval)

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else "unknown"
            try:
                detail = e.response.json() if e.response is not None else {}
            except Exception:
                detail = e.response.text if e.response is not None else str(e)
            raise ValueError(f"Ошибка получения статуса транскрибации: HTTP {status_code} | {detail}")
        except requests.exceptions.RequestException as e:
            consecutive_poll_errors += 1
            if consecutive_poll_errors >= MAX_CONSECUTIVE_POLL_ERRORS:
                raise ValueError(
                    "Не удалось получить статус транскрибации после "
                    f"{consecutive_poll_errors} подряд сетевых ошибок: {e}"
                )
            time.sleep(poll_interval)
            continue


def main(
    audio_file: t.Any | None = None,
    audio_url: str | None = None,
    modal_base_url: str = "https://nick-senin--gigaam-v3-asr-api.modal.run",
    submit_timeout: int = 180,
    poll_interval: int = 5,
    max_wait_time: int = 86400,
) -> dict:
    """
    Транскрибация аудио через GigaAM-v3 на Modal.

    @param audio_file Файл из компонента File input (array[{name, data}] или S3Object)
    @param audio_url URL аудио файла
    @param modal_base_url Базовый URL Modal приложения с GigaAM
    @param submit_timeout Таймаут submit запроса в секундах
    @param poll_interval Интервал поллинга результата в секундах
    @param max_wait_time Максимальное время ожидания в секундах
    @return Словарь с транскрипцией и метаданными
    """
    # Нормализуем параметры (защита от None)
    submit_timeout = int(submit_timeout or 180)
    poll_interval = int(poll_interval or POLL_INTERVAL)
    max_wait_time = int(max_wait_time or MAX_POLL_TIME)

    audio_input = _extract_audio_input(audio_file=audio_file, audio_url=audio_url)
    audio_data, input_type = _prepare_audio_data(audio_input)

    def run_transcription(current_audio_data: str | bytes, current_input_type: str) -> dict:
        submit_response = submit_audio(
            modal_base_url,
            current_audio_data,
            current_input_type,
            timeout=submit_timeout,
        )

        if "error" in submit_response:
            raise ValueError(
                f"Ошибка при отправке: {submit_response.get('message', submit_response.get('error'))}"
            )

        job_id = submit_response.get("job_id")
        if not job_id:
            raise ValueError("Не получен job_id от Modal")

        result = poll_result(modal_base_url, job_id, poll_interval, max_wait_time)
        if "error" in result:
            raise ValueError(f"Ошибка транскрибации: {result.get('message', result.get('error'))}")

        return {
            "text": result.get("text", ""),
            "mode": result.get("mode", "full"),
            "model_repo": result.get("model_repo"),
            "revision": result.get("revision"),
            "audio_seconds": result.get("audio_seconds"),
            "took_seconds": result.get("took_seconds"),
            "chunks": result.get("chunks"),
            "job_id": job_id,
            "full_result": result,
            "submitted_as": current_input_type,
        }

    try:
        return run_transcription(audio_data, input_type)
    except ValueError as e:
        can_retry_via_file = (
            input_type == "url"
            and isinstance(audio_input, str)
            and any(marker in str(e) for marker in URL_MODE_RECOVERABLE_ERROR_MARKERS)
        )
        if not can_retry_via_file:
            raise

        fallback_bytes = _download_audio_url(audio_input, timeout=submit_timeout)
        result = run_transcription(fallback_bytes, "file")
        result["fallback_used"] = "download_url_then_file_upload"
        result["fallback_from_error"] = str(e)
        return result
