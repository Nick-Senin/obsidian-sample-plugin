"""
GENERATE_POST - генерация готового поста из тезисов/сырого текста

ЧТО ДЕЛАЕТ:
- Превращает тезисы или черновик в готовый пост для соцсетей
- Загружает жанровые настройки из Baserow (table/747)
- Если у жанра указан модуль стиля -> генерирует через модуль
- Если модуль не указан -> генерирует через промпт из Baserow
- Улучшает структуру и подачу (абзацы, списки)

ГДЕ ИСПОЛЬЗУЕТСЯ:
- f/prj_content_forge/flows/create_posts_from_transcript__flow
- f/prj_content_forge/process_recording

ИСПОЛЬЗУЕТ:
- Resource: u/theatmacreator/finer_c_openrouter
- Shared: f/shared/llm_utils
- Script: f/prj_content_forge/baserow/get_genres (для получения жанров)
"""
import requests
import wmill
from f.shared.llm_utils import create_llm_client, generate_completion, get_resource_compat

DEFAULT_GENRE_PROMPT = "Ясно, структурно, без воды. Используй абзацы и списки."


def get_genre_with_module(genre_name: str):
    """Получает данные жанра напрямую из Baserow с полем module_path."""
    baserow = get_resource_compat("u/theatmacreator/baserow_api")
    baserow_token = baserow if isinstance(baserow, str) else (baserow.get("token") if isinstance(baserow, dict) else None)
    if not baserow_token:
        raise ValueError("Baserow token is missing in resource u/theatmacreator/baserow_api")
    url = "https://content.nicksenin.com/api/database/rows/table/747/"
    headers = {
        "Authorization": f"Token {baserow_token}",
        "Content-Type": "application/json",
    }

    response = requests.get(url, params={"user_field_names": "true", "size": "100"}, headers=headers)
    response.raise_for_status()

    data = response.json()
    results = data.get("results", [])

    for row in results:
        if row.get("Название") == genre_name:
            return {
                "id": str(row.get("id", "")),
                "description": row.get("Описание", ""),
                "module_path": row.get("Название модуля для стиля текста", "") or None
            }
    return None


def generate_via_module(input_text: str, module_path: str) -> str:
    """Генерирует пост через вызов windmill модуля."""
    try:
        result = wmill.run_script_by_path(
            module_path,
            {"input_text": input_text}
        )
        return result.get("output", input_text)
    except Exception:
        # При ошибке возвращаем входной текст
        return input_text


def generate_via_prompt(input_text: str, genre_description: str, model: str, client) -> str:
    """Генерирует пост через прямой промпт к LLM."""
    prompt = f"""# Задача
На основе текста ниже напиши готовый пост для соцсетей на русском языке.

# Стиль
{genre_description}

# Правила
- Не добавляй никаких пояснений, комментариев, заголовков типа "Пост:".
- Если уместно, используй короткие абзацы и маркированные списки.
- Сохраняй смысл исходного текста, но улучши подачу.

# Текст
{input_text}"""

    return generate_completion(
        client=client,
        prompt=prompt,
        model=model,
        temperature=0.2,
        max_tokens=1500,
    )


def main(
    input: str,
    genre_name: str = "Обычные контентные посты",
    model: str = "google/gemini-3-flash-preview",
) -> dict:
    """
    Превращает тезисы/сырой текст в готовый пост с учётом жанра.

    @param input Тезисы/сырой текст (основа поста)
    @param genre_name Жанр поста (для выбора стиля генерации)
    @param model Модель для использования (только для прямой генерации)
    @return Словарь с итоговым текстом поста
    """
    genre_data = get_genre_with_module(genre_name)

    if genre_data and genre_data.get("module_path"):
        output = generate_via_module(input, genre_data["module_path"])
    elif genre_data and genre_data.get("description"):
        openrouter = get_resource_compat("u/theatmacreator/finer_c_openrouter")
        client = create_llm_client(openrouter)
        output = generate_via_prompt(input, genre_data["description"], model, client)
    else:
        openrouter = get_resource_compat("u/theatmacreator/finer_c_openrouter")
        client = create_llm_client(openrouter)
        output = generate_via_prompt(input, DEFAULT_GENRE_PROMPT, model, client)

    return {"output": output}
