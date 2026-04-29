"""
SPLIT_POSTS - разбиение длинного текста на отдельные посты

ЧТО ДЕЛАЕТ:
- Принимает "сырую" транскрипцию или длинный текст
- Разделяет на смысловые блоки (посты) с помощью LLM
- Использует разделитель @@@@@ между постами
- Определяет границы постов по контексту ("следующий пост про...")

ГДЕ ИСПОЛЬЗУЕТСЯ:
- f/prj_content_forge/flows/create_posts_from_transcript__flow

ИСПОЛЬЗУЕТ:
- Resource: u/theatmacreator/finer_c_openrouter
- Shared: f/shared/llm_utils
"""
import wmill
from f.shared.llm_utils import create_llm_client, generate_completion, get_resource_compat


def main(input: str, model: str = "openai/gpt-oss-120b:nitro") -> dict:
    """
    Разделяет и форматирует текст на отдельные посты.

    @param input Исходный текст для обработки
    @param model Модель для использования (по умолчанию gpt-oss-120b:nitro)
    @return Словарь с разделёнными постами
    """
    openrouter = get_resource_compat("u/theatmacreator/finer_c_openrouter")
    client = create_llm_client(openrouter)

    prompt = f"""# Задача
В преведенном тексте содержится один или несколько больших постов. Твоя задача разделить и отформатировать приведенный текст на отдельные посты.

# Правила
- Отделяй блоки символом @@@@@
- Не добавляй никаких комментариев и пояснений.
- Для определения нового поста в исходном тексте ВСЕГДА добавляются указания на то что это следующий пост. Например : "ок, следующий пост про ...", "третий пост про ..."

# Текст
{input}"""

    output = generate_completion(
        client=client,
        prompt=prompt,
        model=model,
        temperature=0.1,
        max_tokens=36000,
    )

    return {"output": output}
