import openpyxl
from app.services.excel_export import build_catalog_xlsx

def test_export_has_qr_column_last(tmp_path):
    items = [{"platform_code": "EZM-000001", "item_name": "린넨셔츠", "price": 12000}]
    out = tmp_path / "out.xlsx"
    build_catalog_xlsx(items, str(out), base_url="https://x")
    wb = openpyxl.load_workbook(out)
    ws = wb.active
    headers = [c.value for c in ws[1]]
    assert headers[-1] == "QR"            # 최우측 열이 QR (FR-3.2)
    assert ws.cell(row=2, column=1).value == "EZM-000001"
    assert len(ws._images) == 1           # QR 이미지 1개 삽입됨
