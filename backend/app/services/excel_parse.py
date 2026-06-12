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
                "wholesale_price": "도매가", "retail_price": "판매가",
                "fabric_composition": "혼용률", "stock": "재고"}
# 헤더 이름 매칭용 별칭(순서 = 우선순위; 매장마다 다른 포스기 열 이름을 흡수).
# jinsup_dev SYNONYMS_POOL 을 흡수해 병합. ⚠️ 한 필드에 여러 헤더가 동시에 있으면
# 목록의 앞쪽이 이긴다 — 예: 실제 LALAS POS 엔 '입고가'·'도매가'·'도매Sale' 이 모두 있어
# '도매가' 를 맨 앞에 둬야 올바른 열을 고른다.
_ALIASES = {
    "source_p_number": ["품번", "상품코드", "품목코드", "모델명", "제품코드", "코드", "sku"],
    "item_name": ["상품명", "품목명", "물품명", "제품명", "품명", "상품이름"],
    "color": ["색상", "칼라", "칼러", "컬러", "색상명", "컬러명", "color"],
    "size": ["상세사이즈", "사이즈", "규격", "size"],
    "wholesale_price": ["도매가", "도매단가", "입고가", "공급가", "도매가격", "공급가격", "단가"],
    "retail_price": ["소매가", "판매가", "소비자가", "매장판매가", "권장소비자가", "판매가격", "소매가격"],
    # 선택 컬럼(있으면 인입, 없어도 무방)
    "fabric_composition": ["혼용률", "혼방률", "소재"],
    "stock": ["재고정상", "재고", "현재고", "매장량", "수량"],
}
# 헤더에 반드시 있어야 하는 논리 컬럼(없으면 파일 단위 오류). 품번·상품명·도매가만 파일 단위로 막는다.
# ⚠️ 색상·사이즈는 일부러 여기 넣지 않는다 — 컬럼이 없어도 파일을 통째로 막지 말고, '행 단위 누락 오류'로
# 검증 표(_validate_into)에 어디가 빠졌는지 정확히 보여주기 위함(사용자 피드백). 판매가/재고/혼용률은 선택.
_REQUIRED = {"source_p_number": "품번", "item_name": "상품명", "wholesale_price": "도매가"}
SUPPORTED_EXTS = (".xlsx", ".xls", ".csv")


class ExcelFormatError(Exception):
    """파일 단위 형식 오류(필수 컬럼 누락 등) → 라우트에서 400 친화 메시지로."""


@dataclass
class ParseResult:
    rows: list[dict] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)   # {row, field, reason}
    dropped: int = 0   # 품번 없어 폐기한 행 수(에러 아님 — 사용자 정책)


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


def _to_int_lenient(v) -> int:
    """선택 수량(재고)용 — 변환 실패/빈값이면 0. 상품 등록을 막지 않는다(가격과 달리 운영 메타)."""
    if v in (None, ""):
        return 0
    try:
        return _to_int(v)
    except (TypeError, ValueError):
        return 0


def _text(v) -> str:
    """셀 값 → 표시용 텍스트(공백 제거). 정수형 부동소수(95.0)는 '95' 로 — 엑셀 숫자 사이즈의
    부동소수 잔재를 없애 TEXT 컬럼(color/size)에 안전하게 넣는다."""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def _norm(h) -> str:
    return str(h).strip().replace(" ", "").lower() if h is not None else ""


def _header_index(header_cells: list) -> dict:
    """헤더 행에서 각 표준 컬럼의 위치를 별칭으로 찾는다(순서/우선순위 적용).

    한 필드의 별칭이 여러 개 헤더에 있으면 _ALIASES 목록의 앞쪽(우선순위 높음)을 택한다.
    못 찾은 컬럼은 None.
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


def _rec_from(cells: list, col: dict) -> dict:
    """헤더 매칭 결과(col)로 한 행을 표준 키 dict 로 — 열 순서 무관."""
    return {
        key: (cells[i] if (i is not None and i < len(cells)) else None)
        for key, i in col.items()
    }


def _validate_into(cells: list, row_index: int, res: ParseResult, col: dict) -> None:
    rec = _rec_from(cells, col)
    if all(v in (None, "") for v in rec.values()):   # 완전 빈 행은 건너뜀
        return

    has_pnum = rec.get("source_p_number") is not None and str(rec["source_p_number"]).strip()
    has_name = rec.get("item_name") is not None and str(rec["item_name"]).strip()

    # 품번이 없을 때(QA 3차 1p):
    #  - 상품명도 없으면 POS 합계/소계 같은 잡행 → 조용히 폐기(dropped, 에러 아님).
    #  - 상품명이 있으면 진짜 상품으로 보고 '이지머스 자체 품번(platform_code)'으로 등록한다.
    #    파서는 source_p_number=None 마커만 남기고, ingest_excel 이 platform_code 로 채운다.
    #    이미지 자동매칭(품번 기준)은 안 되므로 미매칭 상품 관리에서 수동 연결.
    if not has_pnum:
        if not has_name:
            res.dropped += 1
            return
        rec["source_p_number"] = None
    else:
        rec["source_p_number"] = str(rec["source_p_number"]).strip()

    errs: list[dict] = []
    if not has_name:   # 품번은 있는데 상품명이 없으면(잡행과 구분) 오류
        errs.append({"row": row_index, "field": "상품명", "reason": "필수 값이 누락되었습니다"})
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

    # 색상·사이즈 = 필수(SKU 식별 + DB product_skus NOT NULL). 비면 검증 단계에서 오류로 잡아
    # '검사 통과 → 커밋 시 NOT NULL 실패(0건 등록)' 불일치를 차단한다. 숫자 사이즈(95)는 텍스트로 정규화.
    for fld, label in (("color", "색상"), ("size", "사이즈")):
        v = rec.get(fld)
        if v is None or not str(v).strip():
            errs.append({"row": row_index, "field": label, "reason": "필수 값이 누락되었습니다"})
        else:
            rec[fld] = _text(v)

    # 선택 컬럼 — 재고(관대: 비숫자는 0, 행을 막지 않음), 혼용률(자유 텍스트)
    rec["stock"] = _to_int_lenient(rec.get("stock"))
    fab = rec.get("fabric_composition")
    rec["fabric_composition"] = str(fab).strip() if (fab is not None and str(fab).strip()) else None

    if errs:
        res.errors.extend(errs)
    else:
        res.rows.append(rec)


def parse_template_rows(path: str) -> ParseResult:
    """표준 템플릿 파싱 + 필드 단위 검증. 형식(.xlsx/.xls/.csv)은 확장자로 분기.

    1행을 헤더로 보고 컬럼명(별칭)으로 위치를 찾는다(열 순서/추가열 무관).
    필수 논리컬럼(품번·상품명·도매가)이 헤더에 없으면 ExcelFormatError(파일 단위).
    행 단위 오류는 (행, 필드, 사유) — 시안 '데이터 유효성 검사 결과' 표와 1:1.
    """
    all_rows = _read_all_rows(path)
    res = ParseResult()
    if not all_rows:
        return res
    col = _header_index(all_rows[0])
    missing = [label for key, label in _REQUIRED.items() if col.get(key) is None]
    if missing:
        raise ExcelFormatError(
            "필수 컬럼을 찾을 수 없습니다: " + ", ".join(missing)
            + ". 첫 행에 품번·상품명·도매가 컬럼명이 있는지 확인해주세요."
        )
    for i, cells in enumerate(all_rows[1:], start=2):
        _validate_into(list(cells), i, res, col)
    return res
