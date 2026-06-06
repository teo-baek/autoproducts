import csv
import io
from dataclasses import dataclass, field

import openpyxl

TEMPLATE_COLUMNS = ["품번", "상품명", "색상", "사이즈", "도매가", "판매가"]
_KEY = {"품번": "source_p_number", "상품명": "item_name", "색상": "color",
        "사이즈": "size", "도매가": "wholesale_price", "판매가": "retail_price"}
# 검증 오류의 한글 필드명(시안 데이터 검증 결과 표의 '필드' 컬럼)
_FIELD_LABEL = {"source_p_number": "품번", "item_name": "상품명",
                "wholesale_price": "도매가", "retail_price": "판매가"}
# 지원 형식: 신형 엑셀(.xlsx)·구형 엑셀(.xls)·CSV
SUPPORTED_EXTS = (".xlsx", ".xls", ".csv")


@dataclass
class ParseResult:
    rows: list[dict] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)   # {row, field, reason}


def _to_int(v) -> int:
    """셀 값 → 정수. bool/빈값/비숫자는 ValueError. (엑셀 숫자는 float 로 올 수 있음)"""
    if isinstance(v, bool):
        raise ValueError
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    s = str(v).strip().replace(",", "")
    if s == "":
        raise ValueError
    if s.endswith(".0"):          # '1001.0' 같은 구형엑셀/CSV 숫자 표기 보정
        s = s[:-2]
    return int(s)


# ── 형식별 행 리더 (헤더 1행 건너뛰고 셀 리스트를 순서대로 yield) ──────────────
def _rows_xlsx(path: str):
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb.active
    for row in ws.iter_rows(min_row=2, values_only=True):
        yield list(row)


def _rows_xls(path: str):
    import xlrd  # 구형 엑셀 전용(xlrd>=2.0 는 .xls 만 읽음)
    book = xlrd.open_workbook(path)
    sh = book.sheet_by_index(0)
    for r in range(1, sh.nrows):
        yield [sh.cell_value(r, c) for c in range(sh.ncols)]


def _rows_csv(path: str):
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
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    for row in rows[1:]:  # 헤더 제외
        yield row


def _validate_into(cells: list, row_index: int, res: ParseResult) -> None:
    rec = {_KEY[c]: (cells[j] if j < len(cells) else None) for j, c in enumerate(TEMPLATE_COLUMNS)}
    # 완전 빈 행(트레일링 등)은 조용히 건너뜀
    if all(v in (None, "") for v in rec.values()):
        return

    errs: list[dict] = []
    for key in ("source_p_number", "item_name"):       # 필수 텍스트
        if not (rec[key] is not None and str(rec[key]).strip()):
            errs.append({"row": row_index, "field": _FIELD_LABEL[key], "reason": "필수 값이 누락되었습니다"})
    if rec["wholesale_price"] in (None, ""):            # 도매가 = 필수 + 숫자
        errs.append({"row": row_index, "field": "도매가", "reason": "필수 값이 누락되었습니다"})
    else:
        try:
            rec["wholesale_price"] = _to_int(rec["wholesale_price"])
        except (TypeError, ValueError):
            errs.append({"row": row_index, "field": "도매가", "reason": "숫자 형식이 아닙니다"})
    if rec["retail_price"] in (None, ""):              # 판매가 = 선택, 있으면 숫자
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

    오류는 (행, 필드, 사유) 단위로 수집 — 시안 '데이터 유효성 검사 결과' 표와 1:1.
    한 행에 오류가 하나라도 있으면 그 행은 등록 대상에서 제외(insert 안 함).
    """
    low = path.lower()
    if low.endswith(".xls"):
        reader = _rows_xls(path)
    elif low.endswith(".csv"):
        reader = _rows_csv(path)
    else:
        reader = _rows_xlsx(path)

    res = ParseResult()
    for i, cells in enumerate(reader, start=2):
        _validate_into(list(cells), i, res)
    return res
