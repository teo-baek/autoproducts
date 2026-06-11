"""테넌트(도매관리자) 스코프 헬퍼 — 멀티테넌트 1차.

도매관리자(테넌트) 단위로 상품을 보이게 하는 공용 스코프 계산.
격리는 앱레이어 책임(service-key 우회, RLS 전환은 범위 밖). 1차엔 LALAS 단일 테넌트.
"""


def scoped_wholesaler_ids(sb, manager_id: str | None) -> list[str]:
    """`manager_id`(도매관리자)에 소속된 (살아있는) 도매상 id 목록.

    manager_id 가 없으면 [] 반환(fail-closed — 과노출 금지). 호출부는 이 목록으로
    `products.wholesaler_id` 를 `.in_(...)` 필터한다. 빈 목록 → 빈 카탈로그.
    """
    if not manager_id:
        return []
    rows = (
        sb.table("manager_wholesalers")
        .select("wholesaler_id")
        .eq("manager_id", manager_id)
        .is_("deleted_at", "null")
        .execute()
        .data
        or []
    )
    return [r["wholesaler_id"] for r in rows if r.get("wholesaler_id")]
