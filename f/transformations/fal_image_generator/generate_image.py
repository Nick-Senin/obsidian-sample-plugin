"""
GENERATE_IMAGE - генерация изображений через fal.ai

ЧТО ДЕЛАЕТ:
- Генерирует изображения по текстовому промпту через fal.ai API
- Поддерживает различные модели: fast-sdxl, flux-schnell, flux-pro
- Форматы разрешений: preset ("square_hd", "portrait_4_3") или custom ("1024x1024")
- Соотношения сторон: 1:1, 16:9, 4:3, 9:16
- Возвращает URL готовых изображений

ГДЕ ИСПОЛЬЗУЕТСЯ:
- Потенциально в любых проектах, требующих генерацию изображений

ИСПОЛЬЗУЕТ:
- Resource: u/theatmacreator/fal
- Shared: f/shared/fal_utils (parse_resolution)
- External: fal.ai API (https://fal.ai)
"""
import os
import fal_client
import httpx
import wmill
from f.shared.fal_utils import FalResource, normalize_fal_model_id, parse_resolution


def _get_resource_compat(path: str) -> dict:
    """
    Windmill python SDK versions and backend versions can drift.
    If `wmill.get_resource()` fails due to a missing endpoint, fall back to calling
    the resource API directly (resources/get_value/<path>).
    """
    try:
        return wmill.get_resource(path)
    except Exception:
        token = (os.environ.get("WM_TOKEN") or "").strip()
        workspace = (os.environ.get("WM_WORKSPACE") or "").strip()
        base_url = (os.environ.get("BASE_INTERNAL_URL") or os.environ.get("BASE_URL") or "").strip()
        if not token or not workspace or not base_url:
            raise

        url = f"{base_url.rstrip('/')}/api/w/{workspace}/resources/get_value/{path.lstrip('/')}"
        resp = httpx.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=30.0)
        resp.raise_for_status()
        return resp.json()


def main(
    prompt: str,
    model: str = "fal-ai/fast-sdxl",
    num_images: int = 1,
    resolution: str | None = None,
    aspect_ratio: str | None = None,
) -> dict:
    """
    Генерирует изображения через fal.ai.

    @param prompt Промпт для генерации изображения
    @param model ID модели fal.ai (по умолчанию: fal-ai/fast-sdxl)
    @param num_images Количество изображений (по умолчанию: 1)
    @param resolution Разрешение: "square_hd" или "1024x1024"
    @param aspect_ratio Соотношение сторон: "1:1", "16:9", "4:3", "9:16"
    @return Словарь с URL изображений и метаданными
    """
    fal_resource: FalResource = _get_resource_compat("u/theatmacreator/fal")
    os.environ["FAL_KEY"] = fal_resource["apiKey"]

    model_norm = normalize_fal_model_id(model)

    # Формирование аргументов для модели
    args = {"prompt": prompt, "num_images": num_images}
    args.update(parse_resolution(resolution, model_norm, aspect_ratio))

    # Вызов модели fal.ai
    response = fal_client.run(model_norm, arguments=args)

    return {
        "images": response["images"],
        "model": model_norm,
        "num_images": num_images,
    }
