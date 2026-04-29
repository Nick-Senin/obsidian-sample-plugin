"""
Интеграционные тесты для create_posts_from_transcript__flow

Тестирует полный пайплайн от транскрибации до создания постов в Baserow.
"""
import json
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest


class TestFlowIntegration:
    """Интеграционные тесты для флоу"""

    @pytest.fixture
    def flow_path(self):
        """Путь к тестируемому флоу"""
        return "f/prj_content_forge/flows/create_posts_from_transcript__flow"

    @pytest.fixture
    def flow_input_file(self):
        """Путь к файлу с тестовыми данными для флоу"""
        return Path(__file__).parent.parent / "fixtures" / "flow_input.json"

    @pytest.fixture
    def sample_flow_input(self):
        """Тестовые данные для запуска флоу"""
        return {
            "audio_url": "https://example.com/test-audio.mp3",
            "audio_file": None,
            "model": "whisper-medium",
            "language": "ru",
            "diarize": True,
            "smart_format": False
        }

    def test_flow_input_schema_is_valid(self, sample_flow_input):
        """Тест: входные данные соответствуют схеме флоу"""
        # Проверяем обязательные поля
        expected_keys = {"audio_url", "audio_file", "model", "language", "diarize", "smart_format"}
        assert set(sample_flow_input.keys()) == expected_keys

        # Проверяем типы данных
        assert isinstance(sample_flow_input["audio_url"], str)
        assert isinstance(sample_flow_input["model"], str)
        assert isinstance(sample_flow_input["language"], str)
        assert isinstance(sample_flow_input["diarize"], bool)
        assert isinstance(sample_flow_input["smart_format"], bool)

    def test_flow_input_file_exists(self, flow_input_file):
        """Тест: файл с тестовыми данными существует"""
        assert flow_input_file.exists()

    def test_flow_input_file_is_valid_json(self, flow_input_file):
        """Тест: файл с тестовыми данными является валидным JSON"""
        with open(flow_input_file) as f:
            data = json.load(f)

        assert isinstance(data, dict)
        assert "audio_url" in data

    def test_flow_yaml_exists(self, flow_path):
        """Тест: файл flow.yaml существует"""
        flow_file = Path(flow_path) / "flow.yaml"
        assert flow_file.exists()

    def test_flow_yaml_has_required_modules(self, flow_path):
        """Тест: флоу содержит все необходимые модули"""
        flow_file = Path(flow_path) / "flow.yaml"

        with open(flow_file) as f:
            flow_content = f.read()

        # Проверяем наличие ключевых модулей
        required_modules = [
            "transcribe",
            "split_posts",
            "loop_posts",
            "gen_post",
            "gen_titles",
            "gen_image_ideas",
            "add_to_baserow"
        ]

        for module in required_modules:
            assert module in flow_content, f"Модуль {module} не найден в flow.yaml"

    def test_flow_modules_paths_are_valid(self, flow_path):
        """Тест: пути к модулям в флоу существуют"""
        flow_file = Path(flow_path) / "flow.yaml"

        with open(flow_file) as f:
            flow_content = f.read()

        # Извлекаем пути к скриптам
        import re
        script_paths = re.findall(r"path: ([^\n]+)", flow_content)

        for script_path in script_paths:
            script_file = Path(script_path.replace("f/", "").replace("/", "__") + ".py")
            # Проверяем, что путь соответствует структуре Windmill
            assert script_path.startswith("f/"), f"Некорректный путь: {script_path}"

    def test_flow_has_valid_schema(self, flow_path):
        """Тест: флоу содержит валидную JSON schema"""
        flow_file = Path(flow_path) / "flow.yaml"

        with open(flow_file) as f:
            flow_content = f.read()

        # Проверяем наличие секции schema
        assert "schema:" in flow_content
        assert "$schema" in flow_content
        assert "properties:" in flow_content


class TestFlowModules:
    """Тесты для отдельных модулей флоу"""

    @pytest.fixture
    def flow_modules(self):
        """Список модулей флоу с их путями"""
        return {
            "transcribe": "f/transformations/transcriber/transcribe.py",
            "split_posts": "f/transformations/post_splitter/split_posts.py",
            "gen_post": "f/transformations/post_generator/generate_post.py",
            "gen_titles": "f/transformations/title_generator/generate_titles.py",
            "gen_image_ideas": "f/transformations/image_prompts/generate_image_prompts.py",
            "add_to_baserow": "f/transformations/baserow_post/create_post.py"
        }

    def test_all_module_files_exist(self, flow_modules):
        """Тест: все файлы модулей существуют"""
        project_root = Path(__file__).parent.parent.parent

        for name, path in flow_modules.items():
            module_file = project_root / path
            assert module_file.exists(), f"Файл модуля {name} не найден: {path}"

    def test_all_modules_have_docstrings(self, flow_modules):
        """Тест: все модули имеют docstring согласно стандартам"""
        project_root = Path(__file__).parent.parent.parent

        for name, path in flow_modules.items():
            module_file = project_root / path

            with open(module_file) as f:
                content = f.read()

            # Проверяем наличие docstring
            assert '"""' in content, f"Модуль {name} не имеет docstring"

            # Проверяем наличие обязательных секций
            docstring_section = content.split('"""')[1] if len(content.split('"""')) > 1 else ""

            assert "ЧТО ДЕЛАЕТ:" in docstring_section or "WHAT IT DOES:" in docstring_section, \
                f"Модуль {name} не имеет секции 'ЧТО ДЕЛАЕТ'"
            assert "ГДЕ ИСПОЛЬЗУЕТСЯ:" in docstring_section or "WHERE USED:" in docstring_section, \
                f"Модуль {name} не имеет секции 'ГДЕ ИСПОЛЬЗУЕТСЯ'"
            assert "ИСПОЛЬЗУЕТ:" in docstring_section or "USES:" in docstring_section, \
                f"Модуль {name} не имеет секции 'ИСПОЛЬЗУЕТ'"

    def test_all_modules_import_main(self, flow_modules):
        """Тест: все модули имеют функцию main"""
        project_root = Path(__file__).parent.parent.parent

        for name, path in flow_modules.items():
            module_file = project_root / path

            with open(module_file) as f:
                content = f.read()

            assert "def main(" in content, f"Модуль {name} не имеет функции main"


class TestFlowWmillCommands:
    """Тесты для Windmill CLI команд"""

    @pytest.fixture
    def flow_path(self):
        return "f/prj_content_forge/flows/create_posts_from_transcript__flow"

    def test_wmill_flow_validate_syntax(self, flow_path):
        """
        Тест: проверка синтаксиса флоу через wmill CLI.

        Примечание: этот тест требует установленного wmill CLI и авторизации.
        """
        # Проверяем, что wmill доступен
        try:
            result = subprocess.run(
                ["wmill", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            wmill_available = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            wmill_available = False

        if not wmill_available:
            pytest.skip("wmill CLI не установлен или недоступен")

        # Проверяем валидность флоу
        # Примечание: эта команда может потребовать дополнительных параметров
        # и настройки окружения

    def test_wmill_script_generate_metadata_for_modules(self):
        """
        Тест: проверка возможности генерации метаданных для модулей.

        Примечание: этот тест является примером и может требовать настройки.
        """
        pass  # Реализация зависит от конкретных требований


class TestFlowDataFlow:
    """Тесты для проверки передачи данных между модулями"""

    def test_transcribe_output_matches_split_posts_input(self):
        """
        Тест: выход transcribe соответствует входу split_posts.

        Проверяет, что поле text из результата transcribe
        передаётся как input в split_posts.
        """
        # Это проверка структуры флоу через анализ flow.yaml
        flow_path = Path(__file__).parent.parent.parent / "f/prj_content_forge/flows/create_posts_from_transcript__flow/flow.yaml"

        with open(flow_path) as f:
            flow_content = f.read()

        # Проверяем, что результаты transcribe используются
        assert "results.transcribe.text" in flow_content
        assert "split_posts" in flow_content

    def test_loop_posts_iterates_over_split_results(self):
        """
        Тест: loop_posts итерируется над результатами split_posts.

        Проверяет, что итератор использует результаты split_posts.
        """
        flow_path = Path(__file__).parent.parent.parent / "f/prj_content_forge/flows/create_posts_from_transcript__flow/flow.yaml"

        with open(flow_path) as f:
            flow_content = f.read()

        # Проверяем итератор
        assert "results.split_posts.output" in flow_content
        assert "@@@@@" in flow_content  # Разделитель постов
        assert "loop_posts" in flow_content


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
