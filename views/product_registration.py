import streamlit as st
from services.database import DatabaseConnector
from services.excel import ExcelGenerator
from services.parser import ProductParser
from services.image import ImageProcessor
from services.connector import DriveConnector
from services.qr_generator import QRGenerator
import pandas as pd
import uuid
import time
import re
import zipfile
import io
from datetime import datetime
"""
1초 간편 덤프 (드래그 매칭)
"""

def render_upload_fast():
    """
    도매상이 엑셀 파일과 여러 장의 상품 사진을 한 번에 업로드하여
    상품 데이터를 일괄 등록하고 자동으로 사진을 매핑해주는 UI 컴포넌트입니다.
    
    1. 엑셀 파일이 있으면 파싱하여 텍스트 정보(가격, 사이즈, 컬러 등)를 DB에 우선 등록합니다.
    2. 사진 덤프가 있으면 각각을 압축 후 Supabase Storage에 업로드합니다.
    3. 사진 파일명(확장자 제외)과 엑셀의 품번이 일치하면 자동으로 매핑(Upsert)됩니다.
    4. 매핑되지 않은 사진은 '[신상] 품번' 형태의 임시(가등록) 상품으로 저장되어 추후 '짝 맞추기' 탭에서 처리됩니다.
    """
    store_id = st.session_state.get("store_id", "test_store_01")
    
    st.subheader("⚡ 다중 파일 일괄 업로드")
    st.markdown("포스기 엑셀과 사진 파일들을 이 곳에 한 번에 던져 넣으세요. 사진 이름이 품번과 같다면 자동 매칭됩니다.")
    
    parser = ProductParser()
    image_processor = ImageProcessor()
    db_connector = DatabaseConnector()
    
    col1, col2 = st.columns(2)
    with col1:
        uploaded_excel = st.file_uploader("엑셀 파일 (정보만 등록)", type=["csv", "xlsx", "xls"], key="up_excel_fast")
    with col2:
        uploaded_images = st.file_uploader("사진 갤러리 덤프 (사진만 등록)", type=["jpg", "png", "jpeg"], accept_multiple_files=True, key="up_images_fast")
        
    if st.button("🚀 즉시 업로드 및 자동 매칭 시작", type="primary", width="stretch", key="btn_upload_fast"):
        if not uploaded_excel and not uploaded_images:
            st.warning("엑셀 파일이나 사진 중 최소 하나를 업로드해 주세요.")
        else:
            with st.spinner("클라우드 댐으로 데이터를 마이그레이션 중입니다..."):
                # 1. 엑셀 처리: 텍스트 정보만 먼저 카탈로그에 동기화
                parsed_rows_data = []
                if uploaded_excel:
                    if uploaded_excel.name.endswith('.csv'): df_raw = pd.read_csv(uploaded_excel, encoding='utf-8')
                    elif uploaded_excel.name.endswith('.xls'): df_raw = pd.read_excel(uploaded_excel, engine='xlrd')
                    else: df_raw = pd.read_excel(uploaded_excel)
                    
                    parsed_rows_data = parser.parse_dataframe(df_raw)
                    db_success, db_msg = db_connector.sync_products_to_db(parsed_rows_data, {}, store_id)
                    if db_success: st.success(f"📝 {len(parsed_rows_data)}개의 텍스트 상품 정보가 등록/업데이트 되었습니다.")
                    else: st.error(db_msg)

                # 2. 이미지 처리 및 자동 매칭: 사진 파일명을 기반으로 품번을 유추하여 URL 매핑
                if uploaded_images:
                    matched_count = 0
                    
                    for img_file in uploaded_images:
                        comp_bytes = image_processor.compress_and_resize_image(img_file.getvalue())
                        if not comp_bytes: continue
                        
                        filename_clean = re.sub(r'\.[a-zA-Z0-9]+$', '', img_file.name)
                        p_number_guess = re.sub(r'\.0$', '', filename_clean.strip())
                        
                        public_url = db_connector.upload_product_image(comp_bytes, store_id, p_number_guess)
                        if public_url:
                            # 텍스트 정보가 없어도 일단 이미지가 올라가면 임시 상품(가등록) 레코드를 생성 (Upsert)
                            success, _ = db_connector.insert_single_product(
                                store_id=store_id, p_number=p_number_guess, item_name=f"[신상] {p_number_guess}",
                                image_url=public_url, wholesale="0", retail="0", color="", size=""
                            )
                            if success: matched_count += 1
                            
                    st.success(f"📸 {matched_count}개의 갤러리 덤프 사진이 압축 후 자동 매핑되었습니다!")
                    st.info("이름이 품번과 다른 사진들이 있다면 사이드바의 [🧩 미매핑 짝 맞추기]에서 수동 매치해 주세요.")


"""
즉석 촬영 및 직접 등록
"""

def render_upload_cam():
    store_id = st.session_state.get("store_id", "test_store_01")
    
    st.subheader("📸 모바일 카메라 실시간 촬영 등록")
    st.markdown("물류 창고나 매장에서 스마트폰으로 신상을 바로 찍어 큐시트에 올리세요!")
    
    image_processor = ImageProcessor()
    db_connector = DatabaseConnector()
    
    c_p_number = st.text_input("품번 (필수)", key="cam_pnum")
    c_item_name = st.text_input("상품명", placeholder="예: 단가라 티셔츠", key="cam_name")
    col_c1, col_c2 = st.columns(2)
    with col_c1: c_whole = st.text_input("도매가", value="0", key="cam_whole")
    with col_c2: c_ret = st.text_input("판매가", value="0", key="cam_ret")
    
    c_image = st.camera_input("상품 사진 찍기")
    
    if st.button("즉석 카탈로그 등록하기", type="primary", width="stretch", key="btn_cam_upload"):
        if not c_p_number: st.warning("품번을 입력해 주세요.")
        elif not c_image: st.warning("사진을 촬영해 주세요.")
        else:
            with st.spinner("이미지 모바일 압축 최적화 및 클라우드 전송 중..."):
                comp_bytes = image_processor.compress_and_resize_image(c_image.getvalue())
                pub_url = db_connector.upload_product_image(comp_bytes, store_id, c_p_number)
                if pub_url:
                    success, msg = db_connector.insert_single_product(
                        store_id, c_p_number, c_item_name, pub_url, c_whole, c_ret, "", ""
                    )
                    if success: st.success("🎉 실시간으로 내 모바일 카탈로그에 반영되었습니다!")
                    else: st.error(msg)
                else:
                    st.error("이미지 업로드에 실패했습니다.")


"""
비동기 짝 맞추기 (Tinder 매칭)
"""

def render_match_tool():
    store_id = st.session_state.get("store_id", "test_store_01")
    
    st.subheader("🧩 미매핑 상품 1초 짝 맞추기")
    st.markdown("사진 없이 등록된 엑셀 상품명과, 품번 없이 업로드된 덤프 사진들을 클릭만으로 매치합니다.")
    
    db_connector = DatabaseConnector()
    
    if st.button("🔄 실시간 매칭 대기열 새로고침", width="stretch", key="btn_refresh_match"):
        pass
        
    if db_connector.supabase:
        try:
            # 1. 엑셀로 올라온 정보 (사진이 없는 품번들)
            res_no_img = db_connector.supabase.table("products").select("p_number, item_name").eq("store_id", store_id).is_("image_url", "null").execute()
            res_no_img2 = db_connector.supabase.table("products").select("p_number, item_name").eq("store_id", store_id).eq("image_url", "").execute()
            missing_img_products = (res_no_img.data or []) + (res_no_img2.data or [])
            
            # 2. 갤러리 덤프로 올라온 정보 (상품명이 [신상]인 임시 파일명 가등록본)
            res_temp = db_connector.supabase.table("products").select("p_number, image_url").eq("store_id", store_id).like("item_name", "[신상]%").execute()
            temp_photos = res_temp.data or []
            
            if not temp_photos and not missing_img_products:
                st.success("현재 짝을 맞춰야 할 대기열이 없습니다! 완벽합니다. 🎉")
            else:
                col_p1, col_p2 = st.columns(2)
                with col_p1:
                    st.markdown("##### 📸 정보가 없는 덤프 사진")
                    if temp_photos:
                        selected_photo = st.selectbox("업로드된 사진", temp_photos, format_func=lambda x: f"임시 파일명: {x['p_number']}")
                        if selected_photo:
                            st.image(selected_photo['image_url'], width=150)
                    else:
                        st.write("대기 중인 미매핑 사진이 없습니다.")
                        selected_photo = None
                        
                with col_p2:
                    st.markdown("##### 📝 사진이 없는 엑셀 품번")
                    if missing_img_products:
                        selected_prod = st.selectbox("품번 (상품명)", missing_img_products, format_func=lambda x: f"[{x['p_number']}] {x['item_name']}")
                    else:
                        st.write("사진이 누락된 엑셀 품번이 없습니다.")
                        selected_prod = None
                        
                if selected_photo and selected_prod:
                    if st.button("💖 단 1초만에 짝 맞추기", type="primary", width="stretch", key="btn_do_match"):
                        # 진짜 품번 레코드의 이미지를 임시 사진 URL로 업데이트
                        db_connector.update_product_image(store_id, selected_prod['p_number'], selected_photo['image_url'])
                        # 매칭이 끝난 스켈레톤 임시 레코드는 삭제
                        db_connector.supabase.table("products").delete().eq("store_id", store_id).eq("p_number", selected_photo['p_number']).execute()
                        
                        st.success("✨ 매칭 성공! 완벽한 상품 정보가 카탈로그에 반영되었습니다.")
                        st.rerun()
        except Exception as e:
            st.error(f"대기열 데이터 조회 중 오류가 발생했습니다: {e}")
    else:
        st.warning("데이터베이스 연동이 필요합니다.")


"""
구글 드라이브 통합 변환 (기존)
"""


def render_upload_legacy():
    store_id = st.session_state.get("store_id", "test_store_01")
    saved_drive_url = st.session_state.get("drive_folder_url", "")
    
    st.subheader("📂 기존 구글 드라이브 일괄 통합 모드")
    st.markdown("포스기 엑셀과 구글 드라이브 사진 폴더 URL을 결합해 완벽한 방송용 엑셀과 QR 라벨팩을 다운로드합니다.")
    
    parser = ProductParser()
    connector = DriveConnector()
    image_processor = ImageProcessor()
    excel_generator = ExcelGenerator()
    db_connector = DatabaseConnector()
    qr_generator = QRGenerator()
    
    uploaded_file = st.file_uploader("포스기 엑셀 파일 (XLSX, CSV)", type=["csv", "xlsx", "xls"], key="up_legacy")
    folder_url = st.text_input("구글 드라이브 폴더 주소 (URL)", value=saved_drive_url)
    
    if st.button("엑셀 + QR 통합 변환", width="stretch", type="primary", key="btn_legacy_conv"):
        if uploaded_file is not None and folder_url:
            try:
                folder_id = parser.extract_folder_id(folder_url)
                
                if uploaded_file.name.endswith('.csv'): df_raw = pd.read_csv(uploaded_file, encoding='utf-8')
                elif uploaded_file.name.endswith('.xls'): df_raw = pd.read_excel(uploaded_file, engine='xlrd')
                else: df_raw = pd.read_excel(uploaded_file)

                st.info("📊 구글 드라이브 스캔 중...")
                file_list_map = connector.get_file_list(folder_id)
                parsed_rows_data = parser.parse_dataframe(df_raw)

                progress_bar = st.progress(0)
                image_results = image_processor.process_images_concurrently(
                    parsed_rows_data, file_list_map, folder_id, progress_callback=lambda p: progress_bar.progress(p)
                )

                st.info("🔄 구글 드라이브 이미지를 플랫폼 스토리지로 이전 중...")
                mig_bar = st.progress(0)
                supabase_url_map = {}
                unique_file_items = list(file_list_map.items())  # [(p_num, file_id), ...]
                
                for idx, (p_num, file_id) in enumerate(unique_file_items):
                    img_bytes = image_processor.download_and_compress(file_id)
                    if img_bytes:
                        url = db_connector.upload_product_image(img_bytes, store_id, p_num)
                        if url:
                            supabase_url_map[p_num] = url
                    mig_bar.progress((idx + 1) / max(len(unique_file_items), 1))
                
                st.success(f"✅ {len(supabase_url_map)}개 이미지가 플랫폼 스토리지로 이전 완료!")
                
                st.info("☁️ 클라우드 카탈로그 동기화 중...")
                db_success, db_msg = db_connector.sync_products_to_db(
                    parsed_rows_data, file_list_map, store_id, supabase_url_map=supabase_url_map
                )
                
                st.info("📷 오프라인 QR 라벨 생성 중...")
                qr_results, qr_cache = [], {}
                for row in parsed_rows_data:
                    p_n = re.sub(r'\.0$', '', str(row["p_number"]).strip())
                    if not p_n or p_n.lower() == "nan": qr_results.append(None)
                    else:
                        if p_n in qr_cache: qr_results.append(io.BytesIO(qr_cache[p_n]))
                        else:
                            buf = qr_generator.generate_qr_image(store_id, p_n)
                            qr_cache[p_n] = buf.getvalue()
                            qr_results.append(buf)

                excel_data = excel_generator.generate_excel(parsed_rows_data, image_results, qr_results)
                final_excel_name = f"{datetime.now().strftime('%Y-%m-%d')}_방송제품목록.xlsx"

                st.info("📦 통합 압축(ZIP) 패키징 중...")
                master_zip_buffer = io.BytesIO()
                with zipfile.ZipFile(master_zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as master_zip:
                    master_zip.writestr(final_excel_name, excel_data.getvalue())
                    for p_n, q_b in qr_cache.items():
                        i_name = next((str(r["item_name"]) for r in parsed_rows_data if re.sub(r'\.0$', '', str(r["p_number"]).strip()) == p_n), "상품")
                        s_name = i_name.replace("/", "_").replace("\\", "_")
                        master_zip.writestr(f"QR라벨/{s_name}_{p_n}.png", q_b)

                master_zip_buffer.seek(0)
                st.balloons()
                st.success("🎉 변환 완료!")
                
                st.download_button(
                    label="📦 엑셀 + QR 통합 압축파일 다운로드",
                    data=master_zip_buffer,
                    file_name=f"{datetime.now().strftime('%Y-%m-%d')}_AutoProducts_통합팩.zip",
                    mime="application/zip",
                    width="stretch"
                )

            except Exception as e:
                st.error(f"에러 발생: {e}")
        else:
            st.warning("포스기 엑셀과 구글 드라이브 URL을 모두 입력해주세요.")


def show():
    st.title('📤 스마트 상품 등록 센터')
    st.markdown('어떤 방식으로 상품을 등록하시겠습니까?')
    
    tab1, tab2, tab3, tab4 = st.tabs(['🏢 1초 간편 덤프', '📸 실시간 촬영 등록', '📂 구글 드라이브 일괄 변환', '🧩 미매핑 짝 맞추기'])
    
    with tab1: render_upload_fast()
    with tab2: render_upload_cam()
    with tab3: render_upload_legacy()
    with tab4: render_match_tool()
