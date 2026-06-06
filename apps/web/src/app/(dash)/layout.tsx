"use client";

import type { ReactNode } from "react";
import { AuthGuard } from "@/components/AuthGuard";
import { AccessGate } from "@/components/AccessGate";
import { Shell } from "@/components/Shell";

/** 백오피스(셸-B) 공통 레이아웃 — 로그인 가드 + 접근 게이트(도매/관리자) + 사이드바/탑바. */
export default function DashLayout({ children }: { children: ReactNode }) {
  return (
    <AuthGuard>
      <AccessGate>
        <Shell>{children}</Shell>
      </AccessGate>
    </AuthGuard>
  );
}
