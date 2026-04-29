"""
SOFT_EXPLAIN - Объяснение понятия на 4 уровнях сложности

ЧТО ДЕЛАЕТ:
- Объясняет переданное понятие на 4-х уровнях сложности
- От уровня ребёнка до экспертного уровня

ГДЕ ИСПОЛЬЗУЕТСЯ:
- Используется как самостоятельный инструмент для объяснения концепций

ИСПОЛЬЗУЕТ:
- Resource: u/theatmacreator/finer_c_openrouter
- Shared: f/shared/llm_utils
"""
import wmill
from f.shared.llm_utils import create_llm_client, generate_completion


def main(
    input: str,
    model: str = "anthropic/claude-sonnet-4.5"
) -> dict:
    """
    Объясняет понятие на 4 уровнях сложности.

    @param input Понятие или термин для объяснения
    @param model Модель для использования
    @return Словарь с полем output - объяснение на 4 уровнях
    """
    resource = wmill.get_resource("u/theatmacreator/finer_c_openrouter")
    client = create_llm_client(resource)

    prompt = f"объясни на 4-х уровнях сложности что значит {input}"

    result = generate_completion(
        client=client,
        prompt=prompt,
        model=model,
        temperature=0.1,
    )

    return {"output": result}
