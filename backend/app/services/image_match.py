import re
from pathlib import Path


def match_filename_to_product(filename: str, products_by_pnum: dict[str, str]) -> str | None:
    """파일명에서 품번 토큰을 추출해 products_by_pnum(source_p_number -> product_id)와 매칭."""
    stem = Path(filename).stem
    tokens = re.split(r"[_\-\s]", stem)
    for tok in [stem, *tokens]:
        if tok in products_by_pnum:
            return products_by_pnum[tok]
    return None
