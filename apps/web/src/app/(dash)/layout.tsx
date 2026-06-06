"use client";

import type { ReactNode } from "react";
import { AuthGuard } from "@/components/AuthGuard";
import { WholesalerGate } from "@/components/WholesalerGate";
import { Shell } from "@/components/Shell";

/** 도매 백오피스(셸-B) 공통 레이아웃 — 로그인 가드 + 도매 전용 게이트 + 사이드바/탑바. */
export default function DashLayout({ children }: { children: ReactNode }) {
  return (
    <AuthGuard>
      <WholesalerGate>
        <Shell>{children}</Shell>
      </WholesalerGate>
    </AuthGuard>
  );
}
