"""
IMAGE_TEXT_OVERLAY - Добавление текста на изображение в 3 местах

ЧТО ДЕЛАЕТ:
- Накладывает 3 текстовых блока: сверху, снизу слева, снизу справа
- Для каждого блока задаются шрифт, размер, стиль, начертание, цвет и обводка
- Принимает изображение по URL или из Windmill store (S3Object)
- Работает без системного ImageMagick (использует Pillow)

ГДЕ ИСПОЛЬЗУЕТСЯ:
- Transformation
"""
from typing import TypedDict
import io
import os
import tempfile
import requests
import wmill
from PIL import Image, ImageDraw, ImageFont


class S3Object(TypedDict):
    s3: str


def _write_temp_bytes(data: bytes, suffix: str) -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    return path


def _load_image_bytes(image_url: str | None, image_s3: S3Object | None) -> bytes:
    if image_url:
        resp = requests.get(image_url, timeout=60)
        resp.raise_for_status()
        return resp.content
    if image_s3 and "s3" in image_s3:
        content = wmill.load_s3_file(image_s3)
        if content is None:
            raise ValueError("S3 object not found or empty")
        return bytes(content)
    raise ValueError("Either image_url or image_s3 must be provided")


def _parse_weight(weight: str) -> str:
    normalized = str(weight).strip().lower()
    if normalized.isdigit():
        return "bold" if int(normalized) >= 600 else "normal"
    return "bold" if normalized in ("bold", "600", "700", "800", "900") else "normal"


def _parse_style(style: str) -> str:
    normalized = str(style).strip().lower()
    return "italic" if normalized in ("italic", "oblique") else "normal"


def _load_font_bytes_from_s3(font_s3: S3Object | None) -> bytes | None:
    if not font_s3:
        return None
    content = wmill.load_s3_file(font_s3)
    if content is None:
        raise ValueError("Font S3 object not found or empty")
    return bytes(content)


def _load_font_bytes_from_url(font_url: str | None) -> bytes | None:
    if not font_url:
        return None
    resp = requests.get(font_url, timeout=60)
    resp.raise_for_status()
    return resp.content


def _load_font(
    font: str,
    size: int,
    style: str,
    weight: str,
    font_url: str | None,
    font_s3: S3Object | None,
) -> ImageFont.FreeTypeFont:
    font_bytes = _load_font_bytes_from_url(font_url)
    if font_bytes is None:
        font_bytes = _load_font_bytes_from_s3(font_s3)
    if font_bytes is not None:
        font_path = _write_temp_bytes(font_bytes, suffix=".ttf")
        return ImageFont.truetype(font_path, size=size)

    is_bold = _parse_weight(weight) == "bold"
    is_italic = _parse_style(style) == "italic"

    candidates: list[str] = []
    font_clean = font.strip() if font else ""

    if font_clean:
        if font_clean.lower().endswith((".ttf", ".otf", ".ttc")):
            candidates.append(font_clean)
        if is_bold and is_italic:
            candidates.append(f"{font_clean}-BoldItalic.ttf")
            candidates.append(f"{font_clean}-BoldOblique.ttf")
        elif is_bold:
            candidates.append(f"{font_clean}-Bold.ttf")
        elif is_italic:
            candidates.append(f"{font_clean}-Italic.ttf")
            candidates.append(f"{font_clean}-Oblique.ttf")
        candidates.append(f"{font_clean}.ttf")
        candidates.append(f"{font_clean}.otf")

    if is_bold and is_italic:
        candidates.append("DejaVuSans-BoldOblique.ttf")
    elif is_bold:
        candidates.append("DejaVuSans-Bold.ttf")
    elif is_italic:
        candidates.append("DejaVuSans-Oblique.ttf")
    candidates.append("DejaVuSans.ttf")

    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except Exception:
            continue

    return ImageFont.load_default()


def _measure_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int]:
    bbox = draw.multiline_textbbox((0, 0), text, font=font)
    width = int(bbox[2] - bbox[0])
    height = int(bbox[3] - bbox[1])
    return width, height


def _draw_text_block(
    draw: ImageDraw.ImageDraw,
    text: str,
    anchor: str,
    offset_x: int,
    offset_y: int,
    font: ImageFont.FreeTypeFont,
    fill: str,
    stroke_color: str,
    stroke_width: int,
    image_width: int,
    image_height: int,
) -> None:
    if not text:
        return
    text_width, text_height = _measure_text(draw, text, font)

    if anchor == "top":
        x = (image_width - text_width) // 2 + offset_x
        y = offset_y
    elif anchor == "bottom_left":
        x = offset_x
        y = image_height - text_height - offset_y
    elif anchor == "bottom_right":
        x = image_width - text_width - offset_x
        y = image_height - text_height - offset_y
    else:
        x = offset_x
        y = offset_y

    draw.multiline_text(
        (x, y),
        text,
        font=font,
        fill=fill,
        stroke_width=max(stroke_width, 0),
        stroke_fill=stroke_color if stroke_width > 0 else None,
    )


def main(
    image_url: str | None = None,
    image_s3: S3Object | None = None,
    output_format: str = "png",
    top_text: str = "Верхний текст",
    bottom_left_text: str = "Нижний слева",
    bottom_right_text: str = "Нижний справа",
    top_font: str = "DejaVu-Sans",
    top_size: int = 48,
    top_style: str = "normal",
    top_weight: str = "normal",
    top_color: str = "white",
    top_stroke_color: str = "black",
    top_stroke_width: int = 2,
    top_offset_x: int = 0,
    top_offset_y: int = 40,
    top_font_url: str | None = None,
    top_font_s3: S3Object | None = None,
    bottom_left_font: str = "DejaVu-Sans",
    bottom_left_size: int = 36,
    bottom_left_style: str = "normal",
    bottom_left_weight: str = "normal",
    bottom_left_color: str = "white",
    bottom_left_stroke_color: str = "black",
    bottom_left_stroke_width: int = 2,
    bottom_left_offset_x: int = 40,
    bottom_left_offset_y: int = 40,
    bottom_left_font_url: str | None = None,
    bottom_left_font_s3: S3Object | None = None,
    bottom_right_font: str = "DejaVu-Sans",
    bottom_right_size: int = 36,
    bottom_right_style: str = "normal",
    bottom_right_weight: str = "normal",
    bottom_right_color: str = "white",
    bottom_right_stroke_color: str = "black",
    bottom_right_stroke_width: int = 2,
    bottom_right_offset_x: int = 40,
    bottom_right_offset_y: int = 40,
    bottom_right_font_url: str | None = None,
    bottom_right_font_s3: S3Object | None = None,
    output_s3_path: S3Object | None = None,
) -> S3Object:
    """
    Добавляет текст в 3 местах на изображении.

    @param image_url URL изображения
    @param image_s3 Изображение из Windmill store (S3Object)
    @param output_format Формат результата (png, jpg, webp)
    @param top_text Текст сверху
    @param bottom_left_text Текст снизу слева
    @param bottom_right_text Текст снизу справа
    @param output_s3_path Куда сохранить результат (S3Object) или None для автогенерации
    @return S3Object результата
    """
    image_bytes = _load_image_bytes(image_url, image_s3)
    image = Image.open(io.BytesIO(image_bytes))

    if image.mode not in ("RGBA", "RGB"):
        image = image.convert("RGBA")

    draw = ImageDraw.Draw(image)
    width, height = image.size

    top_font_obj = _load_font(
        top_font,
        top_size,
        top_style,
        top_weight,
        top_font_url,
        top_font_s3,
    )
    bottom_left_font_obj = _load_font(
        bottom_left_font,
        bottom_left_size,
        bottom_left_style,
        bottom_left_weight,
        bottom_left_font_url,
        bottom_left_font_s3,
    )
    bottom_right_font_obj = _load_font(
        bottom_right_font,
        bottom_right_size,
        bottom_right_style,
        bottom_right_weight,
        bottom_right_font_url,
        bottom_right_font_s3,
    )

    _draw_text_block(
        draw,
        top_text,
        "top",
        top_offset_x,
        top_offset_y,
        top_font_obj,
        top_color,
        top_stroke_color,
        top_stroke_width,
        width,
        height,
    )
    _draw_text_block(
        draw,
        bottom_left_text,
        "bottom_left",
        bottom_left_offset_x,
        bottom_left_offset_y,
        bottom_left_font_obj,
        bottom_left_color,
        bottom_left_stroke_color,
        bottom_left_stroke_width,
        width,
        height,
    )
    _draw_text_block(
        draw,
        bottom_right_text,
        "bottom_right",
        bottom_right_offset_x,
        bottom_right_offset_y,
        bottom_right_font_obj,
        bottom_right_color,
        bottom_right_stroke_color,
        bottom_right_stroke_width,
        width,
        height,
    )

    output = io.BytesIO()
    fmt = output_format.strip().lower()
    if fmt in ("jpg", "jpeg") and image.mode == "RGBA":
        image = image.convert("RGB")
    image.save(output, format=fmt.upper())

    return wmill.write_s3_file(output_s3_path, output.getvalue())
