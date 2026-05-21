import qrcode
from PIL import Image
import io
import zipfile
import streamlit as st

class QRGenerator:
    def __init__(self, base_url=None):
        if base_url is None:
            try:
                self.base_url = st.secrets.get("BASE_URL", "http://localhost:8501/cue_sheet")
            except Exception:
                self.base_url = "http://localhost:8501/cue_sheet"
        else:
            self.base_url = base_url

    def generate_qr_image(self, store_id, p_number):
        """특정 상품에 대한 QR 코드 이미지를 BytesIO로 생성하여 반환합니다."""
        url = f"{self.base_url}?store_id={store_id}&search={p_number}"
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=2,
        )
        qr.add_data(url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        
        # 엑셀 삽입 및 보기 좋은 사이즈로 리사이징
        img = img.resize((150, 150), Image.Resampling.LANCZOS)
        
        img_buffer = io.BytesIO()
        img.save(img_buffer, format="PNG")
        img_buffer.seek(0)
        
        return img_buffer

    def create_qr_zip(self, parsed_rows_data, store_id):
        """생성된 모든 QR 코드를 모아 하나의 ZIP 파일 버퍼로 반환합니다."""
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
            for row in parsed_rows_data:
                p_number = str(row["p_number"]).strip()
                # .0 제거 (소수점 정리)
                if p_number.endswith(".0"):
                    p_number = p_number[:-2]
                
                # 품번 누락 시 스킵
                if not p_number or p_number.lower() == "nan":
                    continue
                
                qr_buffer = self.generate_qr_image(store_id, p_number)
                # ZIP 내 파일명: 상품명_품번.png
                safe_item_name = str(row["item_name"]).replace("/", "_").replace("\\", "_")
                filename = f"{safe_item_name}_{p_number}.png"
                
                zip_file.writestr(filename, qr_buffer.getvalue())
                
        zip_buffer.seek(0)
        return zip_buffer
