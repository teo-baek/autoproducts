import type { ReactNode } from "react";

/**
 * 인증 스플릿 셸 (DESIGN-SYSTEM 셸 A) — 좌: 풀블리드 쇼룸 히어로 + 로고/카피, 우: 폼 슬롯.
 * 모바일에선 히어로 숨기고 폼만 표시.
 */
export function AuthShell({ children }: { children: ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      {/* 좌측 히어로 */}
      <aside className="relative hidden overflow-hidden lg:block">
        <div
          className="absolute inset-0 bg-cover bg-center"
          style={{ backgroundImage: "url(/images/marketing/hero-showroom.jpg)" }}
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-black/10 to-black/25" />
        <div className="relative flex h-full flex-col justify-between p-12 text-white">
          <header>
            <div className="font-serif text-3xl italic">ezmerce</div>
            <p className="mt-1 text-sm text-white/70">Wholesale Management Service</p>
          </header>
          <div>
            <h2 className="text-5xl font-extrabold leading-[1.04] tracking-tight">
              Elevate your
              <br />
              wholesale
              <br />
              management.
            </h2>
            <p className="mt-5 max-w-md text-sm leading-relaxed text-white/80">
              Precision control and premium editorial presentation for high-stakes
              inventory and retail partnerships.
            </p>
          </div>
        </div>
      </aside>

      {/* 우측 폼 */}
      <main className="flex items-center justify-center bg-canvas px-6 py-12 sm:px-10 lg:px-16">
        <div className="w-full max-w-md py-6">{children}</div>
      </main>
    </div>
  );
}
