import urllib.request
import io
import re
from PIL import Image as PILImage, ImageOps
from concurrent.futures import ThreadPoolExecutor

class ImageProcessor:
    def __init__(self, max_workers=24):
        self.max_workers = max_workers

    def download_thumbnail_image(self, file_id):
        """구글 드라이브 파일 ID를 이용해 썸네일 또는 원본 이미지를 다운로드하는 함수"""
        if not file_id:
            return None
            
        # 1차 시도: UC (다이렉트) 엔드포인트
        uc_url = f"https://drive.google.com/uc?id={file_id}"
        try:
            req = urllib.request.Request(uc_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.read()
        except:
            pass
            
        # 2차 시도: 썸네일 엔드포인트
        thumb_url = f"https://drive.google.com/thumbnail?id={file_id}&sz=w300"
        try:
            req = urllib.request.Request(thumb_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            with urllib.request.urlopen(req, timeout=4) as response:
                return response.read()
        except:
            return None

    def process_single_row_image(self, p_num, file_list_map, folder_id):
        """단일 행 이미지 다운로드 및 EXIF 보정 후 BytesIO 객체로 반환"""
        if not p_num:
            return "NONE"
        
        # 판다스가 실수로 붙인 소수점 .0을 완벽히 도려내 정형화
        clean_p_num = re.sub(r'\.0$', '', str(p_num).strip())
        
        # 스캔된 파일 리스트에서 ID 획득 시도
        file_id = file_list_map.get(clean_p_num)
        
        img_data = None
        if file_id:
            img_data = self.download_thumbnail_image(file_id)
            
        # 주소 스캔 레이어 (Fallback)
        if not img_data:
            img_extensions = ['jpg', 'jpeg', 'png', 'JPG', 'JPEG', 'PNG']
            for ext in img_extensions:
                fallback_url = f"https://drive.google.com/thumbnail?authuser=0&sz=w300&id={folder_id}&filename={clean_p_num}.{ext}"
                try:
                    req = urllib.request.Request(fallback_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
                    with urllib.request.urlopen(req, timeout=2) as response:
                        img_data = response.read()
                        if img_data:
                            break
                except:
                    continue
                    
        if img_data:
            try:
                pil_img = PILImage.open(io.BytesIO(img_data))
                pil_img = ImageOps.exif_transpose(pil_img)  # EXIF 방향 메타데이터 적용
                pil_img = pil_img.convert("RGB")
                pil_img.thumbnail((150, 200)) # 사용자가 설정한 크기로 유지
                
                img_buffer = io.BytesIO()
                pil_img.save(img_buffer, format="JPEG")
                img_buffer.seek(0)
                return img_buffer
            except:
                return "ERROR"
                
        return "NONE"

    def process_images_concurrently(self, parsed_rows_data, file_list_map, folder_id, progress_callback=None):
        """중복 다운로드를 방지(캐싱)하며 스레드풀을 이용하여 이미지를 비동기 동시 처리"""
        
        # 1. 고유한 품번만 추출
        unique_p_nums = list(set(
            re.sub(r'\.0$', '', str(row["p_number"]).strip()) 
            for row in parsed_rows_data if row["p_number"]
        ))
        
        # 2. 고유 품번에 대해서만 병렬 다운로드 실행
        cache = {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self.process_single_row_image, p_num, file_list_map, folder_id): p_num
                for p_num in unique_p_nums
            }
            
            for f_idx, future in enumerate(futures):
                p_num = futures[future]
                result_buffer = future.result()
                
                # 재사용을 위해 바이트 데이터(raw bytes)를 캐시에 저장
                if isinstance(result_buffer, io.BytesIO):
                    cache[p_num] = result_buffer.getvalue()
                else:
                    cache[p_num] = result_buffer
                    
                if progress_callback:
                    # Streamlit progress bar 업데이트 콜백 호출
                    progress_callback((f_idx + 1) / len(futures))
                    
        # 3. 원래 엑셀의 행 순서대로 매핑 (BytesIO 독립 복제)
        image_results = []
        for row in parsed_rows_data:
            p_num_clean = re.sub(r'\.0$', '', str(row["p_number"]).strip())
            cached_val = cache.get(p_num_clean, "NONE")
            
            if isinstance(cached_val, bytes):
                # 엑셀 셀마다 독립적인 파일 포인터를 가져야 하므로 새로 생성
                new_buf = io.BytesIO(cached_val)
                image_results.append(new_buf)
            else:
                image_results.append(cached_val)
                
        return image_results

    def compress_and_resize_image(self, file_bytes, max_width=600, quality=75):
        """업로드된 이미지 바이트를 받아 리사이징 및 압축(JPEG)하여 bytes로 반환합니다."""
        try:
            pil_img = PILImage.open(io.BytesIO(file_bytes))
            pil_img = ImageOps.exif_transpose(pil_img)  # EXIF 방향 메타데이터 적용
            pil_img = pil_img.convert("RGB")
            
            # 비율 유지하며 가로 최대 길이에 맞춤
            if pil_img.width > max_width:
                w_percent = (max_width / float(pil_img.width))
                h_size = int((float(pil_img.height) * float(w_percent)))
                pil_img = pil_img.resize((max_width, h_size), PILImage.LANCZOS)
                
            img_buffer = io.BytesIO()
            pil_img.save(img_buffer, format="JPEG", quality=quality, optimize=True)
            return img_buffer.getvalue()
        except Exception as e:
            print(f"이미지 압축 오류: {e}")
            return None

    def download_and_compress(self, file_id, max_width=600, quality=75):
        """구글 드라이브 파일 ID로 이미지를 다운로드하고 즉시 압축하여 bytes 반환.
        Supabase Storage 업로드 직전에 사용하는 마이그레이션 전용 헬퍼."""
        raw_bytes = self.download_thumbnail_image(file_id)
        if not raw_bytes:
            return None
        return self.compress_and_resize_image(raw_bytes, max_width=max_width, quality=quality)


