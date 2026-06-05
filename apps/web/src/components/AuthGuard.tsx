"use client";

import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";
import { Spinner } from "./icons";

/**
 * 클라이언트 인증 가드 — 세션 없으면 /login 으로 리다이렉트.
 * (브라우저 supabase 클라이언트 = localStorage 세션 기준. 보호가 필요한 페이지를 감싼다.)
 * 로그아웃/세션만료 시에도 자동으로 /login 으로 보낸다.
 */
export function AuthGuard({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let active = true;
    supabase.auth.getSession().then(({ data }) => {
      if (!active) return;
      if (data.session) setReady(true);
      else router.replace("/login");
    });
    const { data: sub } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!session) router.replace("/login");
    });
    return () => {
      active = false;
      sub.subscription.unsubscribe();
    };
  }, [router]);

  if (!ready) {
    return (
      <div className="grid min-h-screen place-items-center bg-canvas text-muted-foreground">
        <Spinner width={28} height={28} />
      </div>
    );
  }
  return <>{children}</>;
}
