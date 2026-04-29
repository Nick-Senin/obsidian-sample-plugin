"""
PREPARE_AUDIO - подготовка аудиофайла для транскрибации во флоу

ЧТО ДЕЛАЕТ:
- Подготавливает аудиофайл (уже закодированный в base64) для передачи в транскрибацию
- Передаёт posts для следующего шага
- Поддерживает recording_path для локального тестирования

ГДЕ ИСПОЛЬЗУЕТСЯ:
- f/prj_content_forge/flows/process_recording

ИСПОЛЬЗУЕТ:
- External: локальная файловая система (для recording_path)
"""
import base64
import os


def main(
    audio_file=None,
    posts=None,
    recording_path=None,
    **kwargs
) -> dict:
    """
    Подготавливает аудиофайл для транскрибации.

    @param audio_file Файл в формате [{name, data}] где data - base64
    @param posts Массив конфигураций постов
    @param recording_path Локальный путь к файлу (для тестирования)
    @return Словарь с audio_file и posts
    """
    # Fallback на recording_path для тестирования
    if audio_file is None and recording_path:
        with open(recording_path, "rb") as f:
            file_data = f.read()
        encoded = base64.b64encode(file_data).decode("utf-8")
        filename = os.path.basename(recording_path)
        audio_file = [{"name": filename, "data": encoded}]

    if audio_file is None:
        raise ValueError("Нужно указать либо audio_file, либо recording_path")

    # Убираем Data URL префикс если есть
    for item in audio_file:
        if isinstance(item, dict) and "data" in item:
            data = item["data"]
            if isinstance(data, str) and data.startswith("data:"):
                item["data"] = data.split(",", 1)[1] if "," in data else data

    return {"audio_file": audio_file, "posts": posts}
