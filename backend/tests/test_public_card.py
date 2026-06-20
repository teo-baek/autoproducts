"""공개 QR 카드 이미지 선택 — representative_image_url 우선, 없으면 product_images 폴백.

대량 업로드는 product_images 에만 사진을 기록(대표 URL 비어있음) → 공개 카드에서도 보여야 함.
"""
from app.core.config import get_settings
from app.routers.public import _pick_image, _public_image_url, shape_card_skus, build_card
from app.schemas.auth import CurrentUser


def test_pick_image_prefers_representative_url():
    row = {
        "representative_image_url": "https://x/rep.jpg",
        "product_images": [{"storage_path": "a/b.jpg", "is_representative": True, "deleted_at": None}],
    }
    assert _pick_image(row) == "https://x/rep.jpg"


def test_pick_image_falls_back_to_product_images_representative_first():
    row = {
        "representative_image_url": None,
        "product_images": [
            {"storage_path": "w/staging/x.jpg", "is_representative": False, "deleted_at": None},
            {"storage_path": "w/staging/rep.jpg", "is_representative": True, "deleted_at": None},
        ],
    }
    url = _pick_image(row)
    assert url is not None
    assert url == f"{get_settings().gcs_public_base_url.rstrip('/')}/w/staging/rep.jpg"  # 대표 먼저 선택


def test_pick_image_skips_soft_deleted_and_empty():
    assert _pick_image({
        "representative_image_url": None,
        "product_images": [{"storage_path": "d.jpg", "is_representative": True, "deleted_at": "2026-01-01"}],
    }) is None
    assert _pick_image({"representative_image_url": None, "product_images": []}) is None
    assert _pick_image({"representative_image_url": None}) is None


def test_public_image_url_shape():
    base = get_settings().gcs_public_base_url.rstrip("/")
    assert _public_image_url("w/staging/x.jpg") == f"{base}/w/staging/x.jpg"


# ── 로그인 뷰어 카드 옵션(색상/사이즈/재고 + 역할별 가격) ─────────────────────
def _row():
    return {
        "wholesaler_id": "w1",
        "product_skus": [
            {"color": "블랙", "size": "S", "wholesale_price": 6000, "retail_price": 12000, "stock": 3, "deleted_at": None},
            {"color": "블랙", "size": "M", "wholesale_price": 6000, "retail_price": 12000, "stock": 0, "deleted_at": None},
            # soft-delete 된 SKU 는 카드에서 제외돼야 함
            {"color": "화이트", "size": "S", "wholesale_price": 6000, "retail_price": 12000, "stock": 5, "deleted_at": "2026-01-01"},
        ],
    }


def test_card_skus_independent_seller_sees_wholesale():
    viewer = CurrentUser(id="u", role="retail_seller", status="approved", seller_type="independent")
    skus = shape_card_skus(_row(), viewer)
    assert len(skus) == 2  # soft-delete 제외
    assert skus[0] == {"color": "블랙", "size": "S", "stock": 3, "price": 6000}  # 라이브셀러 → 도매가


def test_card_skus_agency_affiliated_price_hidden():
    viewer = CurrentUser(id="u", role="retail_seller", status="approved", seller_type="agency_affiliated")
    skus = shape_card_skus(_row(), viewer)
    assert all(s.get("price") is None for s in skus)  # 에이전시 소속 → 가격 미노출
    assert skus[0]["stock"] == 3                       # 재고는 노출(가격만 가림)


def test_card_skus_wholesaler_owner_sees_both_prices():
    viewer = CurrentUser(id="u", role="wholesaler", status="approved", wholesaler_id="w1")
    skus = shape_card_skus(_row(), viewer)
    assert skus[0]["wholesale_price"] == 6000 and skus[0]["retail_price"] == 12000


# ── 공개 카드 조립 + 테넌트 스코프(FR-4) ─────────────────────────────────────
def _card_row():
    return {
        "platform_code": "EZM-1", "source_p_number": "P1", "item_name": "셔츠",
        "fabric_composition": "면", "origin": "KR", "wholesaler_id": "w1",
        "representative_image_url": "https://x/r.jpg", "product_images": [],
        "product_skus": [
            {"color": "블랙", "size": "S", "wholesale_price": 6000, "retail_price": 12000, "stock": 3, "deleted_at": None},
        ],
    }


def test_build_card_anonymous_has_no_skus():
    card = build_card(_card_row(), None, [])
    assert "skus" not in card                 # 비로그인 → 가격/재고 없음
    assert card["platform_code"] == "EZM-1"   # 공개 최소 필드는 유지
    assert card["representative_image_url"] == "https://x/r.jpg"


def test_build_card_in_scope_seller_gets_skus():
    viewer = CurrentUser(id="u", role="retail_seller", status="approved",
                         seller_type="independent", manager_id="m1")
    card = build_card(_card_row(), viewer, ["w1"])  # 상품 도매(w1) 가 스코프 내
    assert "skus" in card and card["skus"][0]["price"] == 6000


def test_build_card_out_of_scope_no_skus():
    viewer = CurrentUser(id="u", role="retail_seller", status="approved",
                         seller_type="independent", manager_id="m1")
    card = build_card(_card_row(), viewer, ["w-other"])  # 상품 도매(w1) 가 스코프 밖
    assert "skus" not in card                            # 404 아님 — 공개 카드만, 가격/재고 없음
    assert card["platform_code"] == "EZM-1"


def test_build_card_unapproved_no_skus():
    viewer = CurrentUser(id="u", role="retail_seller", status="pending",
                         seller_type="independent", manager_id="m1")
    card = build_card(_card_row(), viewer, ["w1"])
    assert "skus" not in card  # 미승인 → 가격/재고 없음
