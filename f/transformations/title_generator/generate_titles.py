"""
GENERATE_TITLES - генерация вариантов заголовков для поста

ЧТО ДЕЛАЕТ:
- Генерирует 5 вариантов заголовков на основе тезисов поста
- Формат: без кавычек, двоеточий и точек
- Каждое название на отдельной строке
- Без комментариев и пояснений

ГДЕ ИСПОЛЬЗУЕТСЯ:
- f/prj_content_forge/flows/create_posts_from_transcript__flow

ИСПОЛЬЗУЕТ:
- Resource: u/theatmacreator/finer_c_openrouter
- Shared: f/shared/llm_utils
"""
from f.shared.llm_utils import create_llm_client, generate_completion, get_resource_compat


def main(
    input: str,
    model: str = "deepseek/deepseek-chat"
) -> dict:
    """
    Генерирует 5 вариантов названий для поста на основе тезисов.

    @param input Тезисы поста для генерации названий
    @param model Модель для использования (по умолчанию google/gemini-3-flash-preview)
    @return Словарь с сгенерированными названиями
    """
    openrouter = get_resource_compat("u/theatmacreator/finer_c_openrouter")
    client = create_llm_client(openrouter)

    prompt = f"""# Задача
Твоя задача предложить 5 вариантов названий для поста с переданными тезисами

# Формат ответа
- Не используй кавычки, двоеточие и точку
- Каждое название на отдельной строке
- Не никакие добавляй пояснения

# Тезисы
{input}"""

    output = generate_completion(
        client=client,
        prompt=prompt,
        model=model,
        temperature=0.1,
        max_tokens=300,
    )

    return {"output": output}
