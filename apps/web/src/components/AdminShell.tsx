"use client";

import { useState } from "react";
import type { ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LogoutDialog } from "./LogoutDialog";
import { Box, LogOut, Users } from "./icons";

type NavItem = { href: string; label: string; icon: typeof Users };

const NAV: NavItem[] = [
  { href: "/admin", label: "가입 승인", icon: Users },
  { href: "/admin/customers", label: "고객 관리", icon: Users },
  { href: "/admin/products", label: "상품 관리", icon: Box },
];

/**
 * 관리자 콘솔 셸 — 도매 작업공간(Shell)과 의도적으로 분리된 별도 크롬.
 * 플랫폼 관리자(LALAS 연합/에이전시 리더)가 폐쇄망을 운영하는 영역.
 */
export function AdminShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [logoutOpen, setLogoutOpen] = useState(false);
  const isActive = (href: string) =>
    href === "/admin" ? pathname === href : pathname === href || pathname.startsWith(href + "/");

  return (
    <div className="flex min-h-screen bg-canvas">
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col bg-ink-strong text-white lg:flex">
        <div className="flex items-center gap-3 px-6 py-6">
          <span className="flex size-9 items-center justify-center rounded-full bg-white/10 font-serif text-lg italic">
            e
          </span>
          <div>
            <div className="font-serif text-xl italic leading-none">ezmerce</div>
            <div className="mt-1 flex items-center gap-1.5">
              <span className="rounded bg-[var(--color-grade-bg)] px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-[var(--color-grade-fg)]">
                Admin
              </span>
              <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-white/40">
                관리자 콘솔
              </span>
            </div>
          </div>
        </div>

        <nav className="mt-2 flex-1 space-y-1 px-3">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active = isActive(href);
            return (
              <Link
                key={href}
                href={href}
                className={`relative flex items-center gap-3 rounded-[var(--radius)] px-3.5 py-3 text-sm font-medium transition ${
                  active
                    ? "bg-white/[0.08] text-white"
                    : "text-white/55 hover:bg-white/5 hover:text-white/90"
                }`}
              >
                {active && (
                  <span className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-[var(--color-success-solid)]" />
                )}
                <Icon width={18} height={18} />
                {label}
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-white/10 px-3 py-4">
          <button
            type="button"
            onClick={() => setLogoutOpen(true)}
            className="flex w-full items-center gap-3 rounded-[var(--radius)] px-3.5 py-3 text-sm font-medium text-white/55 transition hover:bg-white/5 hover:text-white/90"
          >
            <LogOut width={18} height={18} />
            로그아웃
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-divider bg-surface px-5 sm:px-8">
          <span className="text-sm font-bold text-foreground">관리자 콘솔</span>
          <span className="rounded-full bg-[var(--color-grade-bg)] px-2.5 py-1 text-xs font-semibold text-[var(--color-grade-fg)]">
            Admin
          </span>
          <button
            type="button"
            onClick={() => setLogoutOpen(true)}
            className="ml-auto inline-flex items-center gap-1.5 text-sm font-medium text-muted-foreground transition hover:text-foreground lg:hidden"
          >
            <LogOut width={16} height={16} /> 로그아웃
          </button>
        </header>

        <main className="flex-1 px-5 py-8 sm:px-8 lg:px-10">{children}</main>
      </div>

      <LogoutDialog open={logoutOpen} onClose={() => setLogoutOpen(false)} />
    </div>
  );
}
