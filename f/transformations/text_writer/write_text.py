"""
TEXT_WRITER - генерация текста по промпту и тезисам

ЧТО ДЕЛАЕТ:
- Генерирует текст на основе шаблона промпта и списка тезисов
- Тезисы вставляются в промпт последовательно

ГДЕ ИСПОЛЬЗУЕТСЯ:
- Любые флоу где нужна генерация текста по структуре

ИСПОЛЬЗУЕТ:
- Resource: u/theatmacreator/finer_c_openrouter
- Shared: f/shared/llm_utils
"""
import wmill
from f.shared.llm_utils import create_llm_client, generate_completion


def main(
    prompt_template: str,
    theses: list[str],
    model: str = "google/gemini-2.0-flash-exp:free",
    temperature: float = 0.7,
    max_tokens: int = 2000,
) -> dict:
    """
    Генерирует текст по заданному промпту и тезисам.

    @param prompt_template Шаблон промпта (используй {theses} для подстановки)
    @param theses Список тезисов для вставки в промпт
    @param model Модель для генерации
    @param temperature Температура генерации
    @param max_tokens Максимальное количество токенов
    @return Словарь с ключом 'text' — сгенерированный текст
    """
    resource = wmill.get_resource("u/theatmacreator/finer_c_openrouter")
    client = create_llm_client(resource)

    # Формируем полный промпт с тезисами
    theses_text = "\n".join(f"- {t}" for t in theses)
    full_prompt = prompt_template.replace("{theses}", theses_text)

    result = generate_completion(
        client=client,
        prompt=full_prompt,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    return {"text": result}
