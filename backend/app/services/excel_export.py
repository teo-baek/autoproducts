import io
import openpyxl
from openpyxl.drawing.image import Image as XLImage
from app.services.qr import qr_target_url, generate_qr_png

HEADERS = ["품번", "상품명", "가격", "QR"]


def build_catalog_xlsx(items: list[dict], out_path: str, base_url: str) -> str:
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
    wb.save(out_path)
    return out_path
