"""
Юнит-тесты для generate_post transformation

Тестирует генерацию поста с учётом жанров из Baserow.
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
        'f.prj_content_forge.post_generator.generate_post',
        'f.prj_content_forge.post_generator',
        'f.prj_content_forge',
    ]
    for mod in modules_to_remove:
        if mod in sys.modules:
            del sys.modules[mod]
    yield
    # Очистка после теста
    for mod in modules_to_remove:
        if mod in sys.modules:
            del sys.modules[mod]


class TestGeneratePost:
    """Тесты для функции generate_post"""

    @pytest.fixture
    def mock_wmill_openrouter_resource(self):
        """Мок для Windmill ресурса OpenRouter"""
        return {
            "apiKey": "test-api-key",
            "X_Title": "Test Resource"
        }

    @pytest.fixture
    def mock_wmill_baserow_resource(self):
        """Мок для Windmill ресурса Baserow"""
        return {
            "token": "test-baserow-token"
        }

    @pytest.fixture
    def mock_llm_client(self):
        """Мок для OpenAI клиента"""
        client = Mock()
        return client

    @pytest.fixture
    def mock_genre_data_with_module(self):
        """Мок данных жанра с модулем стиля"""
        return {
            "id": "1",
            "description": "Коротко, по делу. Только факты без эмоций.",
            "module_path": "f/transformations/style_transfer/change_style"
        }

    @pytest.fixture
    def mock_genre_data_with_prompt(self):
        """Мок данных жанра только с промптом"""
        return {
            "id": "1",
            "description": "Ясно, структурно, без воды. Используй абзацы и списки.",
            "module_path": None
        }

    @pytest.fixture
    def sample_input_text(self):
        """Пример входного текста"""
        return "Тезисы про машинное обучение. Нейронные сети учатся на данных."

    @pytest.fixture
    def sample_output_text(self):
        """Пример сгенерированного текста"""
        return "Машинное обучение основано на алгоритмах, которые выявляют закономерности в данных."

    def test_main_returns_dict_with_output_key(
        self,
        mock_wmill_openrouter_resource,
        mock_wmill_baserow_resource,
        mock_llm_client,
        sample_input_text,
        sample_output_text
    ):
        """Тест: функция возвращает словарь с ключом 'output'"""
        mock_baserow_response = MagicMock()
        mock_baserow_response.json.return_value = {
            "results": [
                {
                    "Название": "Обычные контентные посты",
                    "Описание": "Ясно, структурно.",
                    "id": "1"
                }
            ]
        }
        mock_baserow_response.raise_for_status = Mock()

        with patch('wmill.get_resource') as mock_get_resource, \
             patch('f.shared.llm_utils.create_llm_client', return_value=mock_llm_client), \
             patch('f.shared.llm_utils.generate_completion', return_value=sample_output_text), \
             patch('requests.get', return_value=mock_baserow_response):

            # Настраиваем мок для ресурсов
            def get_resource_side_effect(name):
                if "openrouter" in name:
                    return mock_wmill_openrouter_resource
                return mock_wmill_baserow_resource

            mock_get_resource.side_effect = get_resource_side_effect

            from f.prj_content_forge.post_generator.generate_post import main

            result = main(input=sample_input_text)

            assert isinstance(result, dict)
            assert "output" in result
            assert isinstance(result["output"], str)

    def test_main_uses_genre_description_from_baserow(
        self,
        mock_wmill_openrouter_resource,
        mock_wmill_baserow_resource,
        mock_llm_client,
        sample_input_text
    ):
        """Тест: функция использует описание жанра из Baserow"""
        genre_description = "Короткие новости, только факты."

        mock_baserow_response = MagicMock()
        mock_baserow_response.json.return_value = {
            "results": [
                {
                    "Название": "Новости",
                    "Описание": genre_description,
                    "Название модуля для стиля текста": None,
                    "id": "1"
                }
            ]
        }
        mock_baserow_response.raise_for_status = Mock()

        with patch('wmill.get_resource') as mock_get_resource, \
             patch('f.shared.llm_utils.create_llm_client', return_value=mock_llm_client), \
             patch('f.shared.llm_utils.generate_completion', return_value="output") as mock_generate, \
             patch('requests.get', return_value=mock_baserow_response):

            def get_resource_side_effect(name):
                if "openrouter" in name:
                    return mock_wmill_openrouter_resource
                return mock_wmill_baserow_resource

            mock_get_resource.side_effect = get_resource_side_effect

            from f.prj_content_forge.post_generator.generate_post import main

            main(input=sample_input_text, genre_name="Новости")

            # Проверяем, что промпт содержит описание жанра
            assert mock_generate.called
            call_kwargs = mock_generate.call_args.kwargs
            assert genre_description in call_kwargs['prompt']

    def test_main_calls_genre_module_when_specified(
        self,
        mock_wmill_openrouter_resource,
        mock_wmill_baserow_resource,
        sample_input_text
    ):
        """Тест: функция вызывает модуль стиля, если он указан"""
        module_path = "f/transformations/style_transfer/change_style"

        mock_baserow_response = MagicMock()
        mock_baserow_response.json.return_value = {
            "results": [
                {
                    "Название": "Научпоп",
                    "Описание": "Описание жанра",
                    "Название модуля для стиля текста": module_path,
                    "id": "1"
                }
            ]
        }
        mock_baserow_response.raise_for_status = Mock()

        with patch('wmill.get_resource', return_value=mock_wmill_baserow_resource), \
             patch('wmill.run_script_by_path', return_value={"output": "styled output"}) as mock_run_script, \
             patch('requests.get', return_value=mock_baserow_response):

            from f.prj_content_forge.post_generator.generate_post import main

            result = main(input=sample_input_text, genre_name="Научпоп")

            # Проверяем, что был вызван модуль стиля
            mock_run_script.assert_called_once()
            call_args = mock_run_script.call_args
            assert call_args[0][0] == module_path
            assert call_args[0][1]["input_text"] == sample_input_text
            assert result["output"] == "styled output"

    def test_main_uses_default_prompt_when_genre_not_found(
        self,
        mock_wmill_openrouter_resource,
        mock_wmill_baserow_resource,
        mock_llm_client,
        sample_input_text
    ):
        """Тест: функция использует дефолтный промпт, если жанр не найден"""
        mock_baserow_response = MagicMock()
        mock_baserow_response.json.return_value = {
            "results": []  # Жанр не найден
        }
        mock_baserow_response.raise_for_status = Mock()

        with patch('wmill.get_resource') as mock_get_resource, \
             patch('f.shared.llm_utils.create_llm_client', return_value=mock_llm_client), \
             patch('f.shared.llm_utils.generate_completion', return_value="output") as mock_generate, \
             patch('requests.get', return_value=mock_baserow_response):

            def get_resource_side_effect(name):
                if "openrouter" in name:
                    return mock_wmill_openrouter_resource
                return mock_wmill_baserow_resource

            mock_get_resource.side_effect = get_resource_side_effect

            from f.prj_content_forge.post_generator.generate_post import main

            main(input=sample_input_text, genre_name="Несуществующий жанр")

            # Проверяем, что использован дефолтный промпт
            assert mock_generate.called
            call_kwargs = mock_generate.call_args.kwargs
            assert "Ясно, структурно, без воды" in call_kwargs['prompt']

    def test_main_passes_model_parameter_to_llm(
        self,
        mock_wmill_openrouter_resource,
        mock_wmill_baserow_resource,
        mock_llm_client,
        sample_input_text
    ):
        """Тест: функция передаёт параметр model в LLM"""
        test_model = "test-custom-model"

        mock_baserow_response = MagicMock()
        mock_baserow_response.json.return_value = {
            "results": [
                {
                    "Название": "Обычные контентные посты",
                    "Описание": "Описание",
                    "Название модуля для стиля текста": None,
                    "id": "1"
                }
            ]
        }
        mock_baserow_response.raise_for_status = Mock()

        with patch('wmill.get_resource') as mock_get_resource, \
             patch('f.shared.llm_utils.create_llm_client', return_value=mock_llm_client), \
             patch('f.shared.llm_utils.generate_completion', return_value="output") as mock_generate, \
             patch('requests.get', return_value=mock_baserow_response):

            def get_resource_side_effect(name):
                if "openrouter" in name:
                    return mock_wmill_openrouter_resource
                return mock_wmill_baserow_resource

            mock_get_resource.side_effect = get_resource_side_effect

            from f.prj_content_forge.post_generator.generate_post import main

            main(input=sample_input_text, model=test_model)

            # Проверяем, что модель передана в generate_completion
            assert mock_generate.called
            call_kwargs = mock_generate.call_args.kwargs
            assert call_kwargs['model'] == test_model

    def test_get_genre_with_module_fetches_from_baserow(
        self,
        mock_wmill_baserow_resource
    ):
        """Тест: get_genre_with_module делает запрос к Baserow API"""
        mock_baserow_response = MagicMock()
        mock_baserow_response.json.return_value = {
            "results": [
                {
                    "Название": "Тестовый жанр",
                    "Описание": "Описание",
                    "Название модуля для стиля текста": "f/test/module",
                    "id": "123"
                }
            ]
        }
        mock_baserow_response.raise_for_status = Mock()

        with patch('wmill.get_resource', return_value=mock_wmill_baserow_resource), \
             patch('requests.get', return_value=mock_baserow_response) as mock_get:

            from f.prj_content_forge.post_generator.generate_post import get_genre_with_module

            result = get_genre_with_module("Тестовый жанр")

            # Проверяем, что был сделан запрос к Baserow
            mock_get.assert_called_once()
            call_args = mock_get.call_args

            assert "table/747" in call_args[0][0]
            assert call_args[1]["params"]["user_field_names"] == "true"

            # Проверяем результат
            assert result["id"] == "123"
            assert result["description"] == "Описание"
            assert result["module_path"] == "f/test/module"

    def test_get_genre_with_module_returns_none_for_not_found(
        self,
        mock_wmill_baserow_resource
    ):
        """Тест: get_genre_with_module возвращает None, если жанр не найден"""
        mock_baserow_response = MagicMock()
        mock_baserow_response.json.return_value = {
            "results": []  # Пустой результат
        }
        mock_baserow_response.raise_for_status = Mock()

        with patch('wmill.get_resource', return_value=mock_wmill_baserow_resource), \
             patch('requests.get', return_value=mock_baserow_response):

            from f.prj_content_forge.post_generator.generate_post import get_genre_with_module

            result = get_genre_with_module("Несуществующий жанр")

            assert result is None

    def test_generate_via_module_calls_wmill_script(
        self,
        sample_input_text
    ):
        """Тест: generate_via_module вызывает windmill скрипт"""
        module_path = "f/test/module"
        expected_output = "Результат модуля"

        with patch('wmill.run_script_by_path', return_value={"output": expected_output}) as mock_run:

            from f.prj_content_forge.post_generator.generate_post import generate_via_module

            result = generate_via_module(sample_input_text, module_path)

            mock_run.assert_called_once_with(
                module_path,
                {"input_text": sample_input_text}
            )
            assert result == expected_output

    def test_generate_via_module_fallback_on_error(
        self,
        sample_input_text
    ):
        """Тест: generate_via_module возвращает входной текст при ошибке"""
        module_path = "f/test/module"

        with patch('f.prj_content_forge.post_generator.generate_post.wmill.run_script_by_path', side_effect=Exception("Test error")):

            from f.prj_content_forge.post_generator.generate_post import generate_via_module

            result = generate_via_module(sample_input_text, module_path)

            # При ошибке должен вернуть входной текст
            assert result == sample_input_text


class TestGeneratePostIntegration:
    """Интеграционные тесты"""

    def test_genre_not_found_uses_default(self):
        """Тест: при отсутствии жанра используется дефолтный промпт"""
        from f.prj_content_forge.post_generator.generate_post import DEFAULT_GENRE_PROMPT

        assert DEFAULT_GENRE_PROMPT == "Ясно, структурно, без воды. Используй абзацы и списки."


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
