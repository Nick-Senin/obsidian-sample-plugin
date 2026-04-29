"""
REPRO_CHECKLIST - Проверка воспроизводимости текста

ЧТО ДЕЛАЕТ:
- Определяет тип текста: solution или cause_effect
- Оценивает воспроизводимость по шкале 0-10
- Возвращает JSON с reasoning и score

ГДЕ ИСПОЛЬЗУЕТСЯ:
- Используется в deep_completion для проверки качества знаний

ИСПОЛЬЗУЕТ:
- Resource: u/theatmacreator/finer_c_openrouter
- Shared: f/shared/llm_utils
"""
import wmill
from f.shared.llm_utils import create_llm_client, generate_completion
import json


def detect_type(input: str, client) -> str:
    """Определяет тип текста: solution или cause_effect"""
    prompt = f"""# Task
Your task is to determine whether the passed text contains a solution to a problem or rather describes a cause-and-effect relationship.

In the first case, output the solution.
In the second case - cause_effect.

# Output
JSON с полем type и одним из двух значений : solution, cause_effect.

# Input
{input}
"""

    result = generate_completion(
        client=client,
        prompt=prompt,
        model="meta-llama/llama-3.3-70b-instruct",
        temperature=0.1,
    )

    try:
        parsed = json.loads(result)
        return parsed.get("type", "solution")
    except:
        return "solution"


def check_solution(input: str, client) -> dict:
    """Проверка воспроизводимости для solution"""
    prompt = f"""# Task
Your task is to determine the reproducibility rating of the problem-solution text.

# Rules
0 = Невоспроизводимо: Отсутствует какое-либо описание методов. Невозможно понять, что было сделано.

1 = Минимальная информация: Упоминаются некоторые элементы процесса, но без структуры. Дает только очень общее представление.

2 = Базовое описание: Представлен общий подход в самых общих чертах. Основные шаги упомянуты, но многие детали отсутствуют.

3 = Ограниченное описание: Описывает основные этапы процесса. Дает общее понимание направления работы, хотя важные детали опущены.

4 = Частичное описание: Включает описание основных этапов с некоторыми деталями. Эксперт в данной области мог бы частично воспроизвести работу.

5 = Достаточное описание: Методология описана с необходимым минимумом деталей для понимания принципов. Ключевые моменты обозначены.

6 = Хорошее описание: Содержит большую часть важной информации. Общий процесс понятен, хотя некоторые детали могут требовать уточнения.

7 = Надежное описание: Ясно представляет методологию с большинством необходимых деталей. Для воспроизведения требуются лишь незначительные уточнения.

8 = Подробное описание: Предоставляет детальную методологию с конкретными параметрами и измерениями. Большинство важных аспектов освещено.

9 = Отличное описание: Подробная методология с хорошо описанными протоколами и указаниями по преодолению типичных трудностей.

10 = Образцовое описание: Полная методология со всеми необходимыми деталями, позволяющая уверенно воспроизвести процесс даже без специальных знаний в данной области.

It is not necessary for the mechanism of the effect to be represented for the text to be reproducible.

# Output format
In the response return only JSON with these fields:
- reproducibility reasoning.
- reproducibility - number 0 to 10.

# Input
{input}
"""

    result = generate_completion(
        client=client,
        prompt=prompt,
        model="qwen/qwen-turbo",
        temperature=0.1,
    )

    try:
        return json.loads(result)
    except:
        return {
            "reproducibility reasoning": "Failed to parse",
            "reproducibility": 0
        }


def check_cause_effect(input: str, client) -> dict:
    """Проверка воспроизводимости для cause_effect"""
    prompt = f"""# Task
Your task is to determine the reproducibility rating of the cause-effect text.

# Rules
0 = Отсутствие связи: Причина и следствие не связаны или связь не обозначена совсем. Логическая цепочка полностью отсутствует.

1 = Намек на связь: Причина и следствие упоминаются, но их связь лишь подразумевается. Объяснение механизма связи отсутствует.

2 = Слабая связь: Утверждается наличие связи между явлениями, но объяснение поверхностное. Логические шаги пропущены или непоследовательны.

3 = Базовая логика: Представлена базовая логическая цепочка от причины к следствию. Видны общие контуры рассуждения, хотя обоснование неполное.

4 = Частичное объяснение: Описаны некоторые механизмы связи. Логика прослеживается, но имеет пробелы или неясности в ключевых моментах.

5 = Разумное объяснение: Представлено понятное объяснение связи причины и следствия. Основные промежуточные шаги обозначены, хотя и без детализации.

6 = Хорошее обоснование: Логическая цепочка достаточно ясна. Большинство промежуточных шагов описано, создавая последовательную картину.

7 = Четкое объяснение: Связь описана с ясной логикой и достаточными доказательствами. Процесс перехода от причины к следствию легко проследить.

8 = Подробное обоснование: Механизмы причинно-следственной связи раскрыты с необходимыми деталями. Включены важные факторы и условия.

9 = Убедительное объяснение: Представлена полная и хорошо аргументированная причинно-следственная цепочка. Освещены потенциальные альтернативные объяснения.

10 = Безупречная логика: Причинно-следственная связь объяснена исчерпывающе, с учетом всех необходимых условий, механизмов и доказательств. Любой человек может проследить и проверить логику рассуждения.

It is not necessary for the mechanism of the effect to be represented for the text to be reproducible.

# Output format
In the response return only JSON:
- reproducibility reasoning - на русском
- reproducibility - number 0 to 10.

# Input
{input}
"""

    result = generate_completion(
        client=client,
        prompt=prompt,
        model="qwen/qwen-turbo",
        temperature=0.1,
    )

    try:
        return json.loads(result)
    except:
        return {
            "reproducibility reasoning": "Failed to parse",
            "reproducibility": 0
        }


def main(
    input: str
) -> dict:
    """
    Проверяет воспроизводимость текста.

    @param input Текст для проверки
    @return Словарь с полями reproducibility reasoning и reproducibility (0-10)
    """
    resource = wmill.get_resource("u/theatmacreator/finer_c_openrouter")
    client = create_llm_client(resource)

    # Определяем тип текста
    text_type = detect_type(input, client)

    # Проверяем воспроизводимость в зависимости от типа
    if text_type == "cause_effect":
        result = check_cause_effect(input, client)
    else:
        result = check_solution(input, client)

    return result
