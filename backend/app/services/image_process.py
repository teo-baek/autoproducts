"""상품 이미지 서버측 가공 — EXIF 정면보정 → RGB → 웹용 썸네일 JPEG.

jinsup_dev `drive.py._to_excel_thumbnail` 의 PIL 파이프라인을 흡수하되:
- 엑셀 셀용 90×110 이 아니라 **웹 카탈로그용 크기**(긴 변 기준 상한)로 리사이즈한다.
- 구글드라이브/GAS/urllib 소싱은 **가져오지 않는다**(프론트→Storage 직접 업로드 모델 유지).
- 깨진 이미지 1장이 배치 전체를 죽이지 않도록 이미지 단위로 격리한다(예외 전파 X, 상태값 반환).
"""
import io
from dataclasses import dataclass
from typing import Literal

from PIL import Image as PILImage
from PIL import ImageOps, UnidentifiedImageError

# 웹 카탈로그용 리사이즈 상한(긴 변 px). thumbnail() 은 비율 유지하며 박스 안에 맞춤(확대 안 함).
WEB_MAX_BOX = (800, 800)
JPEG_QUALITY = 85


@dataclass
class ProcessedImage:
    """이미지 한 장 가공 결과. status='ok' 일 때만 data 가 JPEG bytes."""
    status: Literal["ok", "error"]
    data: bytes | None = None
    width: int | None = None
    height: int | None = None
    error: str | None = None


def process_image_bytes(raw: bytes, box: tuple[int, int] = WEB_MAX_BOX,
                        quality: int = JPEG_QUALITY) -> ProcessedImage:
    """원본 바이트 → EXIF 정면 보정 → RGB → box 안으로 축소 → JPEG bytes.

    어떤 이유로든 디코딩/가공 실패 시 예외를 전파하지 않고 status='error' 로 반환.
    """
    try:
        img = PILImage.open(io.BytesIO(raw))
        img = ImageOps.exif_transpose(img)       # EXIF 회전 정면 보정
        img = img.convert("RGB")
        img.thumbnail(box)                        # 비율 유지, 박스 안으로 축소(확대 안 함)
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=quality, optimize=True)
        return ProcessedImage(status="ok", data=out.getvalue(),
                              width=img.width, height=img.height)
    except (UnidentifiedImageError, OSError, ValueError, TypeError) as e:
        return ProcessedImage(status="error", error=str(e)[:200])


def thumb_path(storage_path: str, prefix: str = "thumbs/") -> str:
    """원본 storage 경로 → 파생 썸네일 경로. 확장자는 .jpg 로 통일.

    예: 'w1/1001_front.png' → 'thumbs/w1/1001_front.jpg'
    """
    stem = storage_path.rsplit(".", 1)[0] if "." in storage_path.rsplit("/", 1)[-1] else storage_path
    return f"{prefix}{stem}.jpg"
