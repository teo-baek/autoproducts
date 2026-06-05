import { createClient } from "@supabase/supabase-js";

// 브라우저 Supabase 클라이언트 — 로그인(signInWithPassword)·세션 보관용.
// 비밀번호 검증/JWT 발급은 Supabase Auth(GoTrue)가 수행. 서버는 JWKS로 검증만.
const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const anon = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

const missing = [
  !url && "NEXT_PUBLIC_SUPABASE_URL",
  !anon && "NEXT_PUBLIC_SUPABASE_ANON_KEY",
].filter(Boolean);
if (missing.length) {
  // 이건 '프론트 전용' env(apps/web/.env.local). 백엔드 .env(SUPABASE_URL+SERVICE_KEY)와 별개다.
  // 프론트엔 반드시 anon(public) 키를 넣는다 — service key 는 절대 금지(브라우저로 노출됨).
  console.warn(
    `[ezmerce] 누락된 프론트 env: ${missing.join(", ")} → apps/web/.env.local 에 채우세요 (anon=public 키).`
  );
}

// env 누락 시에도 모듈 로드가 깨지지 않게 placeholder 폴백(빈 키면 createClient 가 throw).
// .env.local 채우면 실제 값 사용. signIn 은 실제 키 없으면 당연히 실패.
export const supabase = createClient(
  url || "https://placeholder.supabase.co",
  anon || "anon-key-missing-fill-env-local",
  { auth: { persistSession: true, autoRefreshToken: true } }
);
