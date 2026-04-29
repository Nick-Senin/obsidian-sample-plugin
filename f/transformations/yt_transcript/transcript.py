"""
YT_TRANSCRIPT - Получение транскрипта YouTube видео

ЧТО ДЕЛАЕТ:
- Получает транскрипт YouTube видео по ссылке
- Объединяет все сегменты текста

ГДЕ ИСПОЛЬЗУЕТСЯ:
- Используется для извлечения текста из YouTube видео

ИСПОЛЬЗУЕТ:
- External: yt-dlp (Python library, должна быть доступна в runtime)

ИСТОРИЯ:
- Обновлён для поддержки выбора языка (ru, en, auto)
"""
import os
import tempfile


def ensure_yt_dlp():
    """Проверяет, что yt-dlp доступен в runtime."""
    try:
        import yt_dlp
        return yt_dlp
    except ImportError:
        raise RuntimeError("yt-dlp is not available in the current runtime")


def main(url: str, lang: str = "ru") -> dict:
    """
    Получает транскрипт YouTube видео.

    @param url Ссылка на YouTube видео
    @param lang Язык субтитров (ru, en, auto). По умолчанию ru
    @return Словарь с полем output - текст транскрипта
    """
    yt_dlp = ensure_yt_dlp()

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Настраиваем yt-dlp для скачивания субтитров
            # Определяем языки для поиска
            langs = ['ru', 'en'] if lang == 'auto' else [lang]

            ydl_opts = {
                'skip_download': True,
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': langs,
                'subtitlesformat': 'json3',
                'outtmpl': os.path.join(tmpdir, '%(id)s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                # Проверяем есть ли субтитры
                subtitles = info.get('subtitles', {})
                automatic_captions = info.get('automatic_captions', {})

                if not subtitles and not automatic_captions:
                    return {
                        "output": "",
                        "error": "No subtitles available for this video"
                    }

                # Скачиваем субтитры
                ydl.download([url])

            # Ищем скачанные файлы субтитров
            sub_files = [f for f in os.listdir(tmpdir) if f.endswith('.json3')]

            if not sub_files:
                # Пробуем все доступные языки
                ydl_opts['subtitleslangs'] = ['ru', 'en', 'auto']
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])

                sub_files = [f for f in os.listdir(tmpdir) if f.endswith('.json3')]

                if not sub_files:
                    return {
                        "output": "",
                        "error": "Failed to download subtitles"
                    }

            # Читаем первый файл субтитров
            sub_file = os.path.join(tmpdir, sub_files[0])
            import json
            with open(sub_file, 'r') as f:
                sub_data = json.load(f)

            # Извлекаем текст из событий
            text_parts = []
            if 'events' in sub_data:
                for event in sub_data['events']:
                    if 'segs' in event:
                        for seg in event['segs']:
                            if 'utf8' in seg:
                                text_parts.append(seg['utf8'])

            output = ' '.join(text_parts)

            if not output.strip():
                return {
                    "output": "",
                    "error": "Subtitles are empty"
                }

            return {"output": output}

    except Exception as e:
        return {
            "output": "",
            "error": f"Error: {str(e)}"
        }
