"""
AP_STYLE_FORMAT - Форматирование текста по AP Stylebook без изменения содержания

ЧТО ДЕЛАЕТ:
- Приводит текст к стилю AP Stylebook
- Сохраняет смысл, факты и структуру текста
- Не ограничивает длину ответа по токенам и символам

ГДЕ ИСПОЛЬЗУЕТСЯ:
- Используется для стилистического форматирования англоязычных текстов

ИСПОЛЬЗУЕТ:
- Resource: u/theatmacreator/finer_c_openrouter
- Shared: f/shared/llm_utils
"""
from f.shared.llm_utils import create_llm_client, generate_completion, get_resource_compat


def normalize_output(input_text: str, output_text: str) -> str:
    """
    Убирает типичные артефакты LLM (узкие пробелы/кавычки),
    но только если таких символов не было в исходном тексте.
    """
    replacements = [
        ("\u202f", " "),  # narrow no-break space
        ("\u00a0", " "),  # no-break space
        ("\u2009", " "),  # thin space
        ("\u200a", " "),  # hair space
        ("\u2060", ""),   # word joiner
        ("\u201c", "\""), # left double quote
        ("\u201d", "\""), # right double quote
        ("\u2018", "'"),  # left single quote
        ("\u2019", "'"),  # right single quote
    ]

    normalized = output_text
    for bad, good in replacements:
        if bad not in input_text:
            normalized = normalized.replace(bad, good)
    return normalized


def main(
    input: str,
    model: str = "openai/gpt-oss-120b:nitro",
    temperature: float = 0.1,
) -> dict:
    """
    Форматирует текст по AP Stylebook без изменения содержания.

    @param input Текст для форматирования
    @param model Модель для использования
    @param temperature Температура генерации
    @return Словарь с полем output - отформатированный текст
    """
    resource = get_resource_compat("u/theatmacreator/finer_c_openrouter")
    client = create_llm_client(resource)

    prompt = f"""# Role
You are an AP Stylebook editor.

# Task
Format the text to AP Stylebook without changing content or meaning.

# Rules
- Preserve all facts, names, numbers, quotes, and intent exactly.
- Do NOT add, remove, or rephrase information.
- Keep the same language as the input.
- For prose text, split long paragraphs so that each paragraph contains about 4–5 sentences (insert blank lines between paragraphs). Do not merge existing paragraphs.
- Preserve headings, bullet/numbered lists, tables, code blocks, and existing markdown structure as-is.
- Keep any existing markdown formatting unchanged.
- Keep symbols as symbols (e.g., %, $, #) if they appear in the input. Do not spell them out.
- Use plain ASCII spaces and straight quotes unless the input already uses curly quotes.
- Do not introduce non-breaking spaces or thin/narrow spaces.
- Only fix style, capitalization, punctuation, abbreviations, and formatting per AP Stylebook.
- Output only the formatted text, nothing else.

# Text
{input}
"""

    result = generate_completion(
        client=client,
        prompt=prompt,
        model=model,
        temperature=temperature,
        max_tokens=None,
    )
    output = normalize_output(input, result)
    return {"output": output}
