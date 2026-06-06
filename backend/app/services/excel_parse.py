from dataclasses import dataclass, field
import openpyxl

TEMPLATE_COLUMNS = ["품번", "상품명", "색상", "사이즈", "도매가", "판매가"]
_KEY = {"품번": "source_p_number", "상품명": "item_name", "색상": "color",
        "사이즈": "size", "도매가": "wholesale_price", "판매가": "retail_price"}
# 검증 오류의 한글 필드명(시안 데이터 검증 결과 표의 '필드' 컬럼)
_FIELD_LABEL = {"source_p_number": "품번", "item_name": "상품명",
                "wholesale_price": "도매가", "retail_price": "판매가"}


@dataclass
class ParseResult:
    rows: list[dict] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)   # {row, field, reason}


def _to_int(v) -> int:
    """엑셀 셀 → 정수. bool/빈값/비숫자는 ValueError."""
    if isinstance(v, bool):
        raise ValueError
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    s = str(v).strip().replace(",", "")
    if s == "":
        raise ValueError
    return int(s)


def parse_template_rows(path: str) -> ParseResult:
    """표준 템플릿 파싱 + 필드 단위 검증.

    오류는 (행, 필드, 사유) 단위로 수집 — 시안 '데이터 유효성 검사 결과' 표와 1:1.
    한 행에 오류가 하나라도 있으면 그 행은 등록 대상에서 제외(insert 안 함).
    """
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb.active
    res = ParseResult()
    for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        rec = {_KEY[c]: (row[j] if j < len(row) else None) for j, c in enumerate(TEMPLATE_COLUMNS)}
        # 완전 빈 행(트레일링 등)은 조용히 건너뜀
        if all(v in (None, "") for v in rec.values()):
            continue

        errs: list[dict] = []
        # 필수 텍스트
        for key in ("source_p_number", "item_name"):
            if not (rec[key] and str(rec[key]).strip()):
                errs.append({"row": i, "field": _FIELD_LABEL[key], "reason": "필수 값이 누락되었습니다"})
        # 도매가 = 필수 + 숫자
        if rec["wholesale_price"] in (None, ""):
            errs.append({"row": i, "field": "도매가", "reason": "필수 값이 누락되었습니다"})
        else:
            try:
                rec["wholesale_price"] = _to_int(rec["wholesale_price"])
            except (TypeError, ValueError):
                errs.append({"row": i, "field": "도매가", "reason": "숫자 형식이 아닙니다"})
        # 판매가 = 선택, 있으면 숫자
        if rec["retail_price"] in (None, ""):
            rec["retail_price"] = None
        else:
            try:
                rec["retail_price"] = _to_int(rec["retail_price"])
            except (TypeError, ValueError):
                errs.append({"row": i, "field": "판매가", "reason": "숫자 형식이 아닙니다"})

        if errs:
            res.errors.extend(errs)
        else:
            res.rows.append(rec)
    return res
