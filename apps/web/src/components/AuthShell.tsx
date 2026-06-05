import type { ReactNode } from "react";

// 미세 그레인 텍스처 (SVG fractalNoise) — 딥네이비 패널에 촉감 부여
const GRAIN =
  "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.82' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")";

/**
 * 인증 스플릿 셸 (DESIGN-SYSTEM 셸 A).
 * 좌: 사진 대신 디자인 토큰 기반 에디토리얼 비주얼(딥네이비 + 글로우 + 그리드 + 그레인 + 워터마크).
 * 우: 폼 슬롯. 모바일에선 좌측 숨김.
 */
export function AuthShell({ children }: { children: ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      {/* 좌측 디자인 패널 */}
      <aside className="relative hidden overflow-hidden bg-ink text-white lg:block">
        {/* 컬러 글로우 (사지 + 슬레이트) */}
        <div
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(820px 520px at 88% -8%, rgba(97,157,127,0.24), transparent 60%), radial-gradient(760px 520px at -5% 112%, rgba(148,163,184,0.18), transparent 55%)",
          }}
        />
        {/* 미세 그리드 */}
        <div
          className="absolute inset-0 opacity-[0.05]"
          style={{
            backgroundImage:
              "linear-gradient(to right, #fff 1px, transparent 1px), linear-gradient(to bottom, #fff 1px, transparent 1px)",
            backgroundSize: "72px 72px",
          }}
        />
        {/* 세리프 워터마크 (edge bleed) */}
        <div className="pointer-events-none absolute -bottom-28 -right-10 select-none font-serif text-[26rem] italic leading-none text-white/[0.045]">
          e
        </div>
        {/* 그레인 */}
        <div
          className="absolute inset-0 opacity-[0.10] mix-blend-overlay"
          style={{ backgroundImage: GRAIN }}
        />

        {/* 콘텐츠 */}
        <div className="relative flex h-full flex-col justify-between p-12">
          <header>
            <div className="font-serif text-3xl italic">ezmerce</div>
            <div className="mt-3 h-px w-12 bg-white/25" />
            <p className="mt-3 text-xs font-medium uppercase tracking-[0.18em] text-white/55">
              Wholesale Management Service
            </p>
          </header>

          <div>
            <p className="mb-5 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--color-success-solid)]">
              폐쇄형 B2B 도매 네트워크 · LALAS
            </p>
            <h2 className="text-5xl font-extrabold leading-[1.04] tracking-tight">
              Elevate your
              <br />
              wholesale
              <br />
              management.
            </h2>
            <p className="mt-6 max-w-md text-sm leading-relaxed text-white/65">
              승인된 파트너를 위한 폐쇄형 카탈로그. 역할별 가격·정밀한 재고 관리와
              에디토리얼 프레젠테이션을 한 곳에서.
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
