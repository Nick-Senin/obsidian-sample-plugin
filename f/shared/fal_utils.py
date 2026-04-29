"""
Общие утилиты для работы с fal.ai в Windmill.
"""
from typing import TypedDict


class FalResource(TypedDict):
    """Типизированный словарь для ресурса fal.ai."""
    apiKey: str


def normalize_fal_model_id(model: str) -> str:
    """
    Accept either a model id (e.g. "fal-ai/fast-sdxl") or a model URL
    (e.g. "https://fal.ai/models/fal-ai/fast-sdxl") and return the model id.
    """
    model_norm = (model or "").strip()
    if not model_norm:
        return model_norm

    marker = "fal.ai/models/"
    if marker in model_norm:
        model_norm = model_norm.split(marker, 1)[1]

    model_norm = model_norm.split("?", 1)[0].split("#", 1)[0]
    model_norm = model_norm.lstrip("/")
    return model_norm


def parse_resolution(resolution: str | None, model: str, aspect_ratio: str | None = None) -> dict:
    """
    Преобразует строку разрешения и соотношение сторон в параметры модели.

    @param resolution Разрешение: "square_hd", "1024x1024", или None
    @param model ID модели (для определения формата)
    @param aspect_ratio Соотношение сторон: "1:1", "16:9", "4:3", "9:16", или None
    @return Словарь с параметрами size для модели
    """
    model_norm = normalize_fal_model_id(model)

    # Some fal.ai models (e.g. Gemini 3 Pro Image Preview / Nano Banana) use
    # `aspect_ratio` + `resolution` (1K/2K/4K) and do NOT accept `image_size`.
    if model_norm.startswith("fal-ai/nano-banana-pro") or model_norm.startswith("fal-ai/gemini-3-pro-image-preview"):
        args: dict = {}
        preset_to_aspect = {
            "square_hd": "1:1",
            "landscape_4_3": "4:3",
            "portrait_4_3": "3:4",
            "landscape_16_9": "16:9",
            "portrait_16_9": "9:16",
        }
        if resolution:
            if "x" in resolution:
                w, h = resolution.split("x")
                try:
                    width = int(w)
                    height = int(h)
                    if not aspect_ratio:
                        aspect_ratio = _closest_aspect_ratio(width, height)
                    args["resolution"] = _resolution_from_max_side(max(width, height))
                except ValueError:
                    pass
            elif resolution in {"1K", "2K", "4K"}:
                args["resolution"] = resolution
            else:
                preset_ratio = preset_to_aspect.get(resolution)
                if preset_ratio and not aspect_ratio:
                    aspect_ratio = preset_ratio
                    args["resolution"] = "1K"
        if aspect_ratio:
            args["aspect_ratio"] = aspect_ratio.strip()
        return args
    # Если задано явное разрешение с размерами ("1024x1024"), используем его
    if resolution and "x" in resolution:
        w, h = resolution.split("x")
        return {"width": int(w), "height": int(h)}

    # Если задано соотношение сторон, предпочитаем preset-ы image_size
    if aspect_ratio:
        aspect_ratio = aspect_ratio.strip()
        aspect_ratio_to_preset = {
            "1:1": "square_hd",
            "4:3": "landscape_4_3",
            "3:4": "portrait_4_3",
            "16:9": "landscape_16_9",
            "9:16": "portrait_16_9",
        }
        preset = aspect_ratio_to_preset.get(aspect_ratio)
        if preset:
            return {"image_size": preset}

        # Если формат соотношения сторон нестандартный, рассчитываем размеры
        base_size = 1024
        ratio_map = {
            "1:1": (1, 1),
            "16:9": (16, 9),
            "4:3": (4, 3),
            "9:16": (9, 16),
            "3:4": (3, 4),
        }
        if aspect_ratio in ratio_map:
            num, den = ratio_map[aspect_ratio]
            # Вычисляем размеры, сохраняя общее количество пикселей примерно равным
            total_pixels = base_size * base_size
            width = int((total_pixels * num / den) ** 0.5)
            height = int((total_pixels * den / num) ** 0.5)
            # Округляем до ближайшего числа, кратного 8 (требование некоторых моделей)
            width = (width // 8) * 8
            height = (height // 8) * 8
            return {"width": width, "height": height}

    # Если задан preset ("square_hd"), используем его
    if resolution:
        return {"image_size": resolution}

    return {}


def _closest_aspect_ratio(width: int, height: int) -> str:
    ratios = {
        "21:9": 21 / 9,
        "16:9": 16 / 9,
        "3:2": 3 / 2,
        "4:3": 4 / 3,
        "5:4": 5 / 4,
        "1:1": 1,
        "4:5": 4 / 5,
        "3:4": 3 / 4,
        "2:3": 2 / 3,
        "9:16": 9 / 16,
    }
    target = width / height if height else 1
    return min(ratios, key=lambda key: abs(ratios[key] - target))


def _resolution_from_max_side(max_side: int) -> str:
    if max_side <= 1024:
        return "1K"
    if max_side <= 2048:
        return "2K"
    return "4K"


# Main функция (не используется, нужна для зависимостей Windmill)
def main():
    """Этот скрипт используется как общий модуль, не запускайте напрямую."""
    pass
