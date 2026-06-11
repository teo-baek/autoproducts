-- ezmerce v2 — 델타 마이그레이션 11: 멀티테넌트 승인 풀 — 관리자별 거절(패스) 기록
-- 모델: 가입 신청은 공유 대기 풀(manager_id NULL)에 떠서 모든 도매관리자에게 보임.
--   · 승인(claim) = status=approved + manager_id 세팅 → 다른 관리자 대기 풀에서 사라짐.
--   · 거절 = "이 관리자가 이 신청자를 패스" — 전역 상태 안 바꾸고 본 테이블에 기록.
--     → 거절한 관리자 목록에서만 빠지고, 다른 관리자에겐 계속 pending 으로 보임.
-- 실행 순서: _10 다음. Supabase SQL Editor 직접 실행(DDL). 멱등 지향.

CREATE TABLE IF NOT EXISTS public.manager_rejections (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    manager_id  UUID NOT NULL REFERENCES public.wholesale_managers(id) ON DELETE CASCADE,
    profile_id  UUID NOT NULL REFERENCES public.profiles(id)            ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by  UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    updated_by  UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    deleted_at  TIMESTAMPTZ
);

-- 관리자별 신청자 거절은 (관리자, 신청자) 당 살아있는 1행(멱등 재거절 방지)
CREATE UNIQUE INDEX IF NOT EXISTS manager_rejections_pair_alive
  ON public.manager_rejections (manager_id, profile_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_manager_rejections_manager
  ON public.manager_rejections (manager_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_manager_rejections_profile
  ON public.manager_rejections (profile_id) WHERE deleted_at IS NULL;

-- updated_at 트리거(_04 의 set_updated_at 재사용)
DROP TRIGGER IF EXISTS trg_set_updated_at_manager_rejections ON public.manager_rejections;
CREATE TRIGGER trg_set_updated_at_manager_rejections
  BEFORE UPDATE ON public.manager_rejections FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- soft-cascade: 테넌트 soft-delete 시 소속 연결행 + 거절기록 전파 (_10 soft_cascade_manager 확장)
CREATE OR REPLACE FUNCTION public.soft_cascade_manager() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.deleted_at IS NOT NULL AND OLD.deleted_at IS NULL THEN
    UPDATE public.manager_wholesalers SET deleted_at = NEW.deleted_at
      WHERE manager_id = NEW.id AND deleted_at IS NULL;
    UPDATE public.manager_rejections  SET deleted_at = NEW.deleted_at
      WHERE manager_id = NEW.id AND deleted_at IS NULL;
  END IF;
  RETURN NEW;
END $$;

-- RLS (기본 deny — service_role 우회. anon/authenticated 직접 접근 차단)
ALTER TABLE public.manager_rejections ENABLE ROW LEVEL SECURITY;

-- ── backfill: 기존 승인 도매의 profiles.manager_id 를 살아있는 manager_wholesalers 링크에서 채움 ──
--   구버전(_10 이전 로직)으로 승인된 도매는 manager_id 가 비어 있어, 새 '승인됨 목록'(manager_id 기준)에서
--   누락된다. 살아있는 소속 링크가 있으면 그 manager_id 로 보정(신규 승인은 approve_account 가 직접 세팅).
UPDATE public.profiles p
   SET manager_id = mw.manager_id
  FROM public.manager_wholesalers mw
 WHERE p.role = 'wholesaler' AND p.manager_id IS NULL AND p.deleted_at IS NULL
   AND mw.wholesaler_id = p.wholesaler_id AND mw.deleted_at IS NULL;
