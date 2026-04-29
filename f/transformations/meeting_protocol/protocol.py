"""
MEETING_PROTOCOL - Анализ транскрипта митинга

ЧТО ДЕЛАЕТ:
- Анализирует транскрипт митинга
- Извлекает следующие действия, протокол, ключевые моменты

ГДЕ ИСПОЛЬЗУЕТСЯ:
- Используется как самостоятельный инструмент для анализа встреч

ИСПОЛЬЗУЕТ:
- Resource: u/theatmacreator/finer_c_openrouter
- Shared: f/shared/llm_utils
"""
import wmill
from f.shared.llm_utils import create_llm_client, generate_completion


def main(
    input: str,
    model: str = "openai/gpt-4o-mini-2024-07-18"
) -> dict:
    """
    Анализирует транскрипт митинга и извлекает протокол.

    @param input Транскрипт митинга
    @param model Модель для использования
    @return Словарь с полем output - анализ встречи
    """
    resource = wmill.get_resource("u/theatmacreator/finer_c_openrouter")
    client = create_llm_client(resource)

    prompt = f"""## TASK
- Extract all tasks to do, into a single list.

## ANSWER FORMAT
- Answer STRICTLY in the language of the original transcript.

## INPUT
\"{input}\"
"""

    result = generate_completion(
        client=client,
        prompt=prompt,
        model=model,
        temperature=0.2,
    )

    return {"output": result}
