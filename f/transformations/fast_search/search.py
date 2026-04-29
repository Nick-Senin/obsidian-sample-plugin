"""
FAST_SEARCH - Последовательный поиск через 3 модели

ЧТО ДЕЛАЕТ:
- Выполняет поиск по запросу через 3 разные модели последовательно
- Объединяет результаты в единый ответ

ГДЕ ИСПОЛЬЗУЕТСЯ:
- Используется для получения комплексного результата от разных моделей

ИСПОЛЬЗУЕТ:
- Resource: u/theatmacreator/finer_c_openrouter
- Shared: f/shared/llm_utils
"""
import wmill
from f.shared.llm_utils import create_llm_client, generate_completion


def search_with_model(query: str, model: str, client) -> str:
    """Выполняет поиск с указанной моделью"""
    print(f"[DEBUG] Calling model: {model}")

    prompt = f"""# Задача
Разреши вопрос или найди нужную информацию по запросу. Будь конкретным и предоставь наиболее полезную информацию.

# Запрос
{query}
"""

    result = generate_completion(
        client=client,
        prompt=prompt,
        model=model,
        temperature=0.5,
        max_tokens=1000,
    )

    print(f"[DEBUG] Result length: {len(result)}")
    return result


def merge_search_results(results: list) -> str:
    """Объединяет результаты от разных моделей"""
    if not results:
        return ""

    # Простое объединение с разделителем
    merged = "\n\n---\n\n".join(results)
    return merged


def main(input: str) -> dict:
    """
    Выполняет последовательный поиск через 3 модели.

    @param input Поисковый запрос
    @return Словарь с полем output - объединённый результат поиска
    """
    resource = wmill.get_resource("u/theatmacreator/finer_c_openrouter")
    client = create_llm_client(resource)

    results = []
    errors = []

    # Последовательно вызываем 3 модели
    models = [
        "anthropic/claude-sonnet-4.5",
        "z-ai/glm-4.7",
        "perplexity/sonar-pro-search"
    ]

    for i, model in enumerate(models):
        try:
            print(f"[DEBUG] Starting model {i+1}/{len(models)}: {model}")
            result = search_with_model(input, model, client)
            results.append(result)
            print(f"[DEBUG] Model {i+1} completed successfully")
        except Exception as e:
            print(f"[DEBUG] Model {i+1} failed: {e}")
            errors.append(f"{model}: {str(e)}")
            results.append(f"[Error with {model}: {str(e)}]")

    # Объединяем результаты
    merged = merge_search_results(results)

    output = merged
    if errors:
        output = f"{merged}\n\n[DEBUG ERRORS: {'; '.join(errors)}]"

    return {"output": output}
