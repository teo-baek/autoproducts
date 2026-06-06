"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";
import { getMe } from "@/lib/products";
import { AuthShell } from "@/components/AuthShell";
import { Alert, Button, Checkbox, TextField } from "@/components/ui";
import { Eye, EyeOff, Lock, Mail } from "@/components/icons";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [remember, setRemember] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    setLoading(false);
    if (error) {
      console.error("[login]", error);
      const msg = error.message ?? "";
      if (/invalid login credentials/i.test(msg)) {
        setError("이메일 또는 비밀번호가 올바르지 않습니다.");
      } else if (/api key|apikey|project|fetch|failed/i.test(msg)) {
        setError("Supabase 설정 오류 — apps/web/.env.local 의 anon 키를 채우고 dev 서버를 재시작하세요.");
      } else {
        setError(`로그인 실패: ${msg}`);
      }
      return;
    }
    // 역할별 진입점: 관리자 → 고객 관리(승인), 그 외 → 상품 관리
    try {
      const me = await getMe();
      router.push(me.role === "admin" ? "/customers" : "/products");
    } catch {
      router.push("/products");
    }
  }

  return (
    <AuthShell>
      <h1 className="text-3xl font-extrabold tracking-tight text-foreground">환영합니다</h1>
      <p className="mt-2 text-muted-foreground">계정에 로그인하여 관리 시스템에 접속하세요.</p>

      <form onSubmit={onSubmit} className="mt-8 space-y-5">
        <Alert>{error}</Alert>

        <TextField
          label="이메일 주소"
          type="email"
          name="email"
          autoComplete="email"
          required
          placeholder="name@company.com"
          leftIcon={<Mail />}
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />

        <TextField
          label="비밀번호"
          type={showPw ? "text" : "password"}
          name="password"
          autoComplete="current-password"
          required
          placeholder="••••••••"
          leftIcon={<Lock />}
          labelRight={
            <Link
              href="#"
              className="text-sm font-medium text-muted-foreground hover:text-ink"
            >
              비밀번호 찾기
            </Link>
          }
          right={
            <button
              type="button"
              onClick={() => setShowPw((s) => !s)}
              className="text-border-strong transition hover:text-foreground"
              aria-label={showPw ? "비밀번호 숨기기" : "비밀번호 표시"}
            >
              {showPw ? <EyeOff /> : <Eye />}
            </button>
          }
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />

        <Checkbox
          label="로그인 상태 유지"
          checked={remember}
          onChange={(e) => setRemember(e.target.checked)}
        />

        <Button type="submit" loading={loading} className="w-full">
          로그인
        </Button>
      </form>

      <hr className="my-7 border-divider" />

      <p className="text-sm text-muted-foreground">
        계정 지원이 필요하신가요?{" "}
        <Link href="/register" className="font-semibold text-ink hover:underline">
          회원 가입
        </Link>{" "}
        후 관리자 승인을 요청하세요.
      </p>
    </AuthShell>
  );
}
