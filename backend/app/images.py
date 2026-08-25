from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image

from .config import settings
from .schemas import PartDetection


def ensure_storage() -> None:
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.crop_dir.mkdir(parents=True, exist_ok=True)


async def save_upload(file: UploadFile) -> Path:
    ensure_storage()
    suffix = Path(file.filename or "image.jpg").suffix.lower() or ".jpg"
    target = settings.upload_dir / f"{uuid4()}{suffix}"
    target.write_bytes(await file.read())
    return target


def create_crop(image_path: Path, detection: PartDetection) -> str | None:
    ensure_storage()
    try:
        with Image.open(image_path) as image:
            width, height = image.size
            box = detection.bbox
            left = max(0, int(box.x * width))
            top = max(0, int(box.y * height))
            right = min(width, int((box.x + box.width) * width))
            bottom = min(height, int((box.y + box.height) * height))
            if right <= left or bottom <= top:
                return None
            crop = image.crop((left, top, right, bottom))
            filename = f"{uuid4()}.jpg"
            crop.save(settings.crop_dir / filename, format="JPEG", quality=90)
            return f"/storage/crops/{filename}"
    except Exception:
        return None
