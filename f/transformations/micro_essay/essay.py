"""
MICRO_ESSAY - Написание микроэссе в стиле Пола Грэма

ЧТО ДЕЛАЕТ:
- Пишет краткое эссе (до 250 слов) в стиле Пола Грэма
- На основе переданных тезисов

ГДЕ ИСПОЛЬЗУЕТСЯ:
- Используется для генерации контента в стиле PG

ИСПОЛЬЗУЕТ:
- Resource: u/theatmacreator/finer_c_openrouter
- Shared: f/shared/llm_utils
"""
import wmill
from f.shared.llm_utils import create_llm_client, generate_completion


def main(
    input: str,
    model: str = "deepseek/deepseek-r1"
) -> dict:
    """
    Пишет микроэссе в стиле Пола Грэма.

    @param input Тезисы для эссе
    @param model Модель для использования
    @return Словарь с полем output - микроэссе на русском
    """
    resource = wmill.get_resource("u/theatmacreator/finer_c_openrouter")
    client = create_llm_client(resource)

    prompt = f"""# IDENTITY and PURPOSE

You are an expert on writing concise, clear, and illuminating essays on the topic of the input provided.

# OUTPUT INSTRUCTIONS

- Write the essay in the style of Paul Graham, who is known for this concise, clear, and simple style of writing.
- That means the essay should be written in a simple, conversational style, not in a grandiose or academic style.
- Use the same style, vocabulary level, and sentence structure as Paul Graham.
- Write essay in russian!
- The essay should be a maximum of 250 words.
- Use absolutely ZERO cliches or jargon or journalistic language.
- Do not include common setup language in any sentence, including: in conclusion, in closing, etc.
- Do not output warnings or notes—just the output requested.

# OUTPUT FORMAT

- Output a full, publish-ready essay about the content provided using the instructions above.

# INPUT:

{input}
"""

    result = generate_completion(
        client=client,
        prompt=prompt,
        model=model,
        temperature=0.7,
    )

    return {"output": result}
