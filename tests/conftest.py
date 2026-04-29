"""
Конфигурация pytest для тестов Windmill проекта

Создаёт mock для модуля wmill, чтобы тесты могли запускаться локально
без установленного Windmill SDK.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock
import pytest

# Добавляем корень проекта в path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# Создаём mock модуль wmill
sys.modules['wmill'] = MagicMock()


def pytest_configure(config):
    """Конфигурация pytest - добавление кастомных маркеров"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )


@pytest.fixture(scope="session")
def wmill():
    """Mock модуля wmill для использования в тестах"""
    import wmill
    return wmill
