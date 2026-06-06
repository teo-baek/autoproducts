"use client";

import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";
import { getMe } from "@/lib/products";
import { Spinner } from "./icons";
import { Button } from "./ui";

type GateState = "loading" | "ok" | "denied" | "error";

/**
 * 관리자(admin) 전용 게이트 — 플랫폼 관리자 콘솔(/admin) 보호.
 * 도매/소매/에이전시는 진입 불가(각자 작업공간으로).
 */
export function AdminGate({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [state, setState] = useState<GateState>("loading");
  const [msg, setMsg] = useState("");

  useEffect(() => {
    let active = true;
    getMe()
      .then((me) => {
        if (!active) return;
        if (me.role === "admin") setState("ok");
        else if (me.role === "wholesaler") router.replace("/products"); // 도매는 자기 작업공간으로
        else setState("denied");
      })
      .catch((e) => {
        if (!active) return;
        setMsg(e instanceof Error ? e.message : "알 수 없는 오류");
        setState("error");
      });
    return () => {
      active = false;
    };
  }, [router]);

  async function logout() {
    await supabase.auth.signOut();
    router.replace("/login");
  }

  if (state === "loading") {
    return (
      <div className="grid min-h-screen place-items-center bg-canvas text-muted-foreground">
        <Spinner width={28} height={28} />
      </div>
    );
  }
  if (state === "ok") return <>{children}</>;

  return (
    <div className="grid min-h-screen place-items-center bg-canvas px-6">
      <div className="w-full max-w-md text-center">
        <div className="font-serif text-2xl italic text-foreground">ezmerce</div>
        <h1 className="mt-6 text-2xl font-extrabold tracking-tight text-foreground">
          {state === "error" ? "서버에 연결할 수 없습니다" : "관리자 전용 콘솔입니다"}
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          {state === "error"
            ? msg
            : "이 영역은 플랫폼 관리자(Admin) 계정만 이용할 수 있습니다."}
        </p>
        <div className="mt-8">
          <Button variant="secondary" onClick={logout}>
            로그아웃
          </Button>
        </div>
      </div>
    </div>
  );
}
