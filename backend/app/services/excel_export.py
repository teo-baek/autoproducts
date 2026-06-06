import io
import openpyxl
from openpyxl.drawing.image import Image as XLImage
from app.services.qr import qr_target_url, generate_qr_png

HEADERS = ["품번", "상품명", "가격", "QR"]


def _build_workbook(items: list[dict], base_url: str):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(HEADERS)
    for i, it in enumerate(items, start=2):
        ws.cell(row=i, column=1, value=it["platform_code"])
        ws.cell(row=i, column=2, value=it["item_name"])
        ws.cell(row=i, column=3, value=it.get("price"))
        png = generate_qr_png(qr_target_url(it["platform_code"], base_url))
        img = XLImage(io.BytesIO(png)); img.width = img.height = 64
        ws.add_image(img, f"D{i}")        # 최우측 열(QR)에 삽입
        ws.row_dimensions[i].height = 50
    return wb


def build_catalog_xlsx(items: list[dict], out_path: str, base_url: str) -> str:
    _build_workbook(items, base_url).save(out_path)
    return out_path


def catalog_xlsx_bytes(items: list[dict], base_url: str) -> bytes:
    """파일 경로 없이 메모리(BytesIO)로 xlsx 바이트 생성 — HTTP 다운로드 응답용."""
    buf = io.BytesIO()
    _build_workbook(items, base_url).save(buf)
    return buf.getvalue()


# ── 도매 본인 상품 관리 내보내기(내부용 — QR/가격셰이핑 없는 원장) ──────────────
PRODUCT_HEADERS = ["품번", "플랫폼코드", "상품명", "분류", "색상", "사이즈",
                   "도매가", "판매가", "재고", "혼용률"]


def products_xlsx_bytes(products: list[dict]) -> bytes:
    """도매 본인 상품 목록 → SKU 단위 1행 엑셀. 관리뷰(도매가+판매가) 그대로."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "상품목록"
    ws.append(PRODUCT_HEADERS)
    for p in products:
        skus = p.get("skus") or [{}]
        for s in skus:
            ws.append([
                p.get("source_p_number"), p.get("platform_code"), p.get("item_name"),
                p.get("category"), s.get("color"), s.get("size"),
                s.get("wholesale_price"), s.get("retail_price"), s.get("stock"),
                p.get("fabric_composition"),
            ])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
