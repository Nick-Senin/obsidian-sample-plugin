"""
GEPA_OPTIMIZER - Оптимизация промптов для style transfer используя DSPy GEPA

ЧТО ДЕЛАЕТ:
- Загружает обучающий датасет из ресурса
- Запускает GEPA оптимизацию для улучшения промптов
- Сохраняет оптимизированные инструкции обратно в ресурс

ГДЕ ИСПОЛЬЗУЕТСЯ:
- f/transformations/style_transfer/gepa_optimizer/optimize.py
- Запускается вручную для переоптимизации промптов

ИСПОЛЬЗУЕТ:
- Resource: u/theatmacreator/finer_c_openrouter
- Resource: u/theatmacreator/style_transfer_training_data
- External: dspy-ai==2.5.32
"""
import json
import random
from typing import List

import dspy
from dspy import GEPA, Predict, Signature

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


# Базовые инструкции для оптимизации
BASE_INSTRUCTIONS = """Ты — эксперт по переписыванию текстов в разных стилях. Твоя задача — преобразовать исходный текст в соответствии с указанным стилем."""


# DSPy Signature для стилевого переноса
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
    """Базовый DSPy-модуль для переноса стиля текста."""

    def __init__(
        self,
        instructions: str = BASE_INSTRUCTIONS,
        max_tokens: int = 4000,
        temperature: float = 0.7,
    ) -> None:
        super().__init__()
        self.predictor = Predict(
            StyleTransferSignature,
            instructions=instructions,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def forward(self, input_text: str, style_description: str):
        result = self.predictor(
            input_text=input_text,
            style_description=style_description,
        )
        return result


def load_training_data(data_json: str) -> List[dspy.Example]:
    """Загружает обучающие данные из JSON."""
    data = json.loads(data_json)
    examples = []

    for item in data:
        if not isinstance(item, dict):
            continue

        input_text = item.get("input_text")
        output_text = item.get("output_text")
        style_description = item.get("style_description", "")

        if not input_text or not output_text:
            continue

        examples.append(
            dspy.Example(
                input_text=input_text,
                style_description=style_description,
                output_text=output_text,
            ).with_inputs("input_text", "style_description")
        )

    return examples


def style_metric(gold, pred, trace=None) -> float:
    """Метрика для оценки качества стилевого переноса.

    Сравнивает сгенерированный текст с референсным.
    """
    generated = getattr(pred, "output_text", None)
    reference = getattr(gold, "output_text", "")

    if not generated:
        return 0.0

    # Простая метрика: оценка по длине и наличию ключевых слов
    if not reference:
        return 0.5  # Средняя оценка если нет референса

    # Проверка на минимальную длину
    min_len_ratio = len(generated) / max(len(reference), 1)
    if min_len_ratio < 0.3:
        return 0.1
    elif min_len_ratio > 3.0:
        return 0.3

    # Проверка на пустой результат
    if len(generated.strip()) < 20:
        return 0.1

    # Базовая оценка за непустой результат
    score = 0.7

    # Бонус за достаточную длину
    if len(generated) > 200:
        score += 0.2

    # Бонус за соответствие стилю (наличие переходов)
    transitions = ["однако", "следовательно", "поэтому", "таким образом", "например"]
    if any(t in generated.lower() for t in transitions):
        score += 0.1

    return min(1.0, score)


def split_train_val(
    examples: List[dspy.Example],
    val_ratio: float = 0.2,
    seed: int = 42,
):
    """Разделяет данные на train и val."""
    rnd = random.Random(seed)
    shuffled = list(examples)
    rnd.shuffle(shuffled)

    val_size = max(1, int(len(shuffled) * val_ratio))
    valset = shuffled[:val_size]
    trainset = shuffled[val_size:]

    return trainset, valset


def main(
    training_data: str,
    model: str = "openrouter/moonshotai/kimi-k2-0905:nitro",
    reflection_model: str = "openrouter/deepseek/deepseek-v3.2:nitro",
    max_full_evals: int = 5,
    temperature: float = 0.7,
) -> dict:
    """
    Запускает GEPA оптимизацию для style transfer модуля.

    @param training_data JSON с обучающими примерами [{"input_text": "...", "output_text": "...", "style_description": "..."}]
    @param model Модель для генерации
    @param reflection_model Модель для рефлексии
    @param max_full_evals Количество полных оценок (бюджет оптимизации)
    @param temperature Температура генерации
    @return Оптимизированные инструкции и статистика
    """
    # Получаем OpenRouter ресурс
    resource = wmill.get_resource("u/theatmacreator/finer_c_openrouter")

    # Создаём LM для генерации и рефлексии
    lm = build_lm(
        api_key=resource["apiKey"],
        model=model,
        temperature=temperature,
    )

    reflection_lm = build_lm(
        api_key=resource["apiKey"],
        model=reflection_model,
        temperature=0.3,
        max_tokens=8000,
    )

    # Настраиваем DSPy
    dspy.configure(lm=lm)

    # Загружаем обучающие данные
    examples = load_training_data(training_data)
    if len(examples) < 2:
        raise ValueError(f"Недостаточно обучающих примеров: {len(examples)} (минимум 2)")

    # Разделяем на train/val
    trainset, valset = split_train_val(examples)

    # Создаём базовый модуль
    student = StyleTransferModule(
        instructions=BASE_INSTRUCTIONS,
        temperature=temperature,
    )

    # Создаём GEPA оптимизатор
    optimizer = GEPA(
        metric=style_metric,
        max_full_evals=max_full_evals,
        reflection_lm=reflection_lm,
        track_stats=True,
    )

    # Запускаем оптимизацию
    optimized = optimizer.compile(
        student=student,
        trainset=trainset,
        valset=valset,
    )

    # Извлекаем оптимизированные инструкции
    optimized_instructions = getattr(
        getattr(optimized, "predictor", None),
        "instructions",
        BASE_INSTRUCTIONS
    )

    # Статистика оптимизации
    stats = {
        "train_examples": len(trainset),
        "val_examples": len(valset),
        "optimized": True,
    }

    if hasattr(optimized, "detailed_results"):
        detailed = optimized.detailed_results
        if hasattr(detailed, "val_aggregate_scores"):
            stats["best_score"] = max(detailed.val_aggregate_scores) if detailed.val_aggregate_scores else 0

    return {
        "instructions": optimized_instructions,
        "stats": stats,
    }
