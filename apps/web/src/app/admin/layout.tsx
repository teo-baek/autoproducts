"use client";

import type { ReactNode } from "react";
import { AuthGuard } from "@/components/AuthGuard";
import { AdminGate } from "@/components/AdminGate";
import { AdminShell } from "@/components/AdminShell";

/** 플랫폼 관리자 콘솔 레이아웃 — 로그인 가드 + 관리자 전용 게이트 + 관리자 셸. */
export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <AuthGuard>
      <AdminGate>
        <AdminShell>{children}</AdminShell>
      </AdminGate>
    </AuthGuard>
  );
}
