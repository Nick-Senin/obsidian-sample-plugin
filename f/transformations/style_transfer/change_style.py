"""
CHANGE_STYLE - Переписывает текст в заданном стиле (GEPA-оптимизированная версия)

ЧТО ДЕЛАЕТ:
- Принимает исходный текст и описание стиля
- Переписывает текст в соответствии с указанным стилем
- Использует GEPA-оптимизированные промпты для максимального качества

ГДЕ ИСПОЛЬЗУЕТСЯ:
- f/prj_content_forge/flows/...
- Любые проекты где нужен style transfer

ИСПОЛЬЗУЕТ:
- Resource: u/theatmacreator/finer_c_openrouter
- External: dspy-ai==2.5.32
"""
import re
from typing import List

import dspy
from dspy import Predict, Signature

import wmill


# Подготовка OpenRouter LM для DSPy 2.x
def build_lm(
    api_key: str,
    model: str = "openrouter/moonshotai/kimi-k2-0905:nitro",
    api_base: str = "https://openrouter.ai/api/v1",
    temperature: float = 0.7,
    max_tokens: int = 4000,
) -> dspy.LM:
    """Создаёт dspy.LM для OpenRouter (DSPy 2.x совместимость)."""
    return dspy.LM(
        model=model,
        api_key=api_key,
        api_base=api_base,
        temperature=temperature,
        max_tokens=max_tokens,
    )


# GEPA-оптимизированные инструкции для стилизации текста
GEPA_OPTIMIZED_INSTRUCTIONS = """Ты — эксперт по созданию научно-популярных текстов. Твоя задача — преобразовать предоставленный текст в связный, плавный и увлекательный текст, соответствующий указанному стилю.

**Критически важные требования к выполнению задачи:**

1. **Полнота и развитие:** Текст должен быть **полным и законченным**. Необходимо раскрыть все ключевые идеи из исходного текста, развивая их в связное повествование.

2. **Структура и логика:** Выстрой текст в логичную историю или объяснение. Возможные стратегии:
   - **"Вопрос — гипотезы — вывод — перспективы"**
   - **"Опровержение мифа — новые данные — последствия"**
   - **Хронологический порядок** для исторических тем

3. **Плавные переходы:** Избегай резких скачков между предложениями и абзацами. Используй:
   - Логические связки: «однако», «следовательно», «вместо этого», «иными словами»
   - Повтор ключевых слов из конца предыдущего абзаца в начале следующего
   - Риторические вопросы для ведения читателя

4. **Стиль и тон:**
   - **Образный язык:** Используй метафоры и сравнения
   - **Обращение к читателю:** "представьте себе", "оказывается"
   - **Ясность:** Объясняй сложные термины или заменяй их бытовыми аналогиями
   - **Неформальность:** Допустимы разговорные обороты для создания доверительного рассказа

5. **Форматирование:**
   - **Не используй маркированные или нумерованные списки**
   - **Отделяй смысловые блоки пустой строкой**

6. **Сохранение смысла:** Сохраняй все ключевые идеи и факты из оригинального текста, но излагай их в новом стиле."""


# DSPy Signature для стилевого переноса с GEPA-инструкциями
class StyleTransferSignature(dspy.Signature):
    """Переписать текст в указанном стиле."""

    input_text: str = dspy.InputField(
        desc="Исходный текст для изменения стиля"
    )
    style_description: str = dspy.InputField(
        desc="Описание желаемого стиля и тона"
    )
    reasoning: str = dspy.OutputField(
        desc="Краткий план построения текста (2-4 предложения)"
    )
    output_text: str = dspy.OutputField(
        desc="Переписанный текст в заданном стиле"
    )


class StyleTransferModule(dspy.Module):
    """DSPy-модуль для переноса стиля текста с GEPA-оптимизированными инструкциями."""

    def __init__(
        self,
        max_tokens: int = 4000,
        temperature: float = 0.7,
    ) -> None:
        super().__init__()
        self.predictor = Predict(
            StyleTransferSignature,
            instructions=GEPA_OPTIMIZED_INSTRUCTIONS,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def forward(self, input_text: str, style_description: str):
        cleaned_input = input_text.strip()
        if not cleaned_input:
            raise ValueError("Входной текст пуст")

        cleaned_style = style_description.strip()
        if not cleaned_style:
            raise ValueError("Описание стиля пусто")

        result = self.predictor(
            input_text=cleaned_input,
            style_description=cleaned_style,
        )

        # Извлекаем результат из prediction
        output = getattr(result, "output_text", None)
        if output is None:
            # Фолбэк если поле не найдено
            return dspy.Prediction(output_text=str(result))
        return result


def main(
    input_text: str,
    style_description: str = "Научно-популярный, вовлекающий, ясный. Собери в цельный текст, добавь плавные переходы. Не используй списки. Отделяй смысловые части текста пустой строкой.",
    model: str = "openrouter/moonshotai/kimi-k2-0905:nitro",
    temperature: float = 0.7,
) -> dict:
    """
    Переписывает текст в заданном стиле используя DSPy с GEPA-оптимизированными инструкциями.

    @param input_text Исходный текст для преобразования
    @param style_description Описание желаемого стиля
    @param model Модель LLM для использования
    @param temperature Температура генерации (0.0-1.0)
    @return Словарь с полями output и reasoning - преобразованный текст и план
    """
    # Получаем OpenRouter ресурс
    resource = wmill.get_resource("u/theatmacreator/finer_c_openrouter")

    # Создаём и настраиваем LM
    lm = build_lm(
        api_key=resource["apiKey"],
        model=model,
        temperature=temperature,
    )
    dspy.configure(lm=lm)

    # Создаём модуль и генерируем результат
    module = StyleTransferModule(temperature=temperature)
    prediction = module(input_text=input_text, style_description=style_description)

    # Извлекаем результат
    output = getattr(prediction, "output_text", None)
    reasoning = getattr(prediction, "reasoning", "")

    if not output:
        # Если output_text нет, пытаемся получить полный результат
        full_result = str(prediction)
        # Разделяем reasoning и output_text если возможно
        if "Reasoning:" in full_result and "Output:" in full_result:
            parts = full_result.split("Output:", 1)
            reasoning = parts[0].replace("Reasoning:", "").strip()
            output = parts[1].strip()
        else:
            output = full_result

    return {
        "output": output.strip(),
        "reasoning": reasoning.strip()
    }
