"use client";

import type { ReactNode } from "react";
import { AuthGuard } from "@/components/AuthGuard";
import { SellerGate } from "@/components/SellerGate";
import { SellerShell } from "@/components/SellerShell";

/** 셀러 작업공간 공통 레이아웃 — 로그인 가드 + 셀러 전용 게이트 + 에디토리얼 셸. */
export default function SellerLayout({ children }: { children: ReactNode }) {
  return (
    <AuthGuard>
      <SellerGate>
        <SellerShell>{children}</SellerShell>
      </SellerGate>
    </AuthGuard>
  );
}
