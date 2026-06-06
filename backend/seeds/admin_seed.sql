-- ============================================================================
-- ezmerce — 플랫폼 관리자(admin) 시드 스크립트
-- ----------------------------------------------------------------------------
-- 실행 위치 : Supabase 대시보드 → SQL Editor (이 파일 전체 붙여넣고 Run)
-- 목적      : LALAS 운영용 '관리자(admin)' 계정을 만든다.
--             admin 은 앱 자가가입이 막혀 있으므로(권한 상승 방지) 시드로 직접 만든다.
-- 멱등성    : 같은 이메일로 다시 실행해도 안전(있으면 admin 으로 보정/비번 갱신).
-- 선행 조건 : v2 마이그레이션(_v2_core ~ _07)이 이미 적용돼 있어야 한다.
--             pgcrypto 확장 필요(Supabase 기본 설치됨). 혹시 crypt 가 안 잡히면 아래 1줄을 먼저 실행:
--               create extension if not exists pgcrypto with schema extensions;
-- 보안 주의 : 초기 비밀번호는 시드 직후 반드시 변경 권장. 이 파일을 비번이 적힌 채로 커밋/공유하지 말 것.
-- ============================================================================

-- ┌──────────────────────────────────────────────────────────────────────┐
-- │ ⚙️  여기 두 값만 본인 것으로 수정하세요 (DO 블록 안 v_email / v_password) │
-- └──────────────────────────────────────────────────────────────────────┘
-- 아래 OPTION A(완전 SQL 시드)가 기본 실행 경로입니다.
-- auth 스키마 버전 문제로 실패하면 → 맨 아래 OPTION B(앱 가입 후 승격)를 쓰세요.

-- ====================== OPTION A. 완전 SQL 시드(권장) ========================
-- auth.users + auth.identities + profiles 를 한 번에 생성/보정한다.
DO $$
DECLARE
  v_email    text := 'admin@jinju-ict.com';   -- ← 관리자 이메일
  v_password text := 'ChangeMe!2026';         -- ← 초기 비밀번호(8자 이상). 로그인 후 변경할 것
  v_name     text := '플랫폼 관리자';          -- ← 표시용 이름(선택)
  v_uid      uuid;
BEGIN
  -- 1) 이미 존재하는 이메일인지 확인
  SELECT id INTO v_uid FROM auth.users WHERE email = v_email;

  IF v_uid IS NULL THEN
    -- 2) 없으면 Auth 계정 신규 생성 (비밀번호는 bcrypt 해시로 저장)
    v_uid := gen_random_uuid();
    INSERT INTO auth.users (
      instance_id, id, aud, role, email,
      encrypted_password, email_confirmed_at,
      created_at, updated_at,
      raw_app_meta_data, raw_user_meta_data
    ) VALUES (
      '00000000-0000-0000-0000-000000000000', v_uid, 'authenticated', 'authenticated', v_email,
      extensions.crypt(v_password, extensions.gen_salt('bf')), now(),  -- bcrypt 해시 + 이메일 확인 처리
      now(), now(),
      '{"provider":"email","providers":["email"]}'::jsonb, '{}'::jsonb
    );
    -- 이메일 로그인 식별자(identities) — 없으면 비번 로그인이 안 됨
    INSERT INTO auth.identities (
      id, user_id, provider, provider_id, identity_data,
      created_at, updated_at, last_sign_in_at
    ) VALUES (
      gen_random_uuid(), v_uid, 'email', v_uid::text,
      jsonb_build_object('sub', v_uid::text, 'email', v_email, 'email_verified', true),
      now(), now(), now()
    );
  ELSE
    -- 2') 이미 있으면 비밀번호를 v_password 로 재설정(원치 않으면 이 UPDATE 블록을 주석 처리)
    UPDATE auth.users
       SET encrypted_password = extensions.crypt(v_password, extensions.gen_salt('bf')),
           email_confirmed_at  = COALESCE(email_confirmed_at, now()),
           updated_at          = now()
     WHERE id = v_uid;
  END IF;

  -- 3) profiles 를 admin / approved 로 생성·보정 (soft-delete 됐었다면 복구)
  INSERT INTO public.profiles (id, role, status, full_name)
  VALUES (v_uid, 'admin', 'approved', v_name)
  ON CONFLICT (id) DO UPDATE
     SET role = 'admin', status = 'approved', deleted_at = NULL;

  RAISE NOTICE 'ezmerce admin seeded: % (uid=%)', v_email, v_uid;
END $$;

-- 4) 결과 확인 (이메일은 위 v_email 과 동일하게 바꿔서)
SELECT u.email, p.role, p.status, p.full_name
FROM auth.users u
JOIN public.profiles p ON p.id = u.id
WHERE u.email = 'admin@jinju-ict.com';
-- → role=admin, status=approved 한 줄이 나오면 성공. 앱 /login 으로 로그인 → /admin 진입.


-- ====================== OPTION B. 앱 가입 후 승격(대안) ======================
-- OPTION A 가 Supabase auth 스키마 버전 차이로 실패할 때 사용.
-- 절차:
--   1) 앱(/register)에서 해당 이메일로 아무 유형(예: 소매) 가입 → 비밀번호는 여기서 정함
--   2) 아래 UPDATE 한 줄 실행해 admin 으로 승격 (이메일만 본인 것으로 수정)
-- ↓ 평소엔 주석 상태. 쓸 때 이 한 줄의 맨 앞 '-- ' 만 지우고 실행하세요.
-- update public.profiles set role='admin', status='approved'
--   where id = (select id from auth.users where email='admin@jinju-ict.com');


-- ====================== (참고) 관리자 삭제 / 비번 재설정 ======================
-- 완전 삭제(같은 이메일 재사용하려면 auth 까지 지워야 함. profiles 는 캐스케이드 삭제):
--   delete from auth.users where email='admin@jinju-ict.com';
-- 비번만 재설정:
--   update auth.users
--      set encrypted_password = extensions.crypt('새비번', extensions.gen_salt('bf')), updated_at = now()
--    where email='admin@jinju-ict.com';
