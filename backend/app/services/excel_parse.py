import csv
import io
import re
from dataclasses import dataclass, field

import openpyxl

TEMPLATE_COLUMNS = ["품번", "상품명", "색상", "사이즈", "도매가", "판매가"]
_KEY = {"품번": "source_p_number", "상품명": "item_name", "색상": "color",
        "사이즈": "size", "도매가": "wholesale_price", "판매가": "retail_price"}
# 검증 오류의 한글 필드명(시안 데이터 검증 결과 표의 '필드' 컬럼)
_FIELD_LABEL = {"source_p_number": "품번", "item_name": "상품명",
                "wholesale_price": "도매가", "retail_price": "판매가"}
# 헤더 이름 매칭용 별칭(순서가 달라도, 표기가 조금 달라도 찾도록)
_ALIASES = {
    "source_p_number": ["품번", "상품코드", "제품코드", "품목코드", "코드", "sku"],
    "item_name": ["상품명", "품명", "제품명", "상품이름"],
    "color": ["색상", "컬러", "color"],
    "size": ["사이즈", "size", "규격"],
    "wholesale_price": ["도매가", "도매가격", "공급가", "공급가격", "단가"],
    "retail_price": ["판매가", "소매가", "소비자가", "권장소비자가", "판매가격", "소매가격"],
}
SUPPORTED_EXTS = (".xlsx", ".xls", ".csv")


@dataclass
class ParseResult:
    rows: list[dict] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)   # {row, field, reason}


def _to_int(v) -> int:
    """셀 값 → 정수. 통화기호(₩/$)·'원'·공백·콤마 등은 제거하고 숫자만 해석.

    숫자처럼 보이는 값('₩280,000원', '280000.0', 1001.0)은 통과,
    진짜 비숫자('가격미정')는 ValueError.
    """
    if isinstance(v, bool):
        raise ValueError
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    s = re.sub(r"[^\d.\-]", "", str(v).strip())   # 숫자/소수점/음수 외 전부 제거
    if s in ("", "-", ".", "-.", "-"):
        raise ValueError
    return int(float(s))


def _norm(h) -> str:
    return str(h).strip().replace(" ", "").lower() if h is not None else ""


def _header_index(header_cells: list) -> dict | None:
    """헤더 행에서 각 표준 컬럼의 위치를 별칭으로 찾는다.

    필수 3개(품번·상품명·도매가)가 헤더에 하나도 없으면 헤더가 아니라고 보고
    None 을 반환 → 위치(컬럼 순서) 기반으로 폴백.
    """
    norm = [_norm(c) for c in header_cells]
    idx: dict = {}
    for key, names in _ALIASES.items():
        found = None
        for nm in names:
            n = _norm(nm)
            if n in norm:
                found = norm.index(n)
                break
        idx[key] = found
    if idx["source_p_number"] is None and idx["item_name"] is None and idx["wholesale_price"] is None:
        return None
    return idx


# ── 형식별 전체 행 리더(헤더 포함) ───────────────────────────────────────────
def _read_all_rows(path: str) -> list[list]:
    low = path.lower()
    if low.endswith(".xls"):
        import xlrd  # 구형 엑셀 전용(xlrd>=2.0 는 .xls 만 읽음)
        book = xlrd.open_workbook(path)
        sh = book.sheet_by_index(0)
        return [[sh.cell_value(r, c) for c in range(sh.ncols)] for r in range(sh.nrows)]
    if low.endswith(".csv"):
        with open(path, "rb") as f:
            raw = f.read()
        text = None
        for enc in ("utf-8-sig", "cp949", "euc-kr", "utf-8"):  # 한글 CSV(엑셀 ANSI=cp949) 대응
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            text = raw.decode("utf-8", errors="replace")
        return [list(r) for r in csv.reader(io.StringIO(text))]
    # 기본 .xlsx
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb.active
    return [list(r) for r in ws.iter_rows(values_only=True)]


def _rec_from(cells: list, col: dict | None) -> dict:
    if col is not None:  # 헤더 매칭 — 순서 무관
        return {
            key: (cells[i] if (i is not None and i < len(cells)) else None)
            for key, i in col.items()
        }
    # 위치 기반 폴백(헤더 없음): 표준 컬럼 순서대로
    return {_KEY[c]: (cells[j] if j < len(cells) else None) for j, c in enumerate(TEMPLATE_COLUMNS)}


def _validate_into(cells: list, row_index: int, res: ParseResult, col: dict | None) -> None:
    rec = _rec_from(cells, col)
    if all(v in (None, "") for v in rec.values()):   # 완전 빈 행은 건너뜀
        return

    errs: list[dict] = []
    for key in ("source_p_number", "item_name"):       # 필수 텍스트
        if not (rec.get(key) is not None and str(rec[key]).strip()):
            errs.append({"row": row_index, "field": _FIELD_LABEL[key], "reason": "필수 값이 누락되었습니다"})
    if rec.get("wholesale_price") in (None, ""):        # 도매가 = 필수 + 숫자
        errs.append({"row": row_index, "field": "도매가", "reason": "필수 값이 누락되었습니다"})
    else:
        try:
            rec["wholesale_price"] = _to_int(rec["wholesale_price"])
        except (TypeError, ValueError):
            errs.append({"row": row_index, "field": "도매가", "reason": "숫자 형식이 아닙니다"})
    if rec.get("retail_price") in (None, ""):          # 판매가 = 선택, 있으면 숫자
        rec["retail_price"] = None
    else:
        try:
            rec["retail_price"] = _to_int(rec["retail_price"])
        except (TypeError, ValueError):
            errs.append({"row": row_index, "field": "판매가", "reason": "숫자 형식이 아닙니다"})

    if errs:
        res.errors.extend(errs)
    else:
        res.rows.append(rec)


def parse_template_rows(path: str) -> ParseResult:
    """표준 템플릿 파싱 + 필드 단위 검증. 형식(.xlsx/.xls/.csv)은 확장자로 분기.

    1행을 헤더로 보고 컬럼명(별칭)으로 위치를 찾는다(열 순서/추가열 무관).
    헤더가 표준과 전혀 다르면 위치(컬럼 순서) 기반으로 폴백.
    오류는 (행, 필드, 사유) 단위 — 시안 '데이터 유효성 검사 결과' 표와 1:1.
    """
    all_rows = _read_all_rows(path)
    res = ParseResult()
    if not all_rows:
        return res
    col = _header_index(all_rows[0])
    for i, cells in enumerate(all_rows[1:], start=2):
        _validate_into(list(cells), i, res, col)
    return res
