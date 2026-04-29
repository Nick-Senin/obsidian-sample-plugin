"""
EXTRACT_SOURCE_INFO_JSON - Извлечение библиографической информации в JSON

ЧТО ДЕЛАЕТ:
- Извлекает данные о книге или научной статье из произвольных входных данных
- Возвращает результат в формате JSON с полями title, author, publisher, publish_year, publish_place

ГДЕ ИСПОЛЬЗУЕТСЯ:
- Используется как часть линтера для структурированного хранения библиографических данных

ИСПОЛЬЗУЕТ:
- Resource: u/theatmacreator/finer_c_openrouter
- Shared: f/shared/llm_utils
"""
import wmill
from f.shared.llm_utils import create_llm_client, generate_completion
import json


def main(
    input: str,
    model: str = "openai/gpt-4o-2024-11-20"
) -> dict:
    """
    Извлекает библиографическую информацию в JSON формате.

    @param input Произвольные данные о книге или статье
    @param model Модель для использования
    @return Словарь с полями output (строка JSON) и data (распаршенный dict)
    """
    resource = wmill.get_resource("u/theatmacreator/finer_c_openrouter")
    client = create_llm_client(resource)

    prompt = f"""# Роль
Ты лучший эксперт по извлечению и упорядочиванию данных.

# Задача
Пользователь передает тебе произвольные входные данные о книге или научной статье. Твоя задача найти в этих данных информации о :
- названии работы
- авторе
- годе публикации
- месте публикации
- издателе

Сделай глубокий вдох и подумай очень хорошо, от этого зависит моя карьера.

# Правила
- Если входные данные переданы на английском ответ должен быть долностью на английском языке.
- Если входные данные переданы на русском ответ должен быть долностью на русском языке.
- Если город издания не указан добавь город соответствующий издателю.
- Если авторов несколько нужно указать всех.

# Формат ответа
Отвечай ТОЛЬКО в формате JSON (без markdown кода):
{{"title": "Полное название источника", "author": "Автор в формате Фамилия И. О.", "publisher": "Издательство", "publish_year": "Год издания", "publish_place": "Место издания"}}

Пример:
{{"title": "Физиология трудовых процессов", "author": "Виноградов М. И.", "publisher": "Медицина", "publish_year": "1966", "publish_place": "Москва"}}

Конец инструкций.

# Входные данные
{input}
"""

    result = generate_completion(
        client=client,
        prompt=prompt,
        model=model,
        temperature=0.3,
    )

    # Пытаемся распарсить JSON
    try:
        # Очищаем результат от markdown кода если есть
        cleaned = result.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("\n", 1)[0]
        cleaned = cleaned.strip()
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()

        data = json.loads(cleaned)
    except Exception:
        # Если не удалось распарсить, возвращаем как есть
        data = {"raw": result}

    return {"output": result, "data": data}
