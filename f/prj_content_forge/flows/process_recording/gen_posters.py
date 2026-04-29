"""
GEN_POSTERS - генерация 2 постеров через FAL

ЧТО ДЕЛАЕТ:
- Парсит идеи для картинок (каждая на новой строке)
- Берёт первые 2 идеи (или дублирует последнюю, если меньше)
- Комбинирует каждую идею с жанровым промптом
- Генерирует 2 постера через FAL (9:16, модель из жанра или дефолт)

ГДЕ ИСПОЛЬЗУЕТСЯ:
- f/prj_content_forge/flows/process_recording (forloopflow)

ИСПОЛЬЗУЕТ:
- Script: f/transformations/fal_image_generator/generate_image
- External: FAL.ai API
"""
import wmill

DEFAULT_GENRE_PROMPT = "A clean, modern illustration with a minimalist style. Soft colors, simple shapes, professional design suitable for social media content."
DEFAULT_IMAGE_MODEL = "fal-ai/qwen-image-2512"
DEFAULT_ASPECT_RATIO = "9:16"


def main(ideas, genre_prompt, image_model=None, aspect_ratio=None, **kwargs):
    """
    Генерирует 2 постера на основе идей и жанрового стиля.

    @param ideas Многострочный текст с идеями для картинок
    @param genre_prompt Промпт жанра из Baserow
    @param image_model Модель для генерации (из Genres -> "Модель для картинки")
    @param aspect_ratio Соотношение сторон (из Genres -> "Соотношение сторон для картинки")
    @return Список URL постеров и идеи для Baserow
    """
    # Fallback на дефолтный промпт жанра
    genre_prompt = genre_prompt or DEFAULT_GENRE_PROMPT
    image_model = (image_model or "").strip() or DEFAULT_IMAGE_MODEL
    aspect_ratio = (aspect_ratio or "").strip() or DEFAULT_ASPECT_RATIO

    # Парсим идеи (каждая на отдельной строке)
    ideas_lines = [line.strip() for line in ideas.split("\n") if line.strip()]

    # Берём первые 2 идеи, если их меньше - дублируем последнюю
    poster_ideas = ideas_lines[:2] if len(ideas_lines) >= 2 else ideas_lines
    while len(poster_ideas) < 2:
        poster_ideas.append(poster_ideas[-1] if poster_ideas else DEFAULT_GENRE_PROMPT)

    poster_urls = []
    for idea in poster_ideas:
        # Комбинируем идею контента + жанровый стиль
        combined_prompt = f"{idea}. Style: {genre_prompt}"

        posters_result = wmill.run_script_by_path(
            "f/transformations/fal_image_generator/generate_image",
            {
                "prompt": combined_prompt,
                "model": image_model,
                "num_images": 1,
                "aspect_ratio": aspect_ratio
            }
        )
        poster_urls.append(posters_result["images"][0]["url"])

    # Формируем строку с идеями (объединяем переносом строк)
    ideas_for_baserow = "\n".join(poster_ideas)

    return {
        "poster_urls": poster_urls,
        "ideas_for_baserow": ideas_for_baserow
    }
