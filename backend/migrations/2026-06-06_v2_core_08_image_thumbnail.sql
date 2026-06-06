-- ezmerce v2 — _08 이미지 썸네일 경로
-- 서버측 이미지 가공(image_process.py) 산출물 경로 저장용.
-- 프론트가 Storage(product-images)에 올린 원본을 백엔드가 EXIF 보정 + 웹 리사이즈해
-- thumbs/... 경로로 다시 업로드한 뒤, 그 경로를 여기에 기록한다.
-- 원본은 기존 storage_path 그대로 유지. NULL = 미가공(또는 가공 실패) → 프론트는 원본으로 폴백.
-- 멱등(IF NOT EXISTS) — 재실행 안전.

ALTER TABLE product_images ADD COLUMN IF NOT EXISTS thumbnail_path TEXT;

COMMENT ON COLUMN product_images.thumbnail_path IS '서버 가공 웹 썸네일 경로(thumbs/...). NULL=미가공/실패 → 원본(storage_path) 폴백.';
