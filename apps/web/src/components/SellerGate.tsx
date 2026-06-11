"use client";

import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";
import { getMe, type Me } from "@/lib/products";
import { Spinner } from "./icons";
import { Button } from "./ui";

type GateState =
  | { status: "loading" }
  | { status: "ok"; me: Me }
  | { status: "denied"; me: Me }
  | { status: "pending"; me: Me }
  | { status: "error"; msg: string };

/**
 * 셀러(retail_seller) 전용 게이트 — 셀러 작업공간(에디토리얼 셸) 보호.
 * 통과: 승인된 소매셀러. 관리자/도매는 각자 홈으로 보낸다(교차 진입 방지).
 * (에이전시는 1차 미운영 → denied)
 */
export function SellerGate({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [state, setState] = useState<GateState>({ status: "loading" });

  useEffect(() => {
    let active = true;
    getMe()
      .then((me) => {
        if (!active) return;
        if (me.role === "admin") {
          router.replace("/admin"); // 관리자는 관리자 콘솔로
          return;
        }
        if (me.role === "wholesaler") {
          router.replace("/products"); // 도매는 도매 작업공간으로
          return;
        }
        if (me.role !== "retail_seller") setState({ status: "denied", me });
        else if (me.status !== "approved") setState({ status: "pending", me });
        else setState({ status: "ok", me });
      })
      .catch((e) =>
        active &&
        setState({ status: "error", msg: e instanceof Error ? e.message : "알 수 없는 오류" })
      );
    return () => {
      active = false;
    };
  }, [router]);

  async function logout() {
    await supabase.auth.signOut();
    router.replace("/login");
  }

  if (state.status === "loading") {
    return (
      <div className="grid min-h-screen place-items-center bg-canvas text-muted-foreground">
        <Spinner width={28} height={28} />
      </div>
    );
  }
  if (state.status === "ok") return <>{children}</>;

  const copy: Record<string, { title: string; body: string }> = {
    denied: {
      title: "셀러 회원 전용 영역입니다",
      body: "쇼룸은 소매셀러(Retail Seller) 계정으로만 이용할 수 있습니다. 다른 계정으로 로그인해 주세요.",
    },
    pending: {
      title: "관리자 승인 대기 중",
      body: "계정이 아직 승인되지 않았습니다. 관리자 승인 후 쇼룸을 이용할 수 있습니다.",
    },
    error: {
      title: "서버에 연결할 수 없습니다",
      body: state.status === "error" ? state.msg : "",
    },
  };
  const c = copy[state.status];

  return (
    <div className="grid min-h-screen place-items-center bg-canvas px-6">
      <div className="w-full max-w-md text-center">
        <div className="font-serif text-2xl italic text-foreground">ezmerce</div>
        <h1 className="mt-6 text-2xl font-extrabold tracking-tight text-foreground">{c.title}</h1>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{c.body}</p>
        <div className="mt-8">
          <Button variant="secondary" onClick={logout}>
            로그아웃
          </Button>
        </div>
      </div>
    </div>
  );
}
