"""
FORMAT - Форматирование текста

ЧТО ДЕЛАЕТ:
- Форматирует текст, разбивая на части по 3000 символов
- Убирает опечатки, добавляет форматирование и абзацы
- Объединяет результаты в единый текст

ГДЕ ИСПОЛЬЗУЕТСЯ:
- Используется для форматирования необработанного текста

ИСПОЛЬЗУЕТ:
- Resource: u/theatmacreator/finer_c_openrouter
- Shared: f/shared/llm_utils
"""
import wmill
from f.shared.llm_utils import create_llm_client, generate_completion


def split_string_by_delimiters(s: str, max_size: int = 3000) -> list[str]:
    """
    Разбивает строку на части по max_size символов.

    @param s Исходная строка
    @param max_size Максимальный размер части
    @return Список частей
    """
    delimiters = ["", "\n", ".", " "]
    result = []
    current_index = 0
    str_length = len(s)

    while current_index < str_length:
        end_index = min(current_index + max_size, str_length)
        found = False
        split_index = current_index

        substring = s[current_index:end_index]

        for delim in delimiters:
            if delim == "":
                if end_index == str_length:
                    split_index = end_index
                    found = True
                    break
            else:
                delim_index = substring.rfind(delim)
                if delim_index != -1:
                    split_index = current_index + delim_index + len(delim)
                    found = True
                    break

        if not found:
            split_index = end_index

        result.append(s[current_index:split_index])
        current_index = split_index

    return result


def main(
    input: str,
    model: str = "google/gemini-2.0-flash-001"
) -> dict:
    """
    Форматирует переданный текст.

    @param input Текст для форматирования
    @param model Модель для использования
    @return Словарь с полем output - отформатированный текст
    """
    resource = wmill.get_resource("u/theatmacreator/finer_c_openrouter")
    client = create_llm_client(resource)

    # Разбиваем текст на части
    parts = split_string_by_delimiters(input, 3000)

    # Форматируем каждую часть
    formatted_parts = []
    for part in parts:
        prompt = f"""## Task
You are an expert in text formatting. Format the text below.

## Rules
- Remove typos and hyphens.
- Add formatting and paragraphing selected based on the meaning of the text. Leave blank lines between paragraphs.
- The result should consist of sentences.
- ONLY if there are headings in the text change them to markdown format.
- Leave the text content exactly as it was given.
- My career depends on it.

End of instructions.

## Text for formatting
{part}
"""

        result = generate_completion(
            client=client,
            prompt=prompt,
            model=model,
            temperature=0.1,
            max_tokens=None,
        )
        formatted_parts.append(result)

    # Объединяем результаты
    output = " ".join(formatted_parts)

    return {"output": output}
