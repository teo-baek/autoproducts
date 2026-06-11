-- ezmerce v2 — 델타 마이그레이션 10: 도매관리자(도매연합) 멀티테넌트 1차 재편
-- 테넌트 엔티티(wholesale_managers) + 도매상 소속 연결표(manager_wholesalers)
--   + 셀러/admin → 관리자 연계(profiles.manager_id).
-- 격리는 앱레이어 스코프(service-key 일관). RLS 전환은 범위 밖 — 새 테이블은 기본 deny 최소만.
-- 컨벤션: _03(soft delete/부분 unique/soft-cascade), _04(audit/set_updated_at 트리거) 준수.
-- 실행 순서: base → _02 → _03 → _04 → _05 → _06 → _07 → _08 → _09 → 본 파일(_10).
-- Supabase SQL Editor 에서 직접 실행(DDL). 멱등 지향(IF NOT EXISTS) — 재실행 안전.
-- ⚠️ 1회 실행 시 §8 backfill 포함(기존 도매/셀러를 LALAS 에 묶음) — 누락 시 카탈로그가 빈 결과로 회귀.

-- ── 1) 테넌트 엔티티 ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.wholesale_managers (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    biz_number  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by  UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    updated_by  UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    deleted_at  TIMESTAMPTZ
);

-- ── 2) 도매상 ↔ 관리자 소속 연결표 (단일 manager_id 칸 금지 — n:m forward-compat) ──
CREATE TABLE IF NOT EXISTS public.manager_wholesalers (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    manager_id    UUID NOT NULL REFERENCES public.wholesale_managers(id) ON DELETE CASCADE,
    wholesaler_id UUID NOT NULL REFERENCES public.wholesalers(id)        ON DELETE CASCADE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by    UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    updated_by    UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    deleted_at    TIMESTAMPTZ
);

-- 1:n 강제 — 1차엔 도매상당 (살아있는) 소속 1행만. 같은 도매상 중복 소속 차단.
-- n:m 로 풀 때 이 부분 unique(wid_alive) 만 드롭하면 됨(스키마 변경 최소). _09 의 부분 unique 패턴과 동형.
CREATE UNIQUE INDEX IF NOT EXISTS manager_wholesalers_wid_alive
  ON public.manager_wholesalers (wholesaler_id) WHERE deleted_at IS NULL;
-- (manager, wholesaler) 살아있는 쌍 중복 방지
CREATE UNIQUE INDEX IF NOT EXISTS manager_wholesalers_pair_alive
  ON public.manager_wholesalers (manager_id, wholesaler_id) WHERE deleted_at IS NULL;
-- 관리자별 소속 도매 조회 가속
CREATE INDEX IF NOT EXISTS idx_manager_wholesalers_manager
  ON public.manager_wholesalers (manager_id) WHERE deleted_at IS NULL;

-- ── 3) 셀러/admin → 관리자 연계 (단일 FK; 셀러는 관리자 1개 연계, admin 은 자기 테넌트) ──
ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS manager_id UUID REFERENCES public.wholesale_managers(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_profiles_manager ON public.profiles (manager_id);

-- ── 4) audit: updated_at 자동 갱신 트리거 (_04 의 public.set_updated_at() 재사용) ──
DROP TRIGGER IF EXISTS trg_set_updated_at_wholesale_managers ON public.wholesale_managers;
CREATE TRIGGER trg_set_updated_at_wholesale_managers
  BEFORE UPDATE ON public.wholesale_managers FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
DROP TRIGGER IF EXISTS trg_set_updated_at_manager_wholesalers ON public.manager_wholesalers;
CREATE TRIGGER trg_set_updated_at_manager_wholesalers
  BEFORE UPDATE ON public.manager_wholesalers FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ── 5) soft-cascade: 테넌트 soft-delete 시 소속 연결행 전파 (_03 패턴) ──
CREATE OR REPLACE FUNCTION public.soft_cascade_manager() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.deleted_at IS NOT NULL AND OLD.deleted_at IS NULL THEN
    UPDATE public.manager_wholesalers SET deleted_at = NEW.deleted_at
      WHERE manager_id = NEW.id AND deleted_at IS NULL;
  END IF;
  RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS trg_soft_cascade_manager ON public.wholesale_managers;
CREATE TRIGGER trg_soft_cascade_manager
  AFTER UPDATE OF deleted_at ON public.wholesale_managers
  FOR EACH ROW EXECUTE FUNCTION public.soft_cascade_manager();

-- ── 6) RLS (방어선 최소 — service-key 우회, 기본 deny. RLS 전환은 범위 밖) ──
ALTER TABLE public.wholesale_managers  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.manager_wholesalers ENABLE ROW LEVEL SECURITY;
-- (정책 미추가 = 기본 deny. 앱은 service_role 로 우회. anon/authenticated 직접 접근 차단)

-- ── 7) LALAS 시드 + 기존 단일 admin 연결 ──
--   대표 admin = 기존 단일 admin 계정(이미 존재). id = f50945ce-0fec-4241-96ed-29e3dc97bade
--   고정 시드 UUID(유효 hex): 1a1a0000-0000-0000-0000-00000000a1a5
INSERT INTO public.wholesale_managers (id, name, created_by)
VALUES (
  '1a1a0000-0000-0000-0000-00000000a1a5'::uuid,
  'LALAS',
  'f50945ce-0fec-4241-96ed-29e3dc97bade'
)
ON CONFLICT (id) DO NOTHING;

-- 대표 admin → LALAS 테넌트 매핑
UPDATE public.profiles
  SET manager_id = '1a1a0000-0000-0000-0000-00000000a1a5'::uuid
  WHERE id = 'f50945ce-0fec-4241-96ed-29e3dc97bade';

-- ── 8) backfill: 기존 도매상 전부 LALAS 소속으로, 기존 셀러 전부 LALAS 연계로 ──
--   (1차 회귀 안전 핵심 — 기존 '전체 노출' 결과를 스코프 도입 후에도 동일하게 유지)
INSERT INTO public.manager_wholesalers (manager_id, wholesaler_id, created_by)
SELECT '1a1a0000-0000-0000-0000-00000000a1a5'::uuid, w.id,
       'f50945ce-0fec-4241-96ed-29e3dc97bade'
  FROM public.wholesalers w
 WHERE w.deleted_at IS NULL
   AND NOT EXISTS (
     SELECT 1 FROM public.manager_wholesalers mw
      WHERE mw.wholesaler_id = w.id AND mw.deleted_at IS NULL
   );

UPDATE public.profiles
   SET manager_id = '1a1a0000-0000-0000-0000-00000000a1a5'::uuid
 WHERE role = 'retail_seller' AND deleted_at IS NULL AND manager_id IS NULL;
