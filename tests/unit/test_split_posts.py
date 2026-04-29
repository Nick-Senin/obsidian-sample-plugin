"""
Юнит-тесты для split_posts transformation

Тестирует разбиение длинного текста на отдельные посты.
"""
import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Добавляем корень проекта в path для импортов
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest


class TestSplitPosts:
    """Тесты для функции split_posts"""

    @pytest.fixture
    def mock_wmill_resource(self):
        """Мок для Windmill ресурса OpenRouter"""
        return {
            "apiKey": "test-api-key",
            "X_Title": "Test Resource"
        }

    @pytest.fixture
    def mock_llm_client(self):
        """Мок для OpenAI клиента"""
        client = Mock()
        return client

    @pytest.fixture
    def sample_input_text(self):
        """Пример входного текста для разбиения"""
        return """Привет! Первый пост про машинное обучение.

Основные понятия ML - это обучение с учителем и без учителя.

@@@@@

Второй пост про нейронные сети.

Нейронные сети состоят из слоев и нейронов.

@@@@@

Третий пост про практику.

Лучший способ учиться - это практика на реальных задачах."""

    @pytest.fixture
    def expected_split_output(self):
        """Ожидаемый результат разбиения"""
        return """Привет! Первый пост про машинное обучение.

Основные понятия ML - это обучение с учителем и без учителя.

@@@@@

Второй пост про нейронные сети.

Нейронные сети состоят из слоев и нейронов.

@@@@@

Третий пост про практику.

Лучший способ учиться - это практика на реальных задачах."""

    def test_split_posts_returns_dict_with_output_key(
        self,
        mock_wmill_resource,
        mock_llm_client,
        sample_input_text,
        expected_split_output
    ):
        """Тест: функция возвращает словарь с ключом 'output'"""
        with patch('wmill.get_resource', return_value=mock_wmill_resource), \
             patch('f.shared.llm_utils.create_llm_client', return_value=mock_llm_client), \
             patch('f.shared.llm_utils.generate_completion', return_value=expected_split_output):

            # Импортируем после патчинга
            from f.transformations.post_splitter.split_posts import main

            result = main(input=sample_input_text)

            assert isinstance(result, dict)
            assert "output" in result
            assert isinstance(result["output"], str)

    def test_split_posts_calls_llm_with_correct_params(
        self,
        mock_wmill_resource,
        mock_llm_client,
        sample_input_text
    ):
        """Тест: функция вызывает LLM с правильными параметрами"""
        with patch('wmill.get_resource', return_value=mock_wmill_resource), \
             patch('f.shared.llm_utils.create_llm_client', return_value=mock_llm_client), \
             patch('f.shared.llm_utils.generate_completion', return_value="test output") as mock_generate:

            from f.transformations.post_splitter.split_posts import main

            main(input=sample_input_text, model="test-model")

            # Проверяем, что generate_completion был вызван с правильными параметрами
            mock_generate.assert_called_once()
            call_kwargs = mock_generate.call_args.kwargs

            assert call_kwargs['model'] == "test-model"
            assert call_kwargs['temperature'] == 0.1
            assert call_kwargs['max_tokens'] == 4000
            assert "@@@@@" in call_kwargs['prompt']

    def test_split_posts_creates_correct_separator(
        self,
        mock_wmill_resource,
        mock_llm_client,
        sample_input_text,
        expected_split_output
    ):
        """Тест: результирующий текст содержит разделитель @@@@@"""
        with patch('wmill.get_resource', return_value=mock_wmill_resource), \
             patch('f.shared.llm_utils.create_llm_client', return_value=mock_llm_client), \
             patch('f.shared.llm_utils.generate_completion', return_value=expected_split_output):

            from f.transformations.post_splitter.split_posts import main

            result = main(input=sample_input_text)

            # Проверяем, что разделитель присутствует в выводе
            assert "@@@@@" in result["output"]

    def test_split_posts_can_parse_multiple_posts(
        self,
        mock_wmill_resource,
        mock_llm_client
    ):
        """Тест: корректное разбиение на несколько постов"""
        multi_post_output = """Пост первый

@@@@@

Пост второй

@@@@@

Пост третий"""

        with patch('wmill.get_resource', return_value=mock_wmill_resource), \
             patch('f.shared.llm_utils.create_llm_client', return_value=mock_llm_client), \
             patch('f.shared.llm_utils.generate_completion', return_value=multi_post_output):

            from f.transformations.post_splitter.split_posts import main

            result = main(input="any input")

            posts = result["output"].split("@@@@@")
            posts = [p.strip() for p in posts if p.strip()]

            assert len(posts) == 3
            assert "Пост первый" in posts[0]
            assert "Пост второй" in posts[1]
            assert "Пост третий" in posts[2]

    def test_split_posts_with_single_post(
        self,
        mock_wmill_resource,
        mock_llm_client
    ):
        """Тест: обработка одного поста без разделителя"""
        single_post = "Это один единственный пост."

        with patch('wmill.get_resource', return_value=mock_wmill_resource), \
             patch('f.shared.llm_utils.create_llm_client', return_value=mock_llm_client), \
             patch('f.shared.llm_utils.generate_completion', return_value=single_post):

            from f.transformations.post_splitter.split_posts import main

            result = main(input="single post input")

            assert result["output"] == single_post
            assert "@@@@@" not in result["output"]


class TestSplitPostsIntegration:
    """Интеграционные тесты с использованием фикстур"""

    def test_with_fixture_transcript(self):
        """Тест с использованием фикстуры транскрипта"""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "sample_transcript.json"

        with open(fixture_path) as f:
            fixture_data = json.load(f)

        # Проверяем, что фикстура содержит ожидаемые поля
        assert "text" in fixture_data
        assert "duration" in fixture_data
        assert "language" in fixture_data
        assert fixture_data["language"] == "ru"
        assert len(fixture_data["text"]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
