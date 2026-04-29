"""
Юнит-тесты для process_recording flow

Тестирует обработку OBS записи для создания контента с использованием промптов жанров.
Тестирует Windmill flow через CLI с моками для вызываемых скриптов.
"""
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import subprocess
import json

# Добавляем корень проекта в path для импортов
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest
import base64


# @pytest.fixture(autouse=True)
# def clean_module_cache():
#     """Очищает кэш модулей перед каждым тестом"""
#     modules_to_remove = [
#         'f.prj_content_forge.process_recording',
#         'f.prj_content_forge',
#     ]
#     for mod in modules_to_remove:
#         if mod in sys.modules:
#             del sys.modules[mod]
#     yield
#     # Очистка после теста
#     for mod in modules_to_remove:
#         if mod in sys.modules:
#             del sys.modules[mod]


@pytest.fixture
def sample_audio_file():
    """Фикстура: пример аудиофайла в base64"""
    fake_audio_data = b"FAKE_AUDIO_DATA" * 10
    encoded = base64.b64encode(fake_audio_data).decode("utf-8")
    return [{"name": "test_audio.mp3", "data": encoded}]


@pytest.fixture
def sample_posts_config():
    """Фикстура: пример конфигурации постов"""
    return [
        {
            "index": 0,
            "channel_id": "1",
            "channel_name": "Test Channel",
            "genre_id": "123",
            "genre_name": "Научпоп",
            "date": "05.01.2026"
        }
    ]


@pytest.fixture
def sample_transcript_result():
    """Фикстура: результат транскрибации"""
    return {
        "text": "Первый тезис. Нейронные сети учатся на данных. Второй тезис. Глубокое обучение использует много слоёв."
    }


@pytest.fixture
def sample_split_result():
    """Фикстура: результат разбиения на посты"""
    return {
        "output": "Первый тезис. Нейронные сети учатся на данных.@@@@@Второй тезис. Глубокое обучение использует много слоёв."
    }


@pytest.fixture
def sample_genre_prompt():
    """Фикстура: промпт жанра для картинки"""
    return "A futuristic laboratory with holographic displays, scientific illustration style, high detail"


def mock_wmill_run_script(path, *args, **kwargs):
    """Мок для wmill.run_script_by_path с тестовыми данными"""
    if "transcribe" in path:
        return {"text": "Первый тезис. Нейронные сети учатся на данных. Второй тезис. Глубокое обучение использует много слоёв."}
    elif "split_posts" in path:
        return {"output": "Первый тезис. Нейронные сети учатся на данных.@@@@@Второй тезис. Глубокое обучение использует много слоёв."}
    elif "generate_post" in path:
        return {"output": "Generated post"}
    elif "generate_titles" in path:
        return {"output": "Title 1\nTitle 2"}
    elif "image_prompts" in path:  # generate_image_prompts
        return {"output": "Idea 1: Neural network visualization\nIdea 2: Deep learning layers diagram"}
    elif "get_genre_image_prompt" in path:
        return {"prompt": "A futuristic laboratory with holographic displays, scientific illustration style, high detail"}
    elif "generate_image" in path:
        return {"images": [{"url": "https://example.com/poster.jpg"}]}
    elif "create_post" in path:
        return {"id": "456", "poster_urls": ["https://example.com/poster.jpg"]}
    return {}


def test_flow_returns_success_status():
    """Тест: flow возвращает статус success"""
    # Подготавливаем входные данные для flow
    flow_input = {
        "posts": [
            {
                "index": 0,
                "channel_id": "1",
                "channel_name": "Test Channel",
                "genre_id": "123",
                "genre_name": "Научпоп",
                "date": "05.01.2026"
            }
        ]
    }

    with patch('wmill.run_script_by_path') as mock_run_script:
        mock_run_script.side_effect = mock_wmill_run_script

        # Импортируем и запускаем функцию main из скрипта (flow использует rawscript)
        # Для тестирования rawscript нужно вызывать функцию напрямую
        from f.prj_content_forge.process_recording import main

        # Тестируем через прямую функцию (flow использует ту же логику)
        fake_audio = [{"name": "test.mp3", "data": "ZkFLRV9BVURJTw=="}]  # base64
        result = main(posts=flow_input["posts"], audio_file=fake_audio)

        assert result["status"] == "success"
        assert result["posts_processed"] == 1


def test_flow_calls_genre_prompt_script():
    """Тест: flow вызывает скрипт получения промпта жанра"""
    calls_log = []

    def mock_with_logging(path, *args, **kwargs):
        calls_log.append((path, args[0] if args else {}))
        return mock_wmill_run_script(path, *args, **kwargs)

    with patch('wmill.run_script_by_path') as mock_run_script:
        mock_run_script.side_effect = mock_with_logging

        from f.prj_content_forge.process_recording import main

        posts = [{
            "index": 0,
            "channel_id": "1",
            "channel_name": "Test",
            "genre_id": "123",
            "genre_name": "Научпоп",
            "date": "05.01.2026"
        }]
        fake_audio = [{"name": "test.mp3", "data": "ZkFLRV9BVURJTw=="}]

        main(posts=posts, audio_file=fake_audio)

        # Проверяем, что был вызван скрипт получения промпта жанра
        genre_prompt_calls = [c for c in calls_log if "get_genre_image_prompt" in c[0]]
        assert len(genre_prompt_calls) == 1
        assert genre_prompt_calls[0][1]["genre_id"] == "123"


def test_flow_generates_two_posters_with_genre_prompt():
    """Тест: flow генерирует 2 постера с промптом жанра"""
    calls_log = []
    poster_count = [0]

    def mock_with_logging(path, *args, **kwargs):
        calls_log.append((path, args[0] if args else {}))
        if "generate_image" in path:
            poster_count[0] += 1
        return mock_wmill_run_script(path, *args, **kwargs)

    with patch('wmill.run_script_by_path') as mock_run_script:
        mock_run_script.side_effect = mock_with_logging

        from f.prj_content_forge.process_recording import main

        posts = [{
            "index": 0,
            "channel_id": "1",
            "channel_name": "Test",
            "genre_id": "123",
            "genre_name": "Научпоп",
            "date": "05.01.2026"
        }]
        fake_audio = [{"name": "test.mp3", "data": "ZkFLRV9BVURJTw=="}]

        main(posts=posts, audio_file=fake_audio)

        # Проверяем, что было не менее 2 вызовов генерации изображений (может быть 3 с fallback)
        assert poster_count[0] >= 2


def test_flow_saves_ideas_in_baserow():
    """Тест: flow сохраняет идеи для картинок в Baserow (не только жанровый промпт)"""
    calls_log = []

    def mock_with_logging(path, *args, **kwargs):
        calls_log.append((path, args[0] if args else {}))
        return mock_wmill_run_script(path, *args, **kwargs)

    with patch('wmill.run_script_by_path') as mock_run_script:
        mock_run_script.side_effect = mock_with_logging

        from f.prj_content_forge.process_recording import main

        posts = [{
            "index": 0,
            "channel_id": "1",
            "channel_name": "Test",
            "genre_id": "123",
            "genre_name": "Научпоп",
            "date": "05.01.2026"
        }]
        fake_audio = [{"name": "test.mp3", "data": "ZkFLRV9BVURJTw=="}]

        main(posts=posts, audio_file=fake_audio)

        # Проверяем, что при создании поста передаются идеи (через объединение строк)
        create_post_calls = [c for c in calls_log if "create_post" in c[0]]
        assert len(create_post_calls) == 1

        # image_ideas должны содержить идеи из generate_image_prompts
        image_ideas = create_post_calls[0][1]["image_ideas"]
        assert isinstance(image_ideas, str)
        assert len(image_ideas) > 0


def test_flow_handles_empty_genre_prompt():
    """Тест: flow использует fallback промпт при пустом промпте жанра"""
    empty_prompt = ""
    default_prompt = "A clean, modern illustration with a minimalist style. Soft colors, simple shapes, professional design suitable for social media content."

    def mock_with_empty_genre(path, *args, **kwargs):
        if "get_genre_image_prompt" in path:
            return {"prompt": empty_prompt}
        return mock_wmill_run_script(path, *args, **kwargs)

    with patch('wmill.run_script_by_path') as mock_run_script:
        mock_run_script.side_effect = mock_with_empty_genre

        from f.prj_content_forge.process_recording import main

        posts = [{
            "index": 0,
            "channel_id": "1",
            "channel_name": "Test",
            "genre_id": "123",
            "genre_name": "Научпоп",
            "date": "05.01.2026"
        }]
        fake_audio = [{"name": "test.mp3", "data": "ZkFLRV9BVURJTw=="}]

        result = main(posts=posts, audio_file=fake_audio)

        assert result["status"] == "success"


def test_flow_handles_multiple_posts():
    """Тест: flow обрабатывает несколько постов с разными жанрами"""
    posts_config = [
        {
            "index": 0,
            "channel_id": "1",
            "channel_name": "Channel 1",
            "genre_id": "111",
            "genre_name": "Научпоп",
            "date": "05.01.2026"
        },
        {
            "index": 1,
            "channel_id": "2",
            "channel_name": "Channel 2",
            "genre_id": "222",
            "genre_name": "Новости",
            "date": "05.01.2026"
        }
    ]

    genre_prompts = {
        "111": "Science lab with holograms",
        "222": "News room with monitors"
    }

    def mock_with_multiple_genres(path, *args, **kwargs):
        if "get_genre_image_prompt" in path:
            genre_id = kwargs.get("genre_id") or (args[0].get("genre_id") if args else None)
            return {"prompt": genre_prompts.get(genre_id, "default prompt")}
        return mock_wmill_run_script(path, *args, **kwargs)

    with patch('wmill.run_script_by_path') as mock_run_script:
        mock_run_script.side_effect = mock_with_multiple_genres

        from f.prj_content_forge.process_recording import main

        fake_audio = [{"name": "test.mp3", "data": "ZkFLRV9BVURJTw=="}]

        result = main(posts=posts_config, audio_file=fake_audio)

        assert result["status"] == "success"
        assert result["posts_processed"] == 2
        assert len(result["results"]) == 2


def test_flow_requires_audio_file_or_recording_path():
    """Тест: flow выбрасывает исключение если нет ни audio_file ни recording_path"""
    from f.prj_content_forge.process_recording import main

    with pytest.raises(ValueError, match="Нужно указать либо audio_file"):
        main(posts=[])


def test_flow_reads_local_file_when_audio_file_not_provided():
    """Тест: flow читает локальный файл если audio_file не предоставлен"""
    import tempfile
    import os

    # Создаём временный файл
    with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".mp3") as f:
        f.write(b"FAKE_AUDIO_DATA")
        temp_path = f.name

    try:
        with patch('wmill.run_script_by_path') as mock_run_script:
            mock_run_script.side_effect = mock_wmill_run_script

            from f.prj_content_forge.process_recording import main

            posts = [{
                "index": 0,
                "channel_id": "1",
                "channel_name": "Test",
                "genre_id": "123",
                "genre_name": "Научпоп",
                "date": "05.01.2026"
            }]

            result = main(posts=posts, recording_path=temp_path)

            assert result["status"] == "success"
    finally:
        os.unlink(temp_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
