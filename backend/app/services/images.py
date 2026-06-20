"""상품 대표 이미지 URL 해석 — 공개 카드/카탈로그 공용.

단일 업로드는 `products.representative_image_url` 을 채우지만, **대량 업로드는 `product_images`
에만** 기록(대표 URL 비어있음). 폴백이 없으면 대량 등록 상품은 카드/쇼룸에서 사진이 안 보인다.
"""
from app.core import gcs
from app.core.config import get_settings


def public_image_url(storage_path: str) -> str:
    """Storage 경로 → 공개 URL(GCS 공개 버킷). representative_image_url 과 동일 형식."""
    return gcs.public_url(storage_path)


def storage_path_from_public_url(url: str | None) -> str | None:
    """공개 URL → 버킷 내 storage 경로(엑셀 셀 이미지 다운로드용).

    단일 업로드 상품은 product_images 행 없이 representative_image_url(전체 공개 URL)만 갖는다.
    엑셀 export 는 storage 경로로 다운로드하므로, 대표 URL 에서 공개 prefix(`GCS_PUBLIC_BASE/`)
    뒤 경로만 추출해 폴백한다. 우리 공개 URL 형식이 아니면 None.
    ⚠️ public_image_url 과 같은 prefix(get_settings().gcs_public_base_url)를 써야 한다 — 불일치 시
    조용히 None → 엑셀 export 사진 누락(과거 회귀 주의).
    """
    if not url:
        return None
    base = get_settings().gcs_public_base_url.rstrip("/") + "/"
    if not url.startswith(base):
        return None
    path = url[len(base):].split("?", 1)[0]
    return path or None


def representative_image_url(rep_url: str | None, product_images: list[dict] | None) -> str | None:
    """대표 이미지 URL — rep_url 우선, 없으면 product_images(대표 먼저, soft-delete 제외) 폴백."""
    if rep_url:
        return rep_url
    imgs = [im for im in (product_images or []) if not im.get("deleted_at")]
    if not imgs:
        return None
    imgs.sort(key=lambda im: not im.get("is_representative"))  # 대표 먼저
    return public_image_url(imgs[0]["storage_path"])
