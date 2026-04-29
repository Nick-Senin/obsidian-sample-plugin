"""
PROCESS_RECORDING - обработка OBS записи для Content Forge

ЧТО ДЕЛАЕТ:
- Передаёт данные во флоу f/prj_content_forge/flows/process_recording
- Флоу выполняет полную обработку: транскрибацию, разбиение, генерацию контента, постеров, сохранение в Baserow

ГДЕ ИСПОЛЬЗУЕТСЯ:
- Вызывается из OBS Recording Handler (локальное Python приложение)
- Режим "Создать контент для публикации"

ИСПОЛЬЗУЕТ:
- Flow: f/prj_content_forge/flows/process_recording
- Resource: u/theatmacreator/baserow_api, u/theatmacreator/fal
"""
import wmill


def main(
    posts: list,
    recording_path: str = None,
    audio_file: list = None,
) -> dict:
    """
    Обрабатывает OBS запись для создания контента через флоу.

    @param posts Массив конфигураций постов [{channel_id, channel_name, genre_id, genre_name, date}]
    @param recording_path Локальный путь к файлу записи (для тестирования)
    @param audio_file Файл в формате [{name, data}] где data - base64 (для продакшна)
    @return Результат обработки из флоу
    """
    # Подготовка файла для транскрибации
    # audio_file имеет приоритет (для продакшна), recording_path - для тестирования
    if audio_file is None and recording_path:
        # Для тестирования: читаем локальный файл (работает только если файл доступен на сервере)
        import base64
        import os
        with open(recording_path, "rb") as f:
            file_data = f.read()
        encoded = base64.b64encode(file_data).decode("utf-8")
        filename = os.path.basename(recording_path)
        audio_file = [{"name": filename, "data": encoded}]

    if audio_file is None:
        raise ValueError("Нужно указать либо audio_file, либо recording_path")

    # Выполняем флоу process_recording
    result = wmill.run_flow(
        "f/prj_content_forge/flows/process_recording",
        {
            "audio_file": audio_file,
            "posts": posts
        }
    )

    return result
