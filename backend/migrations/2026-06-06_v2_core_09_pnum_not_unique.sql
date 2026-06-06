-- ezmerce v2 — _09 품번(source_p_number) 유일성 제거
-- ⚠️ 도메인 정정: POS 품번은 신뢰할 수 있는 유일키가 아니다(한 파일 안에서도, 시간이 지나도
--    같은 품번이 서로 다른 상품을 가리킬 수 있음 — 현장 확인). 따라서 (도매업체, 품번) 유일 제약을 제거한다.
-- 상품의 영구 유일 식별자는 platform_code(SEQUENCE 발급, QR 대상) 하나로 남는다(_v2_core 의 전체 UNIQUE 유지).
-- 조회 성능을 위해 같은 컬럼에 '비유일' 부분 인덱스를 둔다(품번→상품 lookup, 이미지 매칭용).
-- 멱등(IF EXISTS/IF NOT EXISTS) — 재실행 안전.

-- 1) 부분 유니크 인덱스 제거(같은 품번 재등록 차단을 풀어, 동일 품번의 서로 다른 상품 허용)
DROP INDEX IF EXISTS public.products_wholesaler_source_alive;

-- 2) 혹시 남아있을 수 있는 옛 테이블 유니크 제약도 안전망으로 제거
ALTER TABLE public.products DROP CONSTRAINT IF EXISTS products_wholesaler_id_source_p_number_key;

-- 3) 비유일 lookup 인덱스(살아있는 행만) — products_pnum_map / 이미지 자동매칭 / 수동매칭 조회 가속
CREATE INDEX IF NOT EXISTS products_wholesaler_source_lookup
  ON public.products (wholesaler_id, source_p_number) WHERE deleted_at IS NULL;

COMMENT ON INDEX public.products_wholesaler_source_lookup IS
  '품번 lookup용 비유일 인덱스. 품번은 유일키 아님(중복 허용) — 영구 식별자는 platform_code.';
