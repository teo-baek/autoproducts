-- ezmerce v2 — 델타 마이그레이션 12: 고객관리 — 소매↔도매 매칭 취소(예외) + 등급(tier, 잠자는 상태)
-- 모델: 같은 도매관리자(테넌트) 안에서는 모든 소매가 모든 도매와 **기본 연결**된다.
--   관리자는 특정 소매↔도매 매칭을 **취소(예외)**할 수 있다 → 취소된 쌍만 wholesaler_customer_exclusions 에 기록.
--   도매가 보는 고객 = 테넌트 전체 소매 − (그 도매에 대해 취소된 소매). 도매관리자는 테넌트 전체.
--   등급(tier): 1차 화면 제외(주문 데이터 없어 기준 없음). DB 칸은 2차(주문 도입) 자동 등급용으로 보존.
-- 격리는 앱레이어 스코프(service-key 일관 — RLS 우회). 새 테이블은 기본 deny 최소만.
-- 컨벤션: _03(soft delete/부분 unique), _04(audit/set_updated_at), _10(n:m 연결표) 준수.
-- 실행 순서: base → _02 → _03 → _04 → _05 → _06 → _07 → _08 → _09 → _10 → _11 → 본 파일(_12).
-- Supabase SQL Editor 에서 직접 실행(DDL). 멱등 지향(IF NOT EXISTS) — 재실행 안전. (프리런치 — 백필 없음)

-- ── 0) 정리: 이전 '배정(opt-in)' 모델의 wholesaler_customers 테이블 제거(있으면) ──
--   테스트 중 만들어진 배정 데이터 + 인덱스/트리거까지 CASCADE 로 전부 정리.
--   이 마이그레이션의 옛 버전을 한 번이라도 실행했다면 그 잔재를 청소. 안 만들었으면 no-op.
DROP TABLE IF EXISTS public.wholesaler_customers CASCADE;

-- ── 1) 소매↔도매 매칭 취소(예외) 표 — 살아있는 행 = "이 소매는 이 도매와 거래 안 함" ──
--   기본은 전부 연결이라 빈 표 = 모두 연결. 취소한 쌍만 행으로 남는다.
CREATE TABLE IF NOT EXISTS public.wholesaler_customer_exclusions (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wholesaler_id UUID NOT NULL REFERENCES public.wholesalers(id) ON DELETE CASCADE,
    customer_id   UUID NOT NULL REFERENCES public.profiles(id)    ON DELETE CASCADE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by    UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    updated_by    UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    deleted_at    TIMESTAMPTZ
);

-- (도매, 소매) 살아있는 취소 쌍 중복 방지 — 복원(soft delete) 후 재취소 허용(부분 unique, _09/_10 패턴).
CREATE UNIQUE INDEX IF NOT EXISTS wc_exclusions_pair_alive
  ON public.wholesaler_customer_exclusions (wholesaler_id, customer_id) WHERE deleted_at IS NULL;
-- 도매별 취소 소매 조회 / 소매별 취소 도매 조회 가속
CREATE INDEX IF NOT EXISTS idx_wcx_wholesaler ON public.wholesaler_customer_exclusions (wholesaler_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_wcx_customer   ON public.wholesaler_customer_exclusions (customer_id)   WHERE deleted_at IS NULL;

-- ── 2) 등급(tier) — profiles 컬럼. 1차 화면 제외(잠자는 상태). 값 = new|regular, null=신규 ──
ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS tier TEXT CHECK (tier IN ('new', 'regular'));
CREATE INDEX IF NOT EXISTS idx_profiles_tier ON public.profiles (tier) WHERE deleted_at IS NULL;

-- ── 3) audit: updated_at 자동 갱신 트리거 (_04 의 public.set_updated_at() 재사용) ──
DROP TRIGGER IF EXISTS trg_set_updated_at_wc_exclusions ON public.wholesaler_customer_exclusions;
CREATE TRIGGER trg_set_updated_at_wc_exclusions
  BEFORE UPDATE ON public.wholesaler_customer_exclusions FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ── 4) RLS (방어선 최소 — service-key 우회, 기본 deny. 앱레이어가 격리 책임) ──
ALTER TABLE public.wholesaler_customer_exclusions ENABLE ROW LEVEL SECURITY;
-- (정책 미추가 = 기본 deny. 앱은 service_role 로 우회. anon/authenticated 직접 접근 차단)
