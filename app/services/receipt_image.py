from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener

register_heif_opener(thumbnails=False)


class ReceiptImageError(ValueError):
    pass


@dataclass(frozen=True)
class PreparedReceiptImage:
    data: bytes
    content_type: str
    extension: str
    width: int
    height: int


def prepare_receipt_image(
    image: bytes,
    *,
    max_dimension: int,
    webp_quality: int,
    max_pixels: int,
) -> PreparedReceiptImage:
    """Normalize a receipt photo and encode it as a compact, metadata-free WebP."""
    try:
        with Image.open(BytesIO(image)) as source:
            if source.width * source.height > max_pixels:
                raise ReceiptImageError(
                    f"Image has too many pixels; maximum is {max_pixels:,}"
                )

            normalized = ImageOps.exif_transpose(source)
            normalized.load()
            rgb = _on_white_background(normalized)
    except ReceiptImageError:
        raise
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError) as exc:
        raise ReceiptImageError("File is not a valid supported receipt image") from exc

    rgb.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
    output = BytesIO()
    try:
        rgb.save(output, format="WEBP", quality=webp_quality, method=6)
    except OSError as exc:
        raise ReceiptImageError("Receipt image could not be compressed") from exc

    return PreparedReceiptImage(
        data=output.getvalue(),
        content_type="image/webp",
        extension=".webp",
        width=rgb.width,
        height=rgb.height,
    )


def _on_white_background(image: Image.Image) -> Image.Image:
    if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
        rgba = image.convert("RGBA")
        background = Image.new("RGBA", rgba.size, "white")
        return Image.alpha_composite(background, rgba).convert("RGB")
    return image.convert("RGB")
