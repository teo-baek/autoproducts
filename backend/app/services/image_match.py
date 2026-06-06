import re
from pathlib import Path


def _strip_dot_zero(s: str) -> str:
    """판다스/포스기가 붙인 실수 표기 끝 `.0` 제거 + 앞뒤 공백 제거 (예: '5015.0' → '5015')."""
    return re.sub(r"\.0$", "", s.strip())


def match_filename_to_product(filename: str, products_by_pnum: dict[str, str]) -> str | None:
    """파일명에서 품번을 추출해 products_by_pnum(source_p_number -> product_id)와 매칭.

    정규화: 확장자 제거 → 끝 `.0` 제거 → trim. 후보 = [정규화 전체, *(_-공백 토큰)] (각 토큰도 끝 `.0` 제거).
    대조: 정확 일치 먼저(전체 → 토큰 순) → 실패 시 대소문자 무시 폴백(거짓충돌 방지로 순서 유지).
    """
    stem = _strip_dot_zero(Path(filename).stem)
    tokens = [_strip_dot_zero(t) for t in re.split(r"[_\-\s]", stem) if t.strip()]
    candidates = [stem, *tokens]

    # 1) 정확 일치 — 전체 정규화 문자열을 토큰보다 먼저
    for c in candidates:
        if c in products_by_pnum:
            return products_by_pnum[c]
    # 2) 대소문자 무시 폴백 — 정확 일치가 모두 실패한 뒤에만
    lower_map = {k.lower(): v for k, v in products_by_pnum.items()}
    for c in candidates:
        v = lower_map.get(c.lower())
        if v is not None:
            return v
    return None
