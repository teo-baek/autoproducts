import re
from pathlib import Path

# 부분일치 폴백에서 너무 짧은 품번이 더 긴 문자열에 우연히 박혀 오매칭되는 걸 막는 최소 길이.
_MIN_SUBSTR = 3


def _strip_dot_zero(s: str) -> str:
    """판다스/포스기가 붙인 실수 표기 끝 `.0` 제거 + 앞뒤 공백 제거 (예: '5015.0' → '5015')."""
    return re.sub(r"\.0$", "", s.strip())


def _bounded_contains(stem_l: str, kl: str) -> bool:
    """kl(소문자 품번)이 stem_l 안에 '경계가 맞게' 들어있으면 True.

    더 긴 숫자/영단어 내부에 우연히 박힌 경우는 거부한다:
      - '501' 이 '5015' 안에 (뒤가 숫자) → 거부
      - 'abc' 가 'abcd' 안에 (뒤가 영문) → 거부
    한글 등 다른 문자가 경계면(예: '상품5015', '셔츠abc123')은 허용 → 글자+숫자 붙은 파일명 매칭.
    """
    start = 0
    while True:
        pos = stem_l.find(kl, start)
        if pos < 0:
            return False
        before = stem_l[pos - 1] if pos > 0 else ""
        after = stem_l[pos + len(kl)] if pos + len(kl) < len(stem_l) else ""
        ok = True
        if kl[0].isdigit() and before.isdigit():
            ok = False
        if kl[-1].isdigit() and after.isdigit():
            ok = False
        if kl[0].isascii() and kl[0].isalpha() and before.isascii() and before.isalpha():
            ok = False
        if kl[-1].isascii() and kl[-1].isalpha() and after.isascii() and after.isalpha():
            ok = False
        if ok:
            return True
        start = pos + 1


def match_filename_to_product(filename: str, products_by_pnum: dict[str, str]) -> str | None:
    """파일명에서 품번을 찾아 products_by_pnum(source_p_number -> product_id)와 매칭.

    품번은 '숫자만'이 아니라 영숫자(F-SLK-001 등)일 수 있으므로, 실제 품번 문자열과 대조한다.
    후보: [정규화 전체, *(_-공백 토큰), *숫자런]. 각 토큰/전체는 끝 `.0` 제거.
      - 숫자런(\\d+) 후보 → '상품5015.jpg'처럼 글자+숫자가 붙어도 숫자 품번을 잡아냄.
    대조 순서: 정확 일치 → 대소문자 무시 → (최종) 경계 가드 부분일치(긴 품번 우선).
    """
    stem = _strip_dot_zero(Path(filename).stem)
    tokens = [_strip_dot_zero(t) for t in re.split(r"[_\-\s]", stem) if t.strip()]
    digit_runs = re.findall(r"\d+", stem)

    seen: set[str] = set()
    cands: list[str] = []
    for c in [stem, *tokens, *digit_runs]:
        if c and c not in seen:
            seen.add(c)
            cands.append(c)

    # 1) 정확 일치 — 전체 → 토큰 → 숫자런 순
    for c in cands:
        if c in products_by_pnum:
            return products_by_pnum[c]
    # 2) 대소문자 무시 폴백
    lower_map = {k.lower(): v for k, v in products_by_pnum.items()}
    for c in cands:
        v = lower_map.get(c.lower())
        if v is not None:
            return v
    # 3) 경계 가드 부분일치 — 품번이 파일명 안에 박힌 경우(글자+숫자 붙음). 가장 긴 품번 우선.
    stem_l = stem.lower()
    best: tuple[str, str] | None = None
    for k, v in products_by_pnum.items():
        kl = k.lower()
        if len(kl) >= _MIN_SUBSTR and _bounded_contains(stem_l, kl):
            if best is None or len(kl) > len(best[0]):
                best = (kl, v)
    return best[1] if best else None
