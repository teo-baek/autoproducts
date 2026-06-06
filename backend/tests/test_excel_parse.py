import openpyxl
from app.services.excel_parse import parse_template_rows, TEMPLATE_COLUMNS

def _make_xlsx(tmp_path, rows):
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(TEMPLATE_COLUMNS)
    for r in rows: ws.append(r)
    p = tmp_path / "t.xlsx"; wb.save(p); return p

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
