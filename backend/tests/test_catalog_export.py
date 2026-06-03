import io
import openpyxl
from fastapi.testclient import TestClient
from app.main import app
from app.core.auth import get_current_user
from app.schemas.auth import CurrentUser
from app.services.excel_export import catalog_xlsx_bytes
import app.routers.catalog as catalog_mod


def test_catalog_xlsx_bytes_has_qr_header():
    data = catalog_xlsx_bytes(
        [{"platform_code": "EZM-000001", "item_name": "셔츠", "price": 12000}],
        base_url="https://x",
    )
    wb = openpyxl.load_workbook(io.BytesIO(data))
    ws = wb.active
    assert [c.value for c in ws[1]][-1] == "QR"        # 최우측 열 QR (FR-3.2)
    assert ws.cell(row=2, column=1).value == "EZM-000001"


def test_export_route_returns_xlsx_with_role_shaped_price(monkeypatch):
    rows = [{
        "platform_code": "EZM-000001", "item_name": "셔츠",
        "product_skus": [{"color": "화이트", "size": "F",
                          "wholesale_price": 12000, "retail_price": 29000, "wholesaler_id": "org-9"}],
    }]
    monkeypatch.setattr(catalog_mod, "_query_catalog_rows", lambda sb, limit, cursor=None: rows)
    monkeypatch.setattr(catalog_mod, "get_supabase", lambda: object())
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id="u", role="retail_seller", status="approved", seller_type="independent")
    try:
        res = TestClient(app).get("/catalog/export.xlsx")
        assert res.status_code == 200
        assert "spreadsheet" in res.headers["content-type"]
        assert "attachment" in res.headers["content-disposition"]
        wb = openpyxl.load_workbook(io.BytesIO(res.content))
        ws = wb.active
        assert [c.value for c in ws[1]][-1] == "QR"
        # independent 셀러 → 도매가 노출 (FR-5.2)
        assert ws.cell(row=2, column=3).value == 12000
    finally:
        app.dependency_overrides.clear()


def test_export_route_blocks_unapproved(monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id="u", role="retail_seller", status="pending", seller_type="independent")
    try:
        res = TestClient(app).get("/catalog/export.xlsx")
        assert res.status_code == 403   # 미승인 → 차단 (FR-5.1)
    finally:
        app.dependency_overrides.clear()
