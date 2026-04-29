"""
Юнит-тесты для get_genre_image_prompt transformation

Тестирует получение промпта для картинки по жанру из Baserow.
"""
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Добавляем корень проекта в path для импортов
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest


# Очистка кэша модулей перед тестами
@pytest.fixture(autouse=True)
def clean_module_cache():
    """Очищает кэш модулей перед каждым тестом"""
    modules_to_remove = [
        'f.transformations.baserow_genres.get_genre_image_prompt',
        'f.transformations.baserow_genres',
        'f.transformations',
    ]
    for mod in modules_to_remove:
        if mod in sys.modules:
            del sys.modules[mod]
    yield
    # Очистка после теста
    for mod in modules_to_remove:
        if mod in sys.modules:
            del sys.modules[mod]


class TestGetGenreImagePrompt:
    """Тесты для функции get_genre_image_prompt"""

    @pytest.fixture
    def mock_wmill_baserow_resource(self):
        """Мок для Windmill ресурса Baserow"""
        return {
            "token": "test-baserow-token"
        }

    @pytest.fixture
    def sample_genre_response(self):
        """Мок ответа от Baserow API с данными жанра"""
        return {
            "id": "123",
            "Название": "Научпоп",
            "Описание": "Популярная наука",
            "Промпт/процесс для картинки": "A futuristic laboratory with holographic displays showing molecular structures, clean white background, scientific illustration style, high detail"
        }

    def test_main_returns_dict_with_prompt_key(
        self,
        mock_wmill_baserow_resource,
        sample_genre_response
    ):
        """Тест: функция возвращает словарь с ключом 'prompt'"""
        mock_baserow_response = MagicMock()
        mock_baserow_response.json.return_value = sample_genre_response
        mock_baserow_response.raise_for_status = Mock()

        with patch('wmill.get_resource', return_value=mock_wmill_baserow_resource), \
             patch('requests.get', return_value=mock_baserow_response):

            from f.transformations.baserow_genres.get_genre_image_prompt import main

            result = main(genre_id="123")

            assert isinstance(result, dict)
            assert "prompt" in result
            assert isinstance(result["prompt"], str)

    def test_main_fetches_from_baserow_api(
        self,
        mock_wmill_baserow_resource,
        sample_genre_response
    ):
        """Тест: функция делает запрос к Baserow API для получения жанра"""
        genre_id = "123"
        expected_url = f"https://content.nicksenin.com/api/database/rows/table/747/{genre_id}/?user_field_names=true"

        mock_baserow_response = MagicMock()
        mock_baserow_response.json.return_value = sample_genre_response
        mock_baserow_response.raise_for_status = Mock()

        with patch('wmill.get_resource', return_value=mock_wmill_baserow_resource), \
             patch('requests.get', return_value=mock_baserow_response) as mock_get:

            from f.transformations.baserow_genres.get_genre_image_prompt import main

            main(genre_id=genre_id)

            # Проверяем, что был сделан запрос к правильному URL
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert call_args[0][0] == expected_url

            # Проверяем заголовки
            headers = call_args[1]["headers"]
            assert headers["Authorization"] == f"Token {mock_wmill_baserow_resource['token']}"
            assert headers["Content-Type"] == "application/json"

    def test_main_returns_correct_prompt_from_baserow(
        self,
        mock_wmill_baserow_resource,
        sample_genre_response
    ):
        """Тест: функция возвращает правильный промпт из Baserow"""
        expected_prompt = sample_genre_response["Промпт/процесс для картинки"]

        mock_baserow_response = MagicMock()
        mock_baserow_response.json.return_value = sample_genre_response
        mock_baserow_response.raise_for_status = Mock()

        with patch('wmill.get_resource', return_value=mock_wmill_baserow_resource), \
             patch('requests.get', return_value=mock_baserow_response):

            from f.transformations.baserow_genres.get_genre_image_prompt import main

            result = main(genre_id="123")

            assert result["prompt"] == expected_prompt

    def test_main_handles_missing_prompt_field(
        self,
        mock_wmill_baserow_resource
    ):
        """Тест: функция обрабатывает отсутствие поля промпта в ответе"""
        mock_baserow_response = MagicMock()
        mock_baserow_response.json.return_value = {
            "id": "123",
            "Название": "Жанр без промпта",
            "Описание": "Описание"
        }
        mock_baserow_response.raise_for_status = Mock()

        with patch('wmill.get_resource', return_value=mock_wmill_baserow_resource), \
             patch('requests.get', return_value=mock_baserow_response):

            from f.transformations.baserow_genres.get_genre_image_prompt import main

            result = main(genre_id="123")

            # Должен вернуть пустую строку при отсутствии поля
            assert result["prompt"] == ""

    def test_main_handles_empty_prompt_value(
        self,
        mock_wmill_baserow_resource
    ):
        """Тест: функция обрабатывает пустое значение поля промпта"""
        mock_baserow_response = MagicMock()
        mock_baserow_response.json.return_value = {
            "id": "123",
            "Название": "Жанр с пустым промптом",
            "Описание": "Описание",
            "Промпт/процесс для картинки": ""  # Пустая строка
        }
        mock_baserow_response.raise_for_status = Mock()

        with patch('wmill.get_resource', return_value=mock_wmill_baserow_resource), \
             patch('requests.get', return_value=mock_baserow_response):

            from f.transformations.baserow_genres.get_genre_image_prompt import main

            result = main(genre_id="123")

            # Должен вернуть пустую строку
            assert result["prompt"] == ""

    def test_main_handles_http_error(
        self,
        mock_wmill_baserow_resource
    ):
        """Тест: функция выбрасывает исключение при HTTP ошибке"""
        mock_baserow_response = MagicMock()
        mock_baserow_response.raise_for_status.side_effect = Exception("HTTP 404: Not Found")

        with patch('wmill.get_resource', return_value=mock_wmill_baserow_resource), \
             patch('requests.get', return_value=mock_baserow_response), \
             pytest.raises(Exception, match="HTTP 404"):

            from f.transformations.baserow_genres.get_genre_image_prompt import main

            main(genre_id="999")

    def test_main_uses_baserow_resource(
        self,
        mock_wmill_baserow_resource
    ):
        """Тест: функция использует правильный ресурс Baserow"""
        mock_baserow_response = MagicMock()
        mock_baserow_response.json.return_value = {
            "Промпт/процесс для картинки": "test prompt"
        }
        mock_baserow_response.raise_for_status = Mock()

        with patch('wmill.get_resource') as mock_get_resource, \
             patch('requests.get', return_value=mock_baserow_response):

            mock_get_resource.return_value = mock_wmill_baserow_resource

            from f.transformations.baserow_genres.get_genre_image_prompt import main

            main(genre_id="123")

            # Проверяем, что был получен правильный ресурс
            mock_get_resource.assert_called_once_with("u/theatmacreator/baserow_api")


class TestGetGenreImagePromptIntegration:
    """Интеграционные тесты"""

    def test_baserow_api_url_format(self):
        """Тест: проверка формата URL для Baserow API"""
        genre_id = "456"
        expected_url = f"https://content.nicksenin.com/api/database/rows/table/747/{genre_id}/?user_field_names=true"

        assert "table/747" in expected_url
        assert genre_id in expected_url
        assert "user_field_names=true" in expected_url


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
