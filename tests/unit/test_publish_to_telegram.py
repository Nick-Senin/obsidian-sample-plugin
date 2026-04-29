"""
Юнит-тесты для publish_to_telegram скрипта

Тестирует публикацию постов из Baserow в Telegram каналы.
"""
import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Добавляем корень проекта в path для импортов
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest


@pytest.fixture
def mock_baserow_resource():
    """Мок для Baserow API ресурса"""
    return {
        "token": "test-baserow-token-12345"
    }


@pytest.fixture
def mock_telegram_bot_resource():
    """Мок для Telegram Bot ресурса"""
    return {
        "token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    }


@pytest.fixture
def sample_post_data():
    """Пример данных поста из Baserow"""
    today = datetime.now().strftime("%Y-%m-%d")
    return {
        "id": 123,
        "Дата публикации": today,
        "Статус": {"id": 1, "value": "Готово к публикации", "color": "green"},
        "Пост для ТГ": "**Тестовый пост**\n\nЭто тестовое сообщение.",
        "Итоговый постер": [
            {"url": "https://example.com/poster.jpg", "name": "poster.jpg"}
        ],
        "Канал публикации": [{"id": 456, "value": "Test Channel"}]
    }


@pytest.fixture
def sample_channel_data():
    """Пример данных канала из Baserow"""
    return {
        "id": 456,
        "Адрес": "@testchannel"
    }


class TestPublishPost:
    """Тесты для функции publish_post"""

    @pytest.fixture
    def mock_image_response(self):
        """Мок ответа при скачивании картинки"""
        response = Mock()
        response.status_code = 200
        response.content = b"fake image data"
        response.raise_for_status = Mock()
        return response

    @pytest.fixture
    def mock_telegram_response(self):
        """Мок ответа от Telegram API"""
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "ok": True,
            "result": {
                "message_id": 100,
                "chat": {"id": -100123456789, "title": "Test Channel"}
            }
        }
        response.raise_for_status = Mock()
        return response

    def test_send_text_only(self, mock_telegram_response):
        """Тест: отправка только текста без картинки (конвертация Markdown в HTML)"""
        channel = "@testchannel"
        # Входной текст с Markdown разметкой
        text = "**Тестовый пост**"

        with patch('requests.post', return_value=mock_telegram_response) as mock_post:
            from f.prj_content_forge.publisher.publish_to_telegram import publish_post

            result = publish_post(channel, text, photo_url=None)

            # Проверяем, что был сделан один POST запрос к sendMessage
            assert mock_post.call_count == 1
            call_args = mock_post.call_args

            assert "sendMessage" in call_args[0][0]
            assert call_args[1]["json"]["chat_id"] == channel
            # Markdown конвертируется в HTML: **text** → <b>text</b>
            assert call_args[1]["json"]["text"] == "<b>Тестовый пост</b>"
            # Проверяем, что parse_mode установлен в HTML
            assert call_args[1]["json"]["parse_mode"] == "HTML"

            assert result["ok"] is True

    def test_send_photo_with_short_caption(self, mock_image_response, mock_telegram_response):
        """Тест: отправка фото с коротким текстом (влезает в caption)"""
        channel = "@testchannel"
        text = "Короткий текст"  # < 1024 символов
        photo_url = "https://example.com/poster.jpg"

        with patch('requests.get', return_value=mock_image_response), \
             patch('requests.post', return_value=mock_telegram_response) as mock_post:

            from f.prj_content_forge.publisher.publish_to_telegram import publish_post

            result = publish_post(channel, text, photo_url)

            # Проверяем, что был сделан один POST запрос к sendPhoto
            assert mock_post.call_count == 1
            call_args = mock_post.call_args

            assert "sendPhoto" in call_args[0][0]
            assert call_args[1]["data"]["chat_id"] == channel
            assert call_args[1]["data"]["caption"] == text
            assert "photo" in call_args[1]["files"]

            assert result["ok"] is True

    def test_send_photo_with_long_text(self, mock_image_response, mock_telegram_response):
        """Тест: отправка фото с длинным текстом (обрезается до 4096 символов)"""
        channel = "@testchannel"
        # Длинный текст > 4096 символов
        text = "a" * 5000
        photo_url = "https://example.com/poster.jpg"

        with patch('requests.get', return_value=mock_image_response), \
             patch('requests.post', return_value=mock_telegram_response) as mock_post:

            from f.prj_content_forge.publisher.publish_to_telegram import publish_post

            result = publish_post(channel, text, photo_url)

            # Проверяем, что был один POST запрос (sendPhoto с обрезанным caption)
            assert mock_post.call_count == 1

            call_args = mock_post.call_args
            assert "sendPhoto" in call_args[0][0]
            # Caption должен быть обрезан до 4096 символов
            assert call_args[1]["data"]["caption"] == "a" * 4096
            assert "photo" in call_args[1]["files"]

            assert result["ok"] is True

    def test_failed_to_download_image(self):
        """Тест: обработка ошибки при скачивании картинки"""
        channel = "@testchannel"
        text = "Текст поста"
        photo_url = "https://example.com/notfound.jpg"

        mock_error_response = Mock()
        mock_error_response.raise_for_status.side_effect = Exception("404 Not Found")

        with patch('requests.get', return_value=mock_error_response):
            from f.prj_content_forge.publisher.publish_to_telegram import publish_post

            with pytest.raises(Exception) as exc_info:
                publish_post(channel, text, photo_url)

            assert "Failed to download image" in str(exc_info.value)

    def test_telegram_api_error(self, mock_image_response):
        """Тест: обработка ошибки Telegram API"""
        channel = "@testchannel"
        text = "Текст поста"
        photo_url = "https://example.com/poster.jpg"

        mock_error_response = Mock()
        mock_error_response.raise_for_status.side_effect = Exception("Bad Request: chat not found")

        with patch('requests.get', return_value=mock_image_response), \
             patch('requests.post', return_value=mock_error_response):

            from f.prj_content_forge.publisher.publish_to_telegram import publish_post

            with pytest.raises(Exception) as exc_info:
                publish_post(channel, text, photo_url)

            # Ошибка пробрасывается дальше
            assert exc_info.value is not None


class TestMain:
    """Тесты для функции main"""

    @pytest.fixture
    def mock_baserow_posts_response(self, sample_post_data):
        """Мок ответа от Baserow со списком постов"""
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "results": [sample_post_data]
        }
        response.raise_for_status = Mock()
        return response

    @pytest.fixture
    def mock_baserow_channel_response(self, sample_channel_data):
        """Мок ответа от Baserow с данными канала"""
        response = Mock()
        response.status_code = 200
        response.json.return_value = sample_channel_data
        response.raise_for_status = Mock()
        return response

    @pytest.fixture
    def mock_baserow_update_response(self):
        """Мок ответа при обновлении статуса в Baserow"""
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "id": 123,
            "Статус": "Опубликован"
        }
        response.raise_for_status = Mock()
        return response

    def test_no_posts_for_today(self, mock_baserow_resource, mock_telegram_bot_resource):
        """Тест: нет постов для публикации сегодня"""
        empty_response = Mock()
        empty_response.status_code = 200
        empty_response.json.return_value = {"results": []}
        empty_response.raise_for_status = Mock()

        with patch('wmill.get_resource') as mock_resource, \
             patch('requests.get', return_value=empty_response):

            # Настраиваем моки ресурсов
            def resource_side_effect(name):
                if "baserow" in name:
                    return mock_baserow_resource
                return mock_telegram_bot_resource

            mock_resource.side_effect = resource_side_effect

            from f.prj_content_forge.publisher.publish_to_telegram import main

            result = main()

            assert result["published_count"] == 0
            assert result["published_ids"] == []
            assert "No posts found" in result["message"]

    def test_successful_publish_single_post(
        self,
        mock_baserow_resource,
        mock_telegram_bot_resource,
        mock_baserow_posts_response,
        mock_baserow_channel_response,
        mock_baserow_update_response
    ):
        """Тест: успешная публикация одного поста"""
        today = datetime.now().strftime("%Y-%m-%d")

        # Мок ответа от Telegram API
        telegram_response = Mock()
        telegram_response.status_code = 200
        telegram_response.json.return_value = {"ok": True, "result": {"message_id": 100}}
        telegram_response.raise_for_status = Mock()

        # Мок для скачивания картинки (если есть в посте)
        mock_image_response = Mock()
        mock_image_response.status_code = 200
        mock_image_response.content = b"fake image data"
        mock_image_response.raise_for_status = Mock()

        with patch('wmill.get_resource') as mock_resource, \
             patch('requests.get') as mock_get, \
             patch('requests.post', return_value=telegram_response) as mock_post, \
             patch('requests.patch', return_value=mock_baserow_update_response) as mock_patch:

            # Настраиваем моки ресурсов
            def resource_side_effect(name):
                if "baserow" in name:
                    return mock_baserow_resource
                return mock_telegram_bot_resource

            mock_resource.side_effect = resource_side_effect

            # Мок для GET запросов: posts -> channel -> image download (опционально)
            mock_get.side_effect = [
                mock_baserow_posts_response,
                mock_baserow_channel_response,
                mock_image_response  # для скачивания картинки
            ]

            from f.prj_content_forge.publisher.publish_to_telegram import main

            result = main()

            assert result["published_count"] == 1
            assert 123 in result["published_ids"]
            assert len(result["errors"]) == 0
            assert "Published 1 posts" in result["message"]

            # Проверяем, что был вызван PATCH для обновления статуса
            assert mock_patch.call_count == 1

    def test_successful_publish_multiple_posts(
        self,
        mock_baserow_resource,
        mock_telegram_bot_resource
    ):
        """Тест: успешная публикация нескольких постов"""
        today = datetime.now().strftime("%Y-%m-%d")
        post1 = {
            "id": 100,
            "Дата публикации": today,
            "Статус": {"id": 1, "value": "Готово к публикации", "color": "green"},
            "Пост для ТГ": "Пост 1",
            "Итоговый постер": None,
            "Канал публикации": [{"id": 456}]
        }
        post2 = {
            "id": 101,
            "Дата публикации": today,
            "Статус": {"id": 1, "value": "Готово к публикации", "color": "green"},
            "Пост для ТГ": "Пост 2",
            "Итоговый постер": None,
            "Канал публикации": [{"id": 456}]
        }

        posts_response = Mock()
        posts_response.status_code = 200
        posts_response.json.return_value = {"results": [post1, post2]}
        posts_response.raise_for_status = Mock()

        channel_response = Mock()
        channel_response.status_code = 200
        channel_response.json.return_value = {"id": 456, "Адрес": "@testchannel"}
        channel_response.raise_for_status = Mock()

        telegram_response = Mock()
        telegram_response.status_code = 200
        telegram_response.json.return_value = {"ok": True}
        telegram_response.raise_for_status = Mock()

        update_response = Mock()
        update_response.status_code = 200
        update_response.json.return_value = {"id": 100, "Статус": "Опубликован"}
        update_response.raise_for_status = Mock()

        with patch('wmill.get_resource') as mock_resource, \
             patch('requests.get') as mock_get, \
             patch('requests.post', return_value=telegram_response), \
             patch('requests.patch', return_value=update_response):

            def resource_side_effect(name):
                if "baserow" in name:
                    return mock_baserow_resource
                return mock_telegram_bot_resource

            mock_resource.side_effect = resource_side_effect
            # posts, channel1, channel2
            mock_get.side_effect = [posts_response, channel_response, channel_response]

            from f.prj_content_forge.publisher.publish_to_telegram import main

            result = main()

            assert result["published_count"] == 2
            assert 100 in result["published_ids"]
            assert 101 in result["published_ids"]

    def test_post_with_wrong_status(self, mock_baserow_resource, mock_telegram_bot_resource):
        """Тест: пост с неправильным статусом пропускается"""
        today = datetime.now().strftime("%Y-%m-%d")
        wrong_post = {
            "id": 999,
            "Дата публикации": today,
            "Статус": {"id": 2, "value": "Черновик", "color": "gray"},
            "Пост для ТГ": "Текст",
            "Итоговый постер": None,
            "Канал публикации": [{"id": 456}]
        }

        posts_response = Mock()
        posts_response.status_code = 200
        posts_response.json.return_value = {"results": [wrong_post]}
        posts_response.raise_for_status = Mock()

        with patch('wmill.get_resource') as mock_resource, \
             patch('requests.get', return_value=posts_response):

            def resource_side_effect(name):
                if "baserow" in name:
                    return mock_baserow_resource
                return mock_telegram_bot_resource

            mock_resource.side_effect = resource_side_effect

            from f.prj_content_forge.publisher.publish_to_telegram import main

            result = main()

            assert result["published_count"] == 0
            assert len(result["errors"]) == 1
            assert "Wrong status" in result["errors"][0]

    def test_post_without_channel_link(self, mock_baserow_resource, mock_telegram_bot_resource):
        """Тест: пост без ссылки на канал вызывает ошибку"""
        today = datetime.now().strftime("%Y-%m-%d")
        post_no_channel = {
            "id": 888,
            "Дата публикации": today,
            "Статус": {"id": 1, "value": "Готово к публикации", "color": "green"},
            "Пост для ТГ": "Текст",
            "Итоговый постер": None,
            "Канал публикации": None
        }

        posts_response = Mock()
        posts_response.status_code = 200
        posts_response.json.return_value = {"results": [post_no_channel]}
        posts_response.raise_for_status = Mock()

        with patch('wmill.get_resource') as mock_resource, \
             patch('requests.get', return_value=posts_response):

            def resource_side_effect(name):
                if "baserow" in name:
                    return mock_baserow_resource
                return mock_telegram_bot_resource

            mock_resource.side_effect = resource_side_effect

            from f.prj_content_forge.publisher.publish_to_telegram import main

            result = main()

            assert result["published_count"] == 0
            assert len(result["errors"]) == 1
            assert "No channel link" in result["errors"][0]

    def test_channel_without_address(self, mock_baserow_resource, mock_telegram_bot_resource):
        """Тест: канал без адреса вызывает ошибку"""
        today = datetime.now().strftime("%Y-%m-%d")
        post = {
            "id": 777,
            "Дата публикации": today,
            "Статус": {"id": 1, "value": "Готово к публикации", "color": "green"},
            "Пост для ТГ": "Текст",
            "Итоговый постер": None,
            "Канал публикации": [{"id": 456}]
        }

        posts_response = Mock()
        posts_response.status_code = 200
        posts_response.json.return_value = {"results": [post]}
        posts_response.raise_for_status = Mock()

        channel_no_address = Mock()
        channel_no_address.status_code = 200
        channel_no_address.json.return_value = {"id": 456, "Адрес": None}
        channel_no_address.raise_for_status = Mock()

        with patch('wmill.get_resource') as mock_resource, \
             patch('requests.get') as mock_get:

            def resource_side_effect(name):
                if "baserow" in name:
                    return mock_baserow_resource
                return mock_telegram_bot_resource

            mock_resource.side_effect = resource_side_effect
            mock_get.side_effect = [posts_response, channel_no_address]

            from f.prj_content_forge.publisher.publish_to_telegram import main

            result = main()

            assert result["published_count"] == 0
            assert len(result["errors"]) == 1
            assert "No address in channel record" in result["errors"][0]

    def test_poster_variations(self, mock_baserow_resource, mock_telegram_bot_resource):
        """Тест: разные варианты поля Итоговый постер (dict, list, None)"""
        today = datetime.now().strftime("%Y-%m-%d")
        # Пост с пустым полем постера
        post_no_poster = {
            "id": 555,
            "Дата публикации": today,
            "Статус": {"id": 1, "value": "Готово к публикации", "color": "green"},
            "Пост для ТГ": "Текст",
            "Итоговый постер": None,
            "Канал публикации": [{"id": 456}]
        }

        posts_response = Mock()
        posts_response.status_code = 200
        posts_response.json.return_value = {"results": [post_no_poster]}
        posts_response.raise_for_status = Mock()

        channel_response = Mock()
        channel_response.status_code = 200
        channel_response.json.return_value = {"id": 456, "Адрес": "@test"}
        channel_response.raise_for_status = Mock()

        telegram_response = Mock()
        telegram_response.status_code = 200
        telegram_response.json.return_value = {"ok": True}
        telegram_response.raise_for_status = Mock()

        update_response = Mock()
        update_response.status_code = 200
        update_response.json.return_value = {"id": 555, "Статус": "Опубликован"}
        update_response.raise_for_status = Mock()

        with patch('wmill.get_resource') as mock_resource, \
             patch('requests.get') as mock_get, \
             patch('requests.post', return_value=telegram_response), \
             patch('requests.patch', return_value=update_response):

            def resource_side_effect(name):
                if "baserow" in name:
                    return mock_baserow_resource
                return mock_telegram_bot_resource

            mock_resource.side_effect = resource_side_effect
            mock_get.side_effect = [posts_response, channel_response]

            from f.prj_content_forge.publisher.publish_to_telegram import main

            result = main()

            assert result["published_count"] == 1
            assert 555 in result["published_ids"]

    def test_status_string_format(self, mock_baserow_resource, mock_telegram_bot_resource):
        """Тест: статус приходит как строка, а не объект"""
        today = datetime.now().strftime("%Y-%m-%d")
        # Baserow может вернуть статус просто как строку
        post_string_status = {
            "id": 444,
            "Дата публикации": today,
            "Статус": "Готово к публикации",  # строка вместо объекта
            "Пост для ТГ": "Текст",
            "Итоговый постер": None,
            "Канал публикации": [{"id": 456}]
        }

        posts_response = Mock()
        posts_response.status_code = 200
        posts_response.json.return_value = {"results": [post_string_status]}
        posts_response.raise_for_status = Mock()

        channel_response = Mock()
        channel_response.status_code = 200
        channel_response.json.return_value = {"id": 456, "Адрес": "@test"}
        channel_response.raise_for_status = Mock()

        telegram_response = Mock()
        telegram_response.status_code = 200
        telegram_response.json.return_value = {"ok": True}
        telegram_response.raise_for_status = Mock()

        update_response = Mock()
        update_response.status_code = 200
        update_response.json.return_value = {"id": 444, "Статус": "Опубликован"}
        update_response.raise_for_status = Mock()

        with patch('wmill.get_resource') as mock_resource, \
             patch('requests.get') as mock_get, \
             patch('requests.post', return_value=telegram_response), \
             patch('requests.patch', return_value=update_response):

            def resource_side_effect(name):
                if "baserow" in name:
                    return mock_baserow_resource
                return mock_telegram_bot_resource

            mock_resource.side_effect = resource_side_effect
            mock_get.side_effect = [posts_response, channel_response]

            from f.prj_content_forge.publisher.publish_to_telegram import main

            result = main()

            assert result["published_count"] == 1

    def test_post_with_wrong_publication_date(self, mock_baserow_resource, mock_telegram_bot_resource):
        """Тест: пост с неправильной датой публикации пропускается"""
        # Пост с датой, отличной от сегодняшней
        today = datetime.now().strftime("%Y-%m-%d")
        wrong_date_post = {
            "id": 777,
            "Дата публикации": "2024-01-01",  # Не сегодня
            "Статус": {"id": 1, "value": "Готово к публикации", "color": "green"},
            "Пост для ТГ": "Текст",
            "Итоговый постер": None,
            "Канал публикации": [{"id": 456}]
        }

        posts_response = Mock()
        posts_response.status_code = 200
        posts_response.json.return_value = {"results": [wrong_date_post]}
        posts_response.raise_for_status = Mock()

        with patch('wmill.get_resource') as mock_resource, \
             patch('requests.get', return_value=posts_response):

            def resource_side_effect(name):
                if "baserow" in name:
                    return mock_baserow_resource
                return mock_telegram_bot_resource

            mock_resource.side_effect = resource_side_effect

            from f.prj_content_forge.publisher.publish_to_telegram import main

            result = main()

            assert result["published_count"] == 0
            assert len(result["errors"]) == 1
            assert f"Wrong publication date '2024-01-01', expected '{today}'" in result["errors"][0]

    def test_post_with_correct_publication_date(self, mock_baserow_resource, mock_telegram_bot_resource):
        """Тест: пост с правильной датой публикации публикуется"""
        today = datetime.now().strftime("%Y-%m-%d")
        correct_date_post = {
            "id": 888,
            "Дата публикации": today,  # Сегодня
            "Статус": {"id": 1, "value": "Готово к публикации", "color": "green"},
            "Пост для ТГ": "Текст",
            "Итоговый постер": None,
            "Канал публикации": [{"id": 456}]
        }

        posts_response = Mock()
        posts_response.status_code = 200
        posts_response.json.return_value = {"results": [correct_date_post]}
        posts_response.raise_for_status = Mock()

        channel_response = Mock()
        channel_response.status_code = 200
        channel_response.json.return_value = {"id": 456, "Адрес": "@test"}
        channel_response.raise_for_status = Mock()

        telegram_response = Mock()
        telegram_response.status_code = 200
        telegram_response.json.return_value = {"ok": True}
        telegram_response.raise_for_status = Mock()

        update_response = Mock()
        update_response.status_code = 200
        update_response.json.return_value = {"id": 888, "Статус": "Опубликован"}
        update_response.raise_for_status = Mock()

        with patch('wmill.get_resource') as mock_resource, \
             patch('requests.get') as mock_get, \
             patch('requests.post', return_value=telegram_response), \
             patch('requests.patch', return_value=update_response):

            def resource_side_effect(name):
                if "baserow" in name:
                    return mock_baserow_resource
                return mock_telegram_bot_resource

            mock_resource.side_effect = resource_side_effect
            mock_get.side_effect = [posts_response, channel_response]

            from f.prj_content_forge.publisher.publish_to_telegram import main

            result = main()

            assert result["published_count"] == 1
            assert 888 in result["published_ids"]


class TestMainErrorHandling:
    """Тесты обработки ошибок в функции main"""

    @pytest.fixture
    def mock_resources(self, mock_baserow_resource, mock_telegram_bot_resource):
        """Комбинированный мок для всех ресурсов"""
        def side_effect(name):
            if "baserow" in name:
                return mock_baserow_resource
            return mock_telegram_bot_resource
        return side_effect

    def test_telegram_api_error_in_main(
        self,
        mock_baserow_resource,
        mock_telegram_bot_resource,
        mock_resources
    ):
        """Тест: ошибка Telegram API при публикации"""
        post = {
            "id": 333,
            "Статус": {"value": "Готово к публикации"},
            "Пост для ТГ": "Текст",
            "Итоговый постер": None,
            "Канал публикации": [{"id": 456}]
        }

        posts_response = Mock()
        posts_response.json.return_value = {"results": [post]}
        posts_response.raise_for_status = Mock()

        channel_response = Mock()
        channel_response.json.return_value = {"Адрес": "@test"}
        channel_response.raise_for_status = Mock()

        # Telegram API возвращает ошибку
        error_response = Mock()
        error_response.status_code = 400
        error_response.json.return_value = {"description": "Bad Request: chat not found"}
        error_response.raise_for_status.side_effect = Exception("HTTP 400")

        with patch('wmill.get_resource', side_effect=mock_resources), \
             patch('requests.get') as mock_get, \
             patch('requests.post', return_value=error_response):

            mock_get.side_effect = [posts_response, channel_response]

            from f.prj_content_forge.publisher.publish_to_telegram import main

            result = main()

            assert result["published_count"] == 0
            assert len(result["errors"]) == 1
            assert "Row 333" in result["errors"][0]

    def test_baserow_update_error(
        self,
        mock_baserow_resource,
        mock_telegram_bot_resource,
        mock_resources
    ):
        """Тест: ошибка при обновлении статуса в Baserow"""
        post = {
            "id": 222,
            "Статус": {"value": "Готово к публикации"},
            "Пост для ТГ": "Текст",
            "Итоговый постер": None,
            "Канал публикации": [{"id": 456}]
        }

        posts_response = Mock()
        posts_response.json.return_value = {"results": [post]}
        posts_response.raise_for_status = Mock()

        channel_response = Mock()
        channel_response.json.return_value = {"Адрес": "@test"}
        channel_response.raise_for_status = Mock()

        telegram_response = Mock()
        telegram_response.json.return_value = {"ok": True}
        telegram_response.raise_for_status = Mock()

        # Ошибка при обновлении статуса
        update_response = Mock()
        update_response.json.return_value = {"detail": "Unauthorized"}
        update_response.raise_for_status.side_effect = Exception("HTTP 401")

        with patch('wmill.get_resource', side_effect=mock_resources), \
             patch('requests.get') as mock_get, \
             patch('requests.post', return_value=telegram_response), \
             patch('requests.patch', return_value=update_response):

            mock_get.side_effect = [posts_response, channel_response]

            from f.prj_content_forge.publisher.publish_to_telegram import main

            result = main()

            assert result["published_count"] == 0
            assert len(result["errors"]) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
