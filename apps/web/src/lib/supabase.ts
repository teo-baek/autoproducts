import { createClient } from "@supabase/supabase-js";

// 브라우저 Supabase 클라이언트 — 로그인(signInWithPassword)·세션 보관용.
// 비밀번호 검증/JWT 발급은 Supabase Auth(GoTrue)가 수행. 서버는 JWKS로 검증만.
const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const anon = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

if (!url || !anon) {
  // 개발 편의: env 누락 시 콘솔 경고(빌드는 통과). .env.local 채우면 됨.
  console.warn(
    "[ezmerce] NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY 가 비어있습니다. apps/web/.env.local 을 채우세요."
  );
}

// env 누락 시에도 모듈 로드가 깨지지 않게 placeholder 폴백(빈 키면 createClient 가 throw).
// .env.local 채우면 실제 값 사용. signIn 은 실제 키 없으면 당연히 실패.
export const supabase = createClient(
  url || "https://placeholder.supabase.co",
  anon || "anon-key-missing-fill-env-local",
  { auth: { persistSession: true, autoRefreshToken: true } }
);
