"use client";

import { useState } from "react";
import type { ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LogoutDialog } from "./LogoutDialog";
import { Popover } from "./ui";
import { Bag, LogOut, User } from "./icons";

type NavItem = { href: string; label: string };

const NAV: NavItem[] = [
  { href: "/seller/showroom", label: "SHOWROOM" },
  { href: "/seller/orders", label: "ORDERS" },
  { href: "/seller/analytics", label: "ANALYTICS" },
];

/**
 * 셀러 셸 — 에디토리얼 상단 내비(시안 "쇼룸 현황"). 도매 셸-B(다크 사이드바)와 달리
 * 중앙 정렬 메뉴 + 우측 장바구니/계정 + 하단 푸터의 라이트 레이아웃.
 */
export function SellerShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [logoutOpen, setLogoutOpen] = useState(false);
  const isActive = (href: string) => pathname === href || pathname.startsWith(href + "/");

  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      {/* ── 상단 내비 ── */}
      <header className="sticky top-0 z-30 border-b border-divider bg-canvas/90 backdrop-blur">
        <div className="relative mx-auto flex h-20 w-full max-w-[1400px] items-center px-6 sm:px-10">
          <Link
            href="/seller/showroom"
            className="font-serif text-2xl font-bold tracking-tight text-foreground"
          >
            ezmerce
          </Link>

          <nav className="absolute left-1/2 hidden -translate-x-1/2 items-center gap-10 md:flex">
            {NAV.map(({ href, label }) => {
              const active = isActive(href);
              return (
                <Link
                  key={href}
                  href={href}
                  className={`relative text-sm font-medium uppercase tracking-[0.15em] transition ${
                    active ? "text-foreground" : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {label}
                  {active && (
                    <span className="absolute -bottom-2 left-0 h-px w-full bg-foreground" />
                  )}
                </Link>
              );
            })}
          </nav>

          <div className="ml-auto flex items-center gap-5 text-foreground">
            <button
              type="button"
              aria-label="장바구니"
              title="장바구니 — 준비 중 (Phase 2)"
              className="text-foreground/75 transition hover:text-foreground"
            >
              <Bag width={20} height={20} />
            </button>
            <Popover
              align="end"
              trigger={({ toggle }) => (
                <button
                  type="button"
                  aria-label="계정"
                  onClick={toggle}
                  className="text-foreground/75 transition hover:text-foreground"
                >
                  <User width={20} height={20} />
                </button>
              )}
            >
              {(close) => (
                <button
                  type="button"
                  onClick={() => {
                    close();
                    setLogoutOpen(true);
                  }}
                  className="flex w-full items-center gap-2 rounded-[var(--radius)] px-3 py-2.5 text-sm font-medium text-foreground transition hover:bg-subtle"
                >
                  <LogOut width={16} height={16} /> 로그아웃
                </button>
              )}
            </Popover>
          </div>
        </div>

        {/* 모바일 내비(중앙 메뉴 대체) */}
        <nav className="flex items-center justify-center gap-8 border-t border-divider px-6 py-3 md:hidden">
          {NAV.map(({ href, label }) => {
            const active = isActive(href);
            return (
              <Link
                key={href}
                href={href}
                className={`text-xs font-medium uppercase tracking-[0.15em] ${
                  active ? "text-foreground" : "text-muted-foreground"
                }`}
              >
                {label}
              </Link>
            );
          })}
        </nav>
      </header>

      <LogoutDialog open={logoutOpen} onClose={() => setLogoutOpen(false)} />

      <main className="mx-auto w-full max-w-[1400px] flex-1 px-6 py-10 sm:px-10">{children}</main>

      {/* ── 푸터 ── */}
      <footer className="border-t border-divider">
        <div className="mx-auto flex w-full max-w-[1400px] flex-col items-start gap-4 px-6 py-8 sm:flex-row sm:items-center sm:px-10">
          <span className="font-serif text-xl font-bold tracking-tight text-foreground">
            ezmerce
          </span>
          <div className="flex flex-wrap gap-x-6 gap-y-2 text-xs font-medium uppercase tracking-[0.12em] text-muted-foreground">
            {/* 1차 미구현 정적 링크 — 추후 약관/지원 페이지 연결 */}
            <span className="cursor-default underline-offset-4 hover:underline">Privacy Policy</span>
            <span className="cursor-default underline-offset-4 hover:underline">Terms of Service</span>
            <span className="cursor-default underline-offset-4 hover:underline">Contact</span>
            <span className="cursor-default underline-offset-4 hover:underline">Support</span>
          </div>
          <span className="text-xs uppercase tracking-[0.12em] text-muted-foreground sm:ml-auto">
            © 2026 ezmerce. All rights reserved.
          </span>
        </div>
      </footer>
    </div>
  );
}
