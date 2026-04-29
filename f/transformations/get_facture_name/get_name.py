"""
GET_FACTURE_NAME - Извлечение причинно-следственных связей

ЧТО ДЕЛАЕТ:
- Извлекает из текста причинно-следственные связи или связи задача-решение
- Формирует одно предложение (max 20 слов) в формате "Для решения X используется Y" или "Причина X ведет к Y"

ГДЕ ИСПОЛЬЗУЕТСЯ:
- Часть линтера для создания кратких описаний связей

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
    Извлекает причинно-следственные связи из текста.

    @param input Текст для анализа
    @param model Модель для использования
    @return Словарь с полем output - предложение со связью
    """
    resource = wmill.get_resource("u/theatmacreator/finer_c_openrouter")
    client = create_llm_client(resource)

    prompt = f"""## Задача
Извлеки из текста ниже причинно-следственные связи или связи задача-решение. Оставь только те связи которые можно повторить на основе переданного текста, а также которые небанальны.

Затем на основе этих связок сформируй предложение которое учитывает не более чем в 20 слов. Формат предложения должен быть следующим : "Для решения задачи X используется Y", или "Причина X ведет к Y" и их комбинации.

В ответе приведи только одно предложение содержащее все связи.

НЕ ДОБАВЛЯЙ точку в конце.

## Текст
{input}
"""

    result = generate_completion(
        client=client,
        prompt=prompt,
        model=model,
        temperature=0.7,
    )

    # Убираем точку в конце если есть
    output = result.rstrip(".")

    return {"output": output}
