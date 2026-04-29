# Инструкции для работы с Windmill (для AI агентов)

## 1. Структура проекта

**Слоистая архитектура:** shared → transformations → projects

```
f/
├── shared/                                    # Инфраструктура (базовые утилиты)
│   ├── __init__.py
│   ├── llm_utils.py                          # LLM-клиенты, retry-логика
│   └── fal_utils.py                          # FAL.ai утилиты
│
├── transformations/                           # Атомарные операции (мультипроектные)
│   ├── transcriber/
│   │   └── transcribe.py                     # Транскрибация через Deepgram
│   ├── post_splitter/
│   │   └── split_posts.py                    # Разбиение текста на посты
│   ├── post_generator/
│   │   └── generate_post.py                  # Генерация готового поста
│   ├── title_generator/
│   │   └── generate_titles.py                # Генерация заголовков
│   ├── image_prompts/
│   │   └── generate_image_prompts.py         # Генерация идей для изображений
│   ├── baserow_post/
│   │   └── create_post.py                    # Создание записи в Baserow
│   ├── fal_image_generator/
│   │   └── generate_image.py                 # Генерация изображений через FAL
│   └── content_forge/
│       └── content_forge_bot.py              # Content Forge бот
│
├── prj_content_forge/                        # Проект: Content Forge
│   ├── baserow_ideas/
│   │   └── save_idea.py                      # Сохранение идей в Baserow
│   ├── publisher/
│   │   ├── publish_to_telegram.py            # Публикация в Telegram
│   │   └── publish_to_telegram.schedule.yaml # Расписание: 15:00 UTC
│   └── flows/
│       └── create_posts_from_transcript__flow/
│           └── flow.yaml                     # Энд-ту-энд пайплайн
│
└── prj_transcriber/                          # Проект: Transcriber
    └── apps/
        └── transcriber__app/                 # Приложение транскрибации
```

### Принципы размещения

| Тип | Куда идёт | Описание |
|-----|-----------|----------|
| **Утилита без бизнес-логики** | `shared/` | LLM-клиенты, retry-логика, базовые функции |
| **Атомарная операция** | `transformations/` | Переиспользуемые блоки логики (transcribe, split, generate) |
| **Бизнес-скрипт проекта** | `prj_<project>/` | Специфичная бизнес-логика (save_idea, publish) |
| **Флоу проекта** | `prj_<project>/flows/` | Оркестрация transformations |
| **Приложение проекта** | `prj_<project>/apps/` | UI для проекта |

### Формат docstring для transformations

Все скрипты в `transformations/` должны иметь docstring:

```python
"""
NAME_SHORT - краткое описание

ЧТО ДЕЛАЕТ:
- Основная функция
- Второстепенная функция

ГДЕ ИСПОЛЬЗУЕТСЯ:
- f/prj_content_forge/flows/create_posts_from_transcript__flow

ИСПОЛЬЗУЕТ:
- Resource: u/theatmacreator/resource_name
- Shared: f/shared/module_name
- External: API endpoint (опционально)
"""
```

### Создание нового проекта

1. Создай папку `f/prj_<project_name>/`
2. Внутри создай подпапки: `scripts/`, `flows/`, `apps/` (по необходимости)
3. Используй transformations из `f/transformations/` для логики
4. Бизнес-специфичные скрипты лежат прямо в `f/prj_<project_name>/`

## 2. Основной рабочий процесс (Workflow)

Выполняй действия строго в этом порядке:

1. **Создание:** Создай файл скрипта в нужной папке:
   - `f/transformations/<name>/script.py` — для атомарных операций
   - `f/prj_<project>/<name>/script.py` — для бизнес-логики проекта
   - `f/shared/<name>.py` — для переиспользуемых утилит

2. **Docstring (для transformations):** Добавь описание:
   ```python
   """
   NAME - краткое описание

   ЧТО ДЕЛАЕТ:
   - Функция 1
   - Функция 2

   ГДЕ ИСПОЛЬЗУЕТСЯ:
   - f/prj_<project>/flows/...

   ИСПОЛЬЗУЕТ:
   - Resource: u/...
   - Shared: f/shared/...
   """
   ```

3. **Метаданные (Важно!):** Сразу после создания/изменения аргументов:
   ```bash
   wmill script generate-metadata f/path/to/script.py --yes
   ```
   Это создаст `.script.yaml` и `.script.lock`. Не редактируй их вручную.

4. **Отправка на сервер:**
   ```bash
   wmill sync push --yes
   ```

5. **Тестирование:**
   ```bash
   wmill script run f/path/to/script -d '{"param1": "value"}'
   ```

## 3. Работа с LLM (OpenRouter/OpenAI)

### Используйте общий модуль `f/shared/llm_utils`

**НЕ повторяйте код!** Используйте существующие утилиты:
```python
from f.shared.llm_utils import create_llm_client, generate_completion

def main(input: str):
    openrouter = wmill.get_resource("u/theatmacreator/finer_c_openrouter")
    client = create_llm_client(openrouter)

    result = generate_completion(
        client=client,
        prompt=f"Текст: {input}",
        model="google/gemini-3-flash-preview",
        temperature=0.1,
    )
    return {"output": result}
```

### Доступные функции в `f/shared/llm_utils.py`

- `OpenRouterResource` — TypedDict для ресурса (apiKey, X_Title)
- `create_llm_client(resource)` — создаёт настроенный OpenAI клиент для OpenRouter
- `generate_completion(client, prompt, model, ...)` — обёртка с retry-логикой

### Правила
1. **Используйте только OpenAI SDK** — не используйте `requests` напрямую
2. **Ресурс хардкодится** — всегда `wmill.get_resource("u/theatmacreator/finer_c_openrouter")`
3. **Ресурс не в параметрах функции** — не добавляйте его в `main()`, чтобы не выбирать в UI

## 4. Написание кода (Python)

### Базовый шаблон transformation скрипта

```python
"""
NAME_SHORT - краткое описание операции

ЧТО ДЕЛАЕТ:
- Основная функция
- Второстепенная функция (если есть)

ГДЕ ИСПОЛЬЗУЕТСЯ:
- f/prj_content_forge/flows/flow_name

ИСПОЛЬЗУЕТ:
- Resource: u/theatmacreator/resource_name
- Shared: f/shared/llm_utils
"""
import wmill
from f.shared.llm_utils import create_llm_client, generate_completion


def main(
    input: str,
    model: str = "google/gemini-3-flash-preview"
) -> dict:
    """
    Описание функции.

    @param input Описание параметра
    @param model Модель для использования
    @return Описание возвращаемого значения
    """
    resource = wmill.get_resource("u/theatmacreator/resource_name")
    client = create_llm_client(resource)

    result = generate_completion(
        client=client,
        prompt=f"# Задача\n{input}",
        model=model,
        temperature=0.1,
    )

    return {"output": result}
```

### Базовый шаблон проектного скрипта

```python
"""
Краткое описание что делает скрипт.
"""
import wmill

def main(param1: str, param2: str = "default") -> dict:
    """
    Описание функции.

    @param param1 Описание параметра
    @param param2 Описание параметра
    @return Описание возвращаемого значения
    """
    # Бизнес-логика проекта
    return {"result": "...")
```

## 5. Правила оформления флоу

### Именование

**Имя папки флоу:**

```
<action>_<target>_<entity>__flow
```

| Компонент | Описание | Примеры |
|-----------|----------|---------|
| action | Глагол действия | create, process, send, sync, update |
| target | Объект действия | posts, users, reports, notifications |
| entity | (опционально) Доп. контекст | from_transcript, daily, weekly |
| __flow | Суффикс флоу | обязателен |

**Примеры:**
```
create_posts_from_transcript__flow/    ✅
send_daily_notifications__flow/        ✅
sync_users_from_crm__flow/             ✅
process_invoices__flow/                ✅
```

**ID модулей внутри флоу:**

Используй короткие глагольные идентификаторы:

```yaml
modules:
  - id: transcribe        # ✅ глагол
  - id: split_posts       # ✅ глагол_объект
  - id: gen_post          # ✅ сокращение (gen = generate)
  - id: add_to_baserow    # ✅ фраза с нижним подчёркиванием
```

**Правила:**
- Простой глагол: `transcribe`, `fetch`, `parse`
- Глагол_существительное: `split_posts`, `gen_titles`, `send_email`

### Структура файла

```yaml
# --- МЕТАДАННЫЕ ---
summary: Краткое описание (одна строка)
description: >
  Подробное описание процесса.
  Может быть многострочным.

value:
  modules:
    - id: step_1
      summary: Краткое описание шага
      value:
        type: script
        path: f/transformations/<category>/<script>

schema:
  $schema: 'https://json-schema.org/draft/2020-12/schema'
  type: object
  order: [...]
  properties: {...}

ws_error_handler_muted: false
```

### Размещение

```
f/
└── prj_<project>/
    └── flows/
        └── <action>_<target>_<entity>__flow/
            └── flow.yaml
```

## 6. Тестирование и проверка работоспособности  

После того как скрипт создан, тебе необходимо найти способ проверить его работоспособность локально. После проверки удали все временные файлы. 

### Добавление новых общих функций

Если нужно добавить переиспользуемый код:
1. Сначала проверь `f/shared/llm_utils.py` — возможно, функция уже есть
2. Если нет — добавь функцию в `f/shared/llm_utils.py` с docstring
3. Не создавай отдельные модули без необходимости

## 7. Частые ошибки и правила

1. **Дублирование кода:**
   - Перед написанием нового кода проверь `f/shared/llm_utils.py`
   - Если логика используется в 2+ скриптах — вынеси в shared

2. **Неправильное размещение:**
   - Атомарные операции → `f/transformations/`
   - Бизнес-логика → `f/prj_<project>/`
   - Утилиты → `f/shared/`

3. **Разные подходы к API:**
   - Используй только OpenAI SDK, не requests
   - Вся логика повторов — в `generate_completion()`

4. **Синхронизация:**
   - Если ресурс создан в веб-интерфейсе, сначала сделай `wmill sync pull --yes`.
   - Никогда не пушь, если не сгенерировал метаданные.

5. **Аргументы:**
   - При тесте через CLI ресурсы передаются строкой: `"$res:u/user/resource_name"`.

6. **Docstring для transformations:**
   - Обязателен формат: ЧТО ДЕЛАЕТ / ГДЕ ИСПОЛЬЗУЕТСЯ / ИСПОЛЬЗУЕТ
   - Без него сложно понять контекст использования

## 8. Запрещённые папки и файлы

- `scripts/` — не используется, всё в `f/`
- `resources/` — не используется, ресурсы в `u/`
- `f/apps/` — устарело, приложения теперь в `f/prj_<project>/apps/`
- `f/flows/` — устарело, флоу теперь в `f/prj_<project>/flows/`
- Создание скриптов вне `shared/`, `transformations/`, `prj_*/` — запрещено
