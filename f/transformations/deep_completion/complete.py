"""
DEEP_COMPLETION - Итеративное улучшение знаний с проверкой воспроизводимости

ЧТО ДЕЛАЕТ:
- Проверяет воспроизводимость знаний (через repro_checklist)
- Если score < 7 - улучшает знания через Perplexity с поиском первоисточника
- Повторяет до достижения reproducibility >= 7 или max_iterations

ГДЕ ИСПОЛЬЗУЕТСЯ:
- Используется для доработки знаний до приемлемого качества

ИСПОЛЬЗУЕТ:
- Resource: u/theatmacreator/finer_c_openrouter
- Shared: f/shared/llm_utils
- Transformation: f/transformations/repro_checklist/check.py
"""
import wmill
from f.shared.llm_utils import create_llm_client, generate_completion


def check_reproducibility(input: str) -> dict:
    """Проверяет воспроизводимость через repro_checklist transformation"""
    # Вызываем repro_checklist как вложенный скрипт
    result = wmill.run_script_by_path(
        "f/transformations/repro_checklist/check",
        {"input": input}
    )

    try:
        if isinstance(result, str):
            import json
            return json.loads(result)
        return result
    except:
        return {"reproducibility": 0, "reproducibility reasoning": "Parse error"}


def improve_knowledge(input: str, reasoning: str, client) -> str:
    """Улучшает знания через Perplexity с цитированием"""
    # Формируем prompt для улучшения
    prompt = f"""# Task
Найди и добавь деталей в переданные знания чтобы они получили максимальную оценку воспроизводимости.

ТВОЯ ЗАДАЧА НАЙТИ ПЕРВОИСТОЧНИК И ДОПОЛНИТЬ ДЕТАЛИ ТОЛЬКО ИЗ НЕГО!

# Output format
Только уточненные знания в том же формате, в котором они были переданы изначально.

# Замечания по воспроизводимости
{reasoning}

# Input knowledge
{input}
"""

    result = generate_completion(
        client=client,
        prompt=prompt,
        model="perplexity/sonar-pro-search",
        temperature=0.1,
        max_tokens=2000,
    )

    return result


def main(
    input: str,
    max_iterations: int = 5
) -> dict:
    """
    Итеративно улучшает знания до достижения reproducibility >= 7.

    @param input Исходные знания для улучшения
    @param max_iterations Максимальное количество итераций
    @return Словарь с полями output, reproducibility, iterations
    """
    resource = wmill.get_resource("u/theatmacreator/finer_c_openrouter")
    client = create_llm_client(resource)

    current_knowledge = input

    for i in range(max_iterations):
        # 1. Проверить воспроизводимость
        check_result = check_reproducibility(current_knowledge)
        repro_score = check_result.get("reproducibility", 0)

        # 2. Если score >= 7 - завершить
        if repro_score >= 7:
            return {
                "output": current_knowledge,
                "reproducibility": repro_score,
                "iterations": i + 1,
                "reasoning": check_result.get("reproducibility reasoning", "")
            }

        # 3. Улучшить знания через Perplexity
        reasoning = check_result.get("reproducibility reasoning", "")
        current_knowledge = improve_knowledge(current_knowledge, reasoning, client)

    return {
        "output": current_knowledge,
        "reproducibility": check_result.get("reproducibility", 0),
        "iterations": max_iterations,
        "max_iterations_reached": True
    }
