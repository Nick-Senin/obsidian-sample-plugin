# Тесты для Windmill проекта

Этот каталог содержит тесты для Windmill скриптов и флоу.

## Структура

```
tests/
├── fixtures/              # Тестовые данные
│   ├── sample_transcript.json
│   ├── expected_split.json
│   └── flow_input.json
│
├── unit/                  # Юнит-тесты для transformations
│   └── test_split_posts.py
│
├── integration/           # Интеграционные тесты для флоу
│   └── test_flow.py
│
└── README.md             # Этот файл
```

## Установка зависимостей

```bash
pip install pytest pytest-mock
```

## Запуск тестов

### Все тесты

```bash
# Из корня проекта
pytest tests/ -v

# Только с покрытием (если установлен pytest-cov)
pytest tests/ --cov=f/transformations --cov-report=html
```

### Юнит-тесты

```bash
pytest tests/unit/ -v
```

### Интеграционные тесты

```bash
pytest tests/integration/ -v
```

### Конкретный тест

```bash
pytest tests/unit/test_split_posts.py::TestSplitPosts::test_split_posts_returns_dict_with_output_key -v
```

## Тестирование через wmill CLI

### Тестирование отдельного скрипта

```bash
# Из корня проекта
wmill script run f/transformations/post_splitter/split_posts -d '{
  "input": "Текст для тестирования"
}'
```

### Тестирование флоу

```bash
wmill script run f/prj_content_forge/flows/create_posts_from_transcript__flow -d @tests/fixtures/flow_input.json
```

## Написание новых тестов

### Юнит-тест для transformation

1. Создай файл в `tests/unit/test_<name>.py`
2. Используй `pytest` и `unittest.mock` для моков
3. Следуй структуре существующих тестов

```python
from unittest.mock import Mock, patch
import pytest

class TestMyTransformation:
    @pytest.fixture
    def mock_wmill_resource(self):
        return {"apiKey": "test-key"}

    def test_my_function(self, mock_wmill_resource):
        with patch('wmill.get_resource', return_value=mock_wmill_resource):
            from f.transformations.my_script import main
            result = main(param="value")
            assert result == expected
```

### Интеграционный тест для флоу

1. Создай файл в `tests/integration/test_<flow_name>.py`
2. Добавь фикстуры в `tests/fixtures/`
3. Проверяй структуру флоу, наличие модулей, валидность схемы

## Тестовые данные

Фикстуры находятся в `tests/fixtures/`:

- `sample_transcript.json` — пример транскрипции
- `expected_split.json` — ожидаемые результаты разбиения
- `flow_input.json` — входные данные для тестирования флоу

## Полезные команды

```bash
# Посмотреть список всех тестов
pytest tests/ --collect-only

# Запустить с остановкой на первом падении
pytest tests/ -x

# Запустить с выводом print
pytest tests/ -s

# Запустить только быстрые тесты
pytest tests/ -m "not slow"
```
