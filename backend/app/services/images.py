"""상품 대표 이미지 URL 해석 — 공개 카드/카탈로그 공용.

단일 업로드는 `products.representative_image_url` 을 채우지만, **대량 업로드는 `product_images`
에만** 기록(대표 URL 비어있음). 폴백이 없으면 대량 등록 상품은 카드/쇼룸에서 사진이 안 보인다.
"""
from app.core.config import get_settings

IMAGE_BUCKET = "product-images"


def public_image_url(storage_path: str) -> str:
    """Storage 경로 → 공개 URL(버킷이 public). representative_image_url 과 동일 형식."""
    base = get_settings().supabase_url.rstrip("/")
    return f"{base}/storage/v1/object/public/{IMAGE_BUCKET}/{storage_path}"


def representative_image_url(rep_url: str | None, product_images: list[dict] | None) -> str | None:
    """대표 이미지 URL — rep_url 우선, 없으면 product_images(대표 먼저, soft-delete 제외) 폴백."""
    if rep_url:
        return rep_url
    imgs = [im for im in (product_images or []) if not im.get("deleted_at")]
    if not imgs:
        return None
    imgs.sort(key=lambda im: not im.get("is_representative"))  # 대표 먼저
    return public_image_url(imgs[0]["storage_path"])
