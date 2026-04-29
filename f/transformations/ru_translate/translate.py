"""
RU_TRANSLATE - Перевод текста на русский язык

ЧТО ДЕЛАЕТ:
- Переводит текст на русский язык
- Разбивает длинный текст на части по 2000 символов
- Объединяет результаты перевода

ГДЕ ИСПОЛЬЗУЕТСЯ:
- Используется для перевода контента на русский

ИСПОЛЬЗУЕТ:
- Resource: u/theatmacreator/finer_c_openrouter
- Shared: f/shared/llm_utils
"""
import wmill
from f.shared.llm_utils import create_llm_client, generate_completion


def split_string_by_delimiters(s: str, max_size: int = 2000) -> list[str]:
    """
    Разбивает строку на части по max_size символов.

    @param s Исходная строка
    @param max_size Максимальный размер части
    @return Список частей
    """
    delimiters = ["", ".", " "]
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
    model: str = "deepseek/deepseek-chat"
) -> dict:
    """
    Переводит текст на русский язык.

    @param input Текст для перевода
    @param model Модель для использования
    @return Словарь с полем output - переведённый текст
    """
    resource = wmill.get_resource("u/theatmacreator/finer_c_openrouter")
    client = create_llm_client(resource)

    # Разбиваем текст на части
    parts = split_string_by_delimiters(input, 2000)

    # Переводим каждую часть
    translated_parts = []
    for part in parts:
        prompt = f"""# Роль
Ты - лучший эксперт переводчик на русский язык.

# Задача
Переведи исходный текст на русский

# Правила
- В точности сохрани смысл и значение исходного текста.
- Учитывай общий контекст и переводи наиболее точно.
- От этого зависит моя карьера.
- Если в тексте есть markdown форматирование - оставь его в точности.

# Формат ответа
- ТОЛЬКО перевод исходного текста
- Не добавляй никаких пояснений, вводных слов.
- Не добавляй кавычки к результату.

Конец инструкций

# Исходный текст
{part}
"""

        result = generate_completion(
            client=client,
            prompt=prompt,
            model=model,
            temperature=0.3,
        )
        translated_parts.append(result)

    # Объединяем результаты
    output = " ".join(translated_parts)

    return {"output": output}
