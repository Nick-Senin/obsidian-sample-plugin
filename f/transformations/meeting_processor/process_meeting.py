"""
MEETING_PROCESSOR - Обработка сырого транскрипта митинга в структурированный отчёт

ЧТО ДЕЛАЕТ:
- Принимает сырой транскрипт встречи с метаданными
- Детерминированно режет длинные транскрипты на чанки
- Обрабатывает чанки через LLM и иерархически собирает отчёт
- Выделяет решения, действия, вопросы, риски с тегами
- Возвращает структурированный Markdown-отчёт

ГДЕ ИСПОЛЬЗУЕТСЯ:
- Любые проекты требующие протоколирования встреч
- Может использоваться самостоятельно или во flows

ИСПОЛЬЗУЕТ:
- Resource: u/theatmacreator/finer_c_openrouter
- Shared: f/shared/llm_utils
"""

from __future__ import annotations

from f.shared.llm_utils import create_llm_client, generate_completion, get_resource_compat


DEFAULT_MODEL = "x-ai/grok-4-fast"
TRANSCRIPT_CHUNK_TARGET_CHARS = 24_000
NOTES_CHUNK_TARGET_CHARS = 32_000
CHUNK_SUMMARY_MAX_TOKENS = 1_200
FINAL_REPORT_MAX_TOKENS = 10_000

REPORT_TEMPLATE = """# Карточка встречи
- Тип встречи: <...>
- Дата/время: <...>
- Длительность: <...>
- Формат: <онлайн/офлайн>
- Участники и роли:
  - <Имя> — <роль>
  - ...
- Контекст (1–3 строки): <...>
- Цель встречи: <...>
- Ожидаемый результат: <...>

# Повестка (как прозвучало)
1) ...
2) ...
3) ...

# Лог разговора (по ходу встречи)
> Формат: [таймкод] Спикер — суть. Теги: #...
- [..:..] <Спикер>: <краткая фиксация> #...
  - Цитата (если важно): "..."
  - Аргументы/детали: ...
- ...

# Итоги
## Решения (#решение)
- R1: <что решили> — контекст/почему — кто подтвердил

## Действия (#действие)
| Действие | Владелец | Дедлайн | Критерий готовности | Комментарий |
|---|---|---|---|---|
| ... | ... | ... | ... | ... |

## Открытые вопросы (#вопрос)
- Q1: ...
- Q2: ...

## Риски/блокеры (#риск)
- ...

## Парковка (важно, но не закрыли)
- ...

# Следующий шаг / следующая встреча
- Когда/условие: ...
- Цель: ...

# Приложения и ссылки
- ..."""

CHUNK_EXTRACTION_INSTRUCTIONS = """РОЛЬ:
Ты — ассистент по протоколированию встреч. Ниже дан фрагмент сырого транскрипта.
Нужно сделать компактные служебные заметки для последующей сборки общего отчёта.

ОБЯЗАТЕЛЬНЫЕ ПРАВИЛА:
1) Не выдумывай факты. Если данных нет, ничего не дописывай.
2) Сохраняй смысл и формулировки, важные фразы оставляй короткими цитатами.
3) Если в фрагменте нет данных по разделу, просто пропусти раздел.
4) Пиши кратко и по делу. Это не финальный отчёт, а сжатые заметки.
5) Выделяй теги: #решение, #действие, #вопрос, #риск, #идея, #согласовано, #не_согласовано.
6) Если есть таймкоды или спикеры, сохраняй их.

ФОРМАТ СЛУЖЕБНЫХ ЗАМЕТОК:
## Участники
- ...

## Повестка
- ...

## Ход обсуждения
- [таймкод] Спикер — суть #теги

## Решения
- ...

## Действия
- Действие | Владелец | Дедлайн | Критерий готовности | Комментарий

## Вопросы
- ...

## Риски
- ...

## Парковка и идеи
- ...

## Ссылки и артефакты
- ...
"""

FINAL_REPORT_INSTRUCTIONS = f"""РОЛЬ:
Ты — ассистент по протоколированию встреч. На входе: сжатые служебные заметки по всей встрече.
На выходе: итоговый структурированный отчёт по шаблону.

ОБЯЗАТЕЛЬНЫЕ ПРАВИЛА:
1) Не выдумывай факты и не "додумывай". Если данных нет — ставь "—" или "не прозвучало".
2) Сохраняй смысл и формулировки. Важные фразы — как короткие цитаты.
3) Нормализуй участников: приведи имена/роли к единому виду, если это следует из текста.
4) Выделяй: #решение, #действие, #вопрос, #риск, #идея, #согласовано, #не_согласовано.
5) Если в исходных заметках есть таймкоды — сохраняй. Если нет — не придумывай.
6) Пиши на русском. Стиль — деловой, лаконичный.
7) Убирай дубли между чанками, но не теряй значимые факты.

ФОРМАТ ВЫВОДА:
Используй Markdown строго по структуре ниже.

{REPORT_TEMPLATE}
"""


def _split_long_block(text: str, limit: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= limit:
        return [text]

    parts: list[str] = []
    remaining = text
    while len(remaining) > limit:
        window = remaining[:limit]
        cut = max(
            window.rfind("\n"),
            window.rfind(". "),
            window.rfind("! "),
            window.rfind("? "),
            window.rfind("; "),
            window.rfind(", "),
            window.rfind(" "),
        )
        if cut < limit // 2:
            cut = limit
        piece = remaining[:cut].strip()
        if piece:
            parts.append(piece)
        remaining = remaining[cut:].strip()
    if remaining:
        parts.append(remaining)
    return parts


def _split_into_blocks(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []

    blocks = [block.strip() for block in normalized.split("\n\n") if block.strip()]
    if len(blocks) == 1:
        blocks = [line.strip() for line in normalized.splitlines() if line.strip()]
    if not blocks:
        return [normalized]
    return blocks


def _chunk_blocks(blocks: list[str], target_chars: int) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for block in blocks:
        sub_blocks = _split_long_block(block, target_chars)
        for sub_block in sub_blocks:
            separator_len = 2 if current else 0
            candidate_len = current_len + separator_len + len(sub_block)
            if current and candidate_len > target_chars:
                chunks.append("\n\n".join(current))
                current = [sub_block]
                current_len = len(sub_block)
            else:
                current.append(sub_block)
                current_len = candidate_len

    if current:
        chunks.append("\n\n".join(current))

    return chunks


def _chunk_transcript(raw_transcript: str, target_chars: int | None = None) -> list[str]:
    return _chunk_blocks(
        _split_into_blocks(raw_transcript),
        target_chars or TRANSCRIPT_CHUNK_TARGET_CHARS,
    )


def _chunk_notes(notes: list[str], target_chars: int | None = None) -> list[list[str]]:
    target_chars = target_chars or NOTES_CHUNK_TARGET_CHARS
    groups: list[list[str]] = []
    current: list[str] = []
    current_len = 0

    for note in notes:
        note = note.strip()
        if not note:
            continue
        separator_len = 2 if current else 0
        candidate_len = current_len + separator_len + len(note)
        if current and candidate_len > target_chars:
            groups.append(current)
            current = [note]
            current_len = len(note)
        else:
            current.append(note)
            current_len = candidate_len

    if current:
        groups.append(current)

    return groups


def _build_chunk_prompt(
    meeting_type: str,
    context: str,
    chunk_text: str,
    chunk_index: int,
    total_chunks: int,
) -> str:
    return f"""{CHUNK_EXTRACTION_INSTRUCTIONS}

ТИП ВСТРЕЧИ: {meeting_type}
КОНТЕКСТ: {context if context else "не указан"}
ФРАГМЕНТ: {chunk_index}/{total_chunks}

СЫРОЙ ТРАНСКРИПТ ФРАГМЕНТА:
<<<
{chunk_text}
>>>

СДЕЛАЙ КОМПАКТНЫЕ СЛУЖЕБНЫЕ ЗАМЕТКИ ТОЛЬКО ПО ЭТОМУ ФРАГМЕНТУ."""


def _build_merge_prompt(
    meeting_type: str,
    context: str,
    notes_group: list[str],
    group_index: int,
    total_groups: int,
    level: int,
) -> str:
    notes_blob = "\n\n---\n\n".join(notes_group)
    return f"""{CHUNK_EXTRACTION_INSTRUCTIONS}

ТИП ВСТРЕЧИ: {meeting_type}
КОНТЕКСТ: {context if context else "не указан"}
ЭТАП СЖАТИЯ: уровень {level}, группа {group_index}/{total_groups}

НИЖЕ НЕ СЫРОЙ ТРАНСКРИПТ, А УЖЕ СЛУЖЕБНЫЕ ЗАМЕТКИ ИЗ НЕСКОЛЬКИХ ЧАНКОВ.
ТВОЯ ЗАДАЧА:
- дедуплицировать повторы;
- сохранить факты, участников, решения, действия, вопросы, риски;
- не добавлять ничего нового;
- вернуть ЕЩЁ БОЛЕЕ КОМПАКТНЫЕ служебные заметки в том же формате.

СЛУЖЕБНЫЕ ЗАМЕТКИ:
<<<
{notes_blob}
>>>
"""


def _build_final_prompt(meeting_type: str, context: str, notes: str) -> str:
    return f"""{FINAL_REPORT_INSTRUCTIONS}

# Входные данные
Тип встречи: {meeting_type}
Контекст: {context if context else "не указан"}

Служебные заметки по всей встрече:
<<<
{notes}
>>>

СОБЕРИ ИТОГОВЫЙ СТРУКТУРИРОВАННЫЙ ОТЧЁТ. Выведи только готовый Markdown-отчёт."""


def _reduce_notes(
    client,
    meeting_type: str,
    context: str,
    model: str,
    notes: list[str],
) -> list[str]:
    level = 1
    current_notes = [note.strip() for note in notes if note and note.strip()]

    while len(current_notes) > 1:
        grouped = _chunk_notes(current_notes)
        if len(grouped) == 1:
            break

        merged_notes: list[str] = []
        total_groups = len(grouped)
        for group_index, group in enumerate(grouped, start=1):
            merged_notes.append(
                generate_completion(
                    client=client,
                    prompt=_build_merge_prompt(
                        meeting_type=meeting_type,
                        context=context,
                        notes_group=group,
                        group_index=group_index,
                        total_groups=total_groups,
                        level=level,
                    ),
                    model=model,
                    temperature=0.0,
                    max_tokens=CHUNK_SUMMARY_MAX_TOKENS,
                )
            )

        current_notes = merged_notes
        level += 1

    return current_notes


def main(
    meeting_type: str,
    raw_transcript: str,
    context: str = "",
    model: str = "x-ai/grok-4-fast",
) -> dict:
    """
    Обрабатывает сырой транскрипт митинга в структурированный отчёт.

    @param meeting_type Тип встречи (номер и название)
    @param raw_transcript Сырой транскрипт встречи
    @param context Дополнительный контекст (опционально)
    @param model Модель для обработки
    @return Словарь с полями report (markdown) и metadata (инфо о обработке)
    """
    transcript = (raw_transcript or "").strip()
    if not transcript:
        raise ValueError("raw_transcript is required")

    resource = get_resource_compat("u/theatmacreator/finer_c_openrouter")
    client = create_llm_client(resource)

    transcript_chunks = _chunk_transcript(transcript)
    total_chunks = len(transcript_chunks)

    chunk_notes: list[str] = []
    for chunk_index, chunk_text in enumerate(transcript_chunks, start=1):
        chunk_notes.append(
            generate_completion(
                client=client,
                prompt=_build_chunk_prompt(
                    meeting_type=meeting_type,
                    context=context,
                    chunk_text=chunk_text,
                    chunk_index=chunk_index,
                    total_chunks=total_chunks,
                ),
                model=model,
                temperature=0.0,
                max_tokens=CHUNK_SUMMARY_MAX_TOKENS,
            )
        )

    reduced_notes = _reduce_notes(
        client=client,
        meeting_type=meeting_type,
        context=context,
        model=model,
        notes=chunk_notes,
    )

    final_notes = reduced_notes[0] if reduced_notes else ""
    result = generate_completion(
        client=client,
        prompt=_build_final_prompt(
            meeting_type=meeting_type,
            context=context,
            notes=final_notes,
        ),
        model=model,
        temperature=0.1,
        max_tokens=FINAL_REPORT_MAX_TOKENS,
    )

    return {
        "report": result,
        "metadata": {
            "meeting_type": meeting_type,
            "model_used": model,
            "has_context": bool(context),
            "transcript_chunk_count": total_chunks,
            "transcript_chunk_sizes": [len(chunk) for chunk in transcript_chunks],
            "notes_reduction_rounds": max(0, len(chunk_notes) - len(reduced_notes)),
        },
    }
