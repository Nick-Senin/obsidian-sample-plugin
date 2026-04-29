# Windmill HTTP Routes API - Полное исследование

## 1. API Endpoints для создания HTTP Routes

Windmill использует термин **HTTP Triggers** для HTTP Routes. Основные эндпоинты:

### 1.1 Создание HTTP триггеров

| Метод | Эндпоинт | Описание |
|-------|----------|----------|
| `POST` | `/w/{workspace}/http_triggers/create` | Создание одного HTTP триггера |
| `POST` | `/w/{workspace}/http_triggers/create_many` | Массовое создание HTTP триггеров |
| `POST` | `/w/{workspace}/http_triggers/update/{path}` | Обновление существующего триггера |
| `DELETE` | `/w/{workspace}/http_triggers/delete/{path}` | Удаление HTTP триггера |
| `GET` | `/w/{workspace}/http_triggers/list` | Список всех HTTP триггеров |
| `GET` | `/w/{workspace}/http_triggers/get/{path}` | Получение конкретного триггера |

### 1.2 Схема NewHttpTrigger

```json
{
  "type": "object",
  "properties": {
    "path": {"type": "string"},
    "script_path": {"type": "string"},
    "route_path": {"type": "string"},
    "workspaced_route": {"type": "boolean"},
    "summary": {"type": "string"},
    "description": {"type": "string"},
    "is_flow": {"type": "boolean"},
    "http_method": {
      "type": "string",
      "enum": ["get", "post", "put", "delete", "patch"]
    },
    "is_async": {"type": "boolean"},
    "authentication_method": {
      "type": "string",
      "enum": ["none", "windmill", "api_key", "basic_http", "custom_script", "signature"]
    },
    "is_static_website": {"type": "boolean"},
    "wrap_body": {"type": "boolean"},
    "raw_string": {"type": "boolean"}
  },
  "required": [
    "path",
    "script_path",
    "route_path",
    "is_flow",
    "is_async",
    "authentication_method",
    "http_method",
    "is_static_website"
  ]
}
```

### 1.3 Пример запроса на создание

```bash
curl -X POST "https://app.windmill.dev/w/myworkspace/http_triggers/create" \
  -H "Authorization: Bearer <your_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "path": "myapi/hello",
    "script_path": "f/hello/world",
    "route_path": "custom/hello",
    "workspaced_route": false,
    "is_flow": false,
    "is_async": true,
    "authentication_method": "api_key",
    "http_method": "post",
    "is_static_website": false
  }'
```

---

## 2. Аутентификация

### 2.1 Создание токена через CLI

```bash
wmill user create-token
```

### 2.2 Создание токена через API

```
POST /users/tokens/create
POST /users/tokens/impersonate
```

### 2.3 Использование токена

Все запросы к API должны включать заголовок:

```http
Authorization: Bearer <your_token>
```

---

## 3. OpenAPI Спецификация

Windmill предоставляет полную OpenAPI 3.0.3 спецификацию:

- **URL**: `https://app.windmill.dev/api/openapi.json`
- **Интерактивная документация**: `https://app.windmill.dev/openapi.html`

Спецификация содержит:
- Все доступные API эндпоинты
- Схемы запросов/ответов
- Методы аутентификации
- Примеры использования

---

## 4. Клиентские библиотеки

### 4.1 Python (windmill-api)

```bash
pip install windmill-api
```

```python
from windmill_api import WindmillApi

api = WindmillApi(
    base_url="https://app.windmill.dev",
    token="your_token"
)

# Создание HTTP триггера
result = api.create_http_trigger(
    workspace="myworkspace",
    new_http_trigger={
        "path": "api/hello",
        "script_path": "f/hello/script",
        "route_path": "hello",
        "is_flow": False,
        "is_async": True,
        "authentication_method": "api_key",
        "http_method": "post",
        "is_static_website": False
    }
)
```

### 4.2 Rust (windmill-api)

```toml
[dependencies]
windmill-api = "1.544.2"
```

Библиотека автоматически сгенерирована из OpenAPI спецификации.

### 4.3 TypeScript/JavaScript

```typescript
export async function main(url: string, body: object = {}, headers: Record<string, string> = {}) {
  const resp = await fetch(url, {
    method: "POST",
    headers: headers,
    body: JSON.stringify(body)
  });
  return await resp.json();
}
```

---

## 5. Backend архитектура

### 5.1 Технологический стек

- **Язык**: Rust
- **Архитектура**: Микросервисы
- **Масштабирование**: Горизонтальное, stateless API
- **Поддерживаемые языки скриптов**: Python, TypeScript (Deno), Go, Bash

### 5.2 Репозиторий

**GitHub**: https://github.com/windmill-labs/windmill

Структура бэкенда:
- `backend/windmill-worker/src/worker.rs` - Worker реализация
- `backend/windmill-api/` - API сервер
- `backend/windmill-frontend/` - Frontend компоненты

---

## 6. Полезные ресурсы

### Документация
- [HTTP Routes Documentation](https://www.windmill.dev/docs/core_concepts/http_routing)
- [Triggers Documentation](https://www.windmill.dev/docs/getting_started/triggers)
- [WebSocket Triggers](https://www.windmill.dev/docs/core_concepts/websocket_triggers)
- [NATS Triggers](https://www.windmill.dev/docs/core_concepts/nats_triggers)

### GitHub
- [Основной репозиторий](https://github.com/windmill-labs/windmill)
- [Helm Charts](https://github.com/windmill-labs/windmill-helm-charts)
- [Windmill Overview](https://github.com/windmill-labs/windmill/blob/main/windmill-overview.mdc)

### Инструменты
- [Rust API Client](https://crates.io/crates/windmill-api/1.544.2)
- [Python API Client](https://pypi.org/project/windmill-api/)
- [Windmill Hub - Примеры скриптов](https://hub.windmill.dev/)

### Сообщество
- [Issue #5115](https://github.com/windmill-labs/windmill/issues/5115) - Signature verification for webhooks
- [Issue #4697](https://github.com/windmill-labs/windmill/issues/4697) - Creating HTTP routes with access control
- [StackOverflow Discussion](https://stackoverflow.com/questions/79579433/windmill-how-to-pass-variables-from-one-node-or-trigger-to-another)

---

## 7. Примеры использования

### 7.1 Создание REST API из скрипта

```python
import wmill

# Скрипт: f/hello/world.py
def main(name: str = "World") -> dict:
    return {"message": f"Hello, {name}!"}
```

```bash
# Создание HTTP триггера
curl -X POST "https://app.windmill.dev/w/myworkspace/http_triggers/create" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "path": "api/hello",
    "script_path": "f/hello/world",
    "route_path": "hello",
    "is_flow": false,
    "is_async": true,
    "authentication_method": "none",
    "http_method": "get",
    "is_static_website": false
  }'

# Вызов созданного API
curl "https://app.windmill.dev/api/hello?name=Claude"
```

### 7.2 Массовое создание HTTP триггеров

```python
# Использование create_many для批量 создания
triggers = [
    {
        "path": f"api/v1/endpoint_{i}",
        "script_path": f"f/scripts/endpoint_{i}",
        "route_path": f"endpoint_{i}",
        "is_flow": False,
        "is_async": True,
        "authentication_method": "api_key",
        "http_method": "post",
        "is_static_website": False
    }
    for i in range(10)
]

api.create_http_triggers(
    workspace="myworkspace",
    new_http_trigger=triggers
)
```

---

## 8. Методы аутентификации для HTTP Routes

| Метод | Описание | Использование |
|-------|----------|---------------|
| `none` | Без аутентификации | Публичные API |
| `windmill` | Windmill users | Требует авторизованного пользователя |
| `api_key` | API Token | Для программного доступа |
| `basic_http` | Basic Auth | username/password |
| `custom_script` | Кастомная логика | Собственная проверка через скрипт |
| `signature` | Подпись запроса | Для вебхуков с верификацией |

---

## 9. Changelog и новые возможности

Windmill активно развивается. В последних версиях добавлено:

- Импорт спецификаций HTTP триггеров из JSON/YAML файлов
- Загрузка спецификаций по URL
- Кастомные HTTP заголовки ответов
- Установка кастомных HTTP status codes

---

## 10. Заключение

Windmill предоставляет мощный API для программного создания HTTP Routes:

✅ **Полный OpenAPI spec** - все эндпоинты задокументированы
✅ **Клиентские библиотеки** - Python, Rust, TypeScript
✅ **Bearer Token Auth** - простая и безопасная аутентификация
✅ **Rust backend** - высокая производительность
✅ **Open Source** - полный код доступен на GitHub

Для автоматизации создания HTTP Routes рекомендуется:
1. Использовать Python клиент `windmill-api`
2. Создавать токены через `wmill user create-token`
3. Использовать `create_many` для массового создания
4. Хранить конфигурацию маршрутов в YAML/JSON файлах
