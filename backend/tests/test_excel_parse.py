import csv
import openpyxl
from app.services.excel_parse import parse_template_rows, TEMPLATE_COLUMNS

def _make_xlsx(tmp_path, rows):
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(TEMPLATE_COLUMNS)
    for r in rows: ws.append(r)
    p = tmp_path / "t.xlsx"; wb.save(p); return p

def _make_csv(tmp_path, rows, encoding="utf-8-sig"):
    p = tmp_path / "t.csv"
    with open(p, "w", newline="", encoding=encoding) as f:
        w = csv.writer(f)
        w.writerow(TEMPLATE_COLUMNS)
        for r in rows: w.writerow(r)
    return p

def _make_xls(tmp_path, rows):
    import xlwt
    wb = xlwt.Workbook(); ws = wb.add_sheet("s")
    for j, c in enumerate(TEMPLATE_COLUMNS): ws.write(0, j, c)
    for i, r in enumerate(rows, start=1):
        for j, v in enumerate(r): ws.write(i, j, v)
    p = tmp_path / "t.xls"; wb.save(str(p)); return p


def test_parse_csv_valid(tmp_path):
    p = _make_csv(tmp_path, [["1001", "린넨셔츠", "화이트", "F", "12000", "29000"]])
    parsed = parse_template_rows(str(p))
    assert parsed.errors == []
    assert parsed.rows[0]["source_p_number"] == "1001"
    assert parsed.rows[0]["wholesale_price"] == 12000

def test_parse_csv_cp949_korean(tmp_path):
    # 한글 엑셀의 ANSI(cp949) CSV 도 읽혀야 함
    p = _make_csv(tmp_path, [["1002", "한글상품", "블랙", "L", "15000", "30000"]], encoding="cp949")
    parsed = parse_template_rows(str(p))
    assert parsed.rows[0]["item_name"] == "한글상품"

def test_parse_currency_and_won(tmp_path):
    # 도매가/판매가에 ₩·원·콤마가 섞여도 숫자로 해석 ('분명 맞는데' 케이스)
    p = _make_xlsx(tmp_path, [["F-1", "실크블라우스", "블랙", "M", "₩280,000원", "350,000 원"]])
    parsed = parse_template_rows(str(p))
    assert parsed.errors == []
    assert parsed.rows[0]["wholesale_price"] == 280000
    assert parsed.rows[0]["retail_price"] == 350000


def test_parse_header_order_independent(tmp_path):
    # 열 순서가 다르고 추가 열(카테고리)이 있어도 헤더 이름으로 매칭
    p = tmp_path / "t.xlsx"
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["상품명", "품번", "카테고리", "도매가", "판매가", "색상", "사이즈"])
    ws.append(["실크블라우스", "F-SLK-001", "의류", "280000", "350000", "아이보리", "S"])
    wb.save(p)
    parsed = parse_template_rows(str(p))
    assert parsed.errors == []
    r = parsed.rows[0]
    assert r["source_p_number"] == "F-SLK-001"
    assert r["wholesale_price"] == 280000
    assert r["color"] == "아이보리"


def test_parse_alias_header(tmp_path):
    # 별칭 헤더(공급가/소비자가/상품코드)도 인식
    p = tmp_path / "t.xlsx"
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["상품코드", "상품명", "색상", "사이즈", "공급가", "소비자가"])
    ws.append(["A-1", "코트", "네이비", "L", "120000", "200000"])
    wb.save(p)
    parsed = parse_template_rows(str(p))
    assert parsed.errors == []
    assert parsed.rows[0]["wholesale_price"] == 120000


def test_parse_blank_pnum_falls_back_to_item_name(tmp_path):
    # 품번 비었지만 상품명 있으면 상품명을 품번 대용으로 등록(데이터 손실 방지)
    p = _make_xlsx(tmp_path, [["", "프릴리OPS", "블랙", "F", "18000", ""]])
    parsed = parse_template_rows(str(p))
    assert parsed.errors == []
    assert parsed.rows[0]["source_p_number"] == "프릴리OPS"


def test_parse_blank_pnum_and_name_excluded(tmp_path):
    # 품번·상품명 둘 다 없으면(도매가만) 식별 불가 → 제외(오류)
    p = _make_xlsx(tmp_path, [["", "", "블랙", "F", "18000", ""]])
    parsed = parse_template_rows(str(p))
    assert parsed.rows == []
    fields = {e["field"] for e in parsed.errors}
    assert "품번" in fields and "상품명" in fields


def test_parse_xls_valid(tmp_path):
    # 구형 엑셀(.xls) — 숫자는 float 로 들어와도 _to_int 가 보정
    p = _make_xls(tmp_path, [["2001", "울코트", "네이비", "M", 50000, 99000]])
    parsed = parse_template_rows(str(p))
    assert parsed.errors == []
    assert parsed.rows[0]["wholesale_price"] == 50000
    assert parsed.rows[0]["retail_price"] == 99000

def test_parse_valid_rows(tmp_path):
    p = _make_xlsx(tmp_path, [["1001","린넨셔츠","화이트","F","12000","29000"]])
    parsed = parse_template_rows(str(p))
    assert parsed.rows[0]["source_p_number"] == "1001"
    assert parsed.rows[0]["wholesale_price"] == 12000
    assert parsed.errors == []

def test_parse_missing_price_is_error(tmp_path):
    p = _make_xlsx(tmp_path, [["1002","바지","블랙","L","","20000"]])
    parsed = parse_template_rows(str(p))
    assert parsed.errors and parsed.errors[0]["row"] == 2
    assert parsed.errors[0]["field"] == "도매가"          # 필드 단위 보고
    assert parsed.errors[0]["reason"] == "필수 값이 누락되었습니다"


def test_parse_non_numeric_price_is_error(tmp_path):
    p = _make_xlsx(tmp_path, [["1003","니트","그레이","M","열두개","20000"]])
    parsed = parse_template_rows(str(p))
    assert parsed.rows == []
    e = parsed.errors[0]
    assert e["field"] == "도매가" and e["reason"] == "숫자 형식이 아닙니다"


def test_parse_missing_required_text_reports_field(tmp_path):
    p = _make_xlsx(tmp_path, [["", "", "블랙", "L", "10000", ""]])
    parsed = parse_template_rows(str(p))
    fields = {e["field"] for e in parsed.errors}
    assert {"품번", "상품명"} <= fields                    # 누락 필드별로 보고


def test_parse_blank_trailing_row_skipped(tmp_path):
    p = _make_xlsx(tmp_path, [["1001","셔츠","화이트","F","12000","29000"], [None]*6])
    parsed = parse_template_rows(str(p))
    assert len(parsed.rows) == 1 and parsed.errors == []   # 빈 행은 오류 아님
