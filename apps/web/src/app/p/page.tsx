"use client";
/**
 * 공개 QR 카드 — QR 스캔 시 뜨는 인스타그램 비율(4:5) 모바일 제품 카드.
 *
 * - 정적 export(`output: 'export'`) 환경 → 동적 경로 대신 **`/p?code=EZM-…` 쿼리 + 클라 페치**
 *   (런타임 서버 없이 어떤 코드든 동작, 새 상품마다 재빌드 불필요).
 * - 데이터 = 백엔드 `GET /p/{platform_code}`.
 *   · 비로그인/외부 → 가격·재고 없는 최소 카드(품번=업체품번·이미지·혼용률·원산지).
 *   · 로그인 + 승인 셀러 → 세션 토큰을 실어 보내면 서버가 역할별 가격(visible_price)
 *     + 색상/사이즈별 재고를 추가로 내려준다(에이전시 소속 셀러는 "가격 문의").
 * - 공개 접근 가능 페이지(로그인은 선택). (dash) 그룹 밖이라 사이드바 없는 단독 화면.
 * - 시안에 전용 화면 없음 → 디자인 토큰 기반 신규 디자인(DESIGN-SYSTEM §QR 카드).
 */
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { supabase } from "@/lib/supabase";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8444";

type CardSku = {
  color: string;
  size: string;
  stock: number | null;
  price?: number | null; // 셀러 단일가(노출 허용 시 number, 미노출 시 null)
  wholesale_price?: number; // 관리뷰(도매 본인/admin) 전용
  retail_price?: number | null; // 관리뷰 전용
};

type PublicCard = {
  platform_code: string;
  source_p_number: string | null; // 업체 품번(표시용)
  item_name: string;
  fabric_composition: string | null;
  origin: string | null;
  representative_image_url: string | null;
  skus?: CardSku[]; // 로그인 + 승인 뷰어에게만 내려옴
};

export default function ProductCardPage() {
  // useSearchParams 는 정적 export 시 Suspense 경계 필요(빌드 규칙).
  return (
    <Suspense fallback={<Shell><SkeletonCard /></Shell>}>
      <CardLoader />
    </Suspense>
  );
}

function CardLoader() {
  const code = useSearchParams().get("code")?.trim() ?? "";
  // data.card: PublicCard(찾음) | null(404/오류). data===null 또는 옛 code 면 아직 로딩.
  const [data, setData] = useState<{ code: string; card: PublicCard | null } | null>(null);

  useEffect(() => {
    if (!code) return;
    let alive = true;
    (async () => {
      // 로그인 상태면 토큰을 실어 보낸다(서버가 역할별 가격/재고 추가). 비로그인이면 헤더 없이 = 공개 최소 응답.
      let headers: HeadersInit = {};
      try {
        const { data: sess } = await supabase.auth.getSession();
        if (sess.session) headers = { Authorization: `Bearer ${sess.session.access_token}` };
      } catch {
        /* 세션 조회 실패 → 익명으로 진행 */
      }
      try {
        const res = await fetch(`${API_BASE}/p/${encodeURIComponent(code)}`, { cache: "no-store", headers });
        const card = res.ok ? ((await res.json()) as PublicCard) : null;
        if (alive) setData({ code, card });
      } catch {
        if (alive) setData({ code, card: null });
      }
    })();
    return () => {
      alive = false;
    };
  }, [code]);

  const resolved = data && data.code === code ? data.card : undefined; // undefined = 로딩 중
  const status: "empty" | "loading" | "ok" = !code
    ? "empty"
    : resolved === undefined
      ? "loading"
      : resolved
        ? "ok"
        : "empty";

  useEffect(() => {
    if (resolved) document.title = `${resolved.item_name} — ezmerce`;
  }, [resolved]);

  return (
    <Shell>
      {status === "loading" && <SkeletonCard />}
      {status === "ok" && resolved && <Card card={resolved} />}
      {status === "empty" && <NotFound />}
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main className="relative flex min-h-dvh flex-col items-center justify-center bg-canvas px-5 py-10">
      {/* 상단 은은한 잉크 그라데이션 — 깊이감 */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-44 bg-gradient-to-b from-ink/[0.07] to-transparent"
      />
      <div className="relative w-full max-w-[26rem]">
        <div className="mb-6 text-center">
          <span className="font-serif text-[1.75rem] italic leading-none text-ink">ezmerce</span>
        </div>
        {children}
        <p className="mt-6 text-center text-xs text-muted-foreground">
          ezmerce 공식 제품 정보 · 무단 도용 금지
        </p>
      </div>
    </main>
  );
}

function Card({ card }: { card: PublicCard }) {
  const specs: { label: string; value: string }[] = [];
  if (card.fabric_composition) specs.push({ label: "혼용률", value: card.fabric_composition });
  if (card.origin) specs.push({ label: "원산지", value: card.origin });

  const pnum = card.source_p_number ?? card.platform_code; // 업체 품번 우선, 없으면 EZM 코드
  const skus = card.skus ?? []; // 로그인 + 승인 뷰어에게만 채워짐
  const prices = skus
    .map((s) => s.price ?? s.wholesale_price) // 셀러 단일가 → 없으면 관리뷰 도매가
    .filter((n): n is number => n != null);
  const repPrice = prices.length ? Math.min(...prices) : null; // 대표 도매가(미노출=null)
  const showPricing = skus.length > 0; // 옵션 정보가 내려왔다 = 로그인 셀러

  // 색상 → 사이즈(숫자 우선) 정렬. 색상은 그룹 첫 행에만 표기.
  const rows = [...skus].sort(
    (a, b) =>
      a.color.localeCompare(b.color, "ko") || a.size.localeCompare(b.size, "ko", { numeric: true })
  );

  return (
    <article className="overflow-hidden rounded-2xl border border-divider bg-surface shadow-lg">
      {/* 히어로 — 인스타 4:5 */}
      <div className="relative aspect-[4/5] w-full bg-subtle">
        {card.representative_image_url ? (
          // 외부(Supabase Storage) 공개 URL → next/image 원격 설정 불필요한 plain img.
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={card.representative_image_url}
            alt={card.item_name}
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center">
            <span className="font-serif text-6xl italic text-border-strong">e</span>
          </div>
        )}
      </div>

      {/* 본문 */}
      <div className="space-y-4 p-6">
        <div>
          <h1 className="text-xl font-bold leading-snug tracking-tight text-foreground">
            {card.item_name}
          </h1>
          <p className="mt-1.5 font-mono text-xs tracking-wide text-muted-foreground">
            품번 {pnum}
          </p>
        </div>

        {/* 도매가 — 로그인 셀러에게만. 미노출(에이전시 소속 등)이면 "가격 문의". */}
        {showPricing && (
          <div className="flex items-baseline justify-between rounded-xl bg-subtle px-4 py-3">
            <span className="text-sm text-muted-foreground">도매가</span>
            <span className="text-lg font-bold tracking-tight text-foreground">
              {repPrice == null ? "가격 문의" : `₩${repPrice.toLocaleString("ko-KR")}`}
            </span>
          </div>
        )}

        {specs.length > 0 && (
          <dl className="divide-y divide-divider overflow-hidden rounded-xl border border-divider">
            {specs.map((s) => (
              <div key={s.label} className="flex items-start justify-between gap-4 px-4 py-3">
                <dt className="shrink-0 text-sm text-muted-foreground">{s.label}</dt>
                <dd className="text-right text-sm font-medium text-foreground">{s.value}</dd>
              </div>
            ))}
          </dl>
        )}

        {/* 색상 × 사이즈 재고 — 로그인 셀러에게만. */}
        {showPricing && rows.length > 0 && (
          <div>
            <div className="mb-1.5 text-sm font-semibold text-[var(--color-text-secondary)]">
              색상 · 사이즈별 재고
            </div>
            <div className="overflow-hidden rounded-xl border border-divider">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-divider bg-canvas text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    <th className="px-3 py-2">색상</th>
                    <th className="px-3 py-2">사이즈</th>
                    <th className="px-3 py-2 text-right">재고</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((s, i) => {
                    const newColor = i === 0 || s.color !== rows[i - 1].color;
                    const avail = Math.max(0, s.stock ?? 0); // 음수=예약분 → 가용 0
                    return (
                      <tr
                        key={`${s.color}-${s.size}-${i}`}
                        className={
                          newColor && i > 0 ? "border-t-2 border-t-divider" : "border-t border-divider/50"
                        }
                      >
                        <td className="px-3 py-2 font-medium text-foreground">{newColor ? s.color : ""}</td>
                        <td className="px-3 py-2 text-[var(--color-text-secondary)]">{s.size}</td>
                        <td className="px-3 py-2 text-right tabular-nums">
                          {avail <= 0 ? (
                            <span className="font-semibold text-[var(--color-danger-fg)]">품절</span>
                          ) : (
                            <span className="text-foreground">{avail.toLocaleString("ko-KR")}</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </article>
  );
}

function SkeletonCard() {
  return (
    <div className="overflow-hidden rounded-2xl border border-divider bg-surface shadow-lg">
      <div className="aspect-[4/5] w-full animate-pulse bg-subtle" />
      <div className="space-y-3 p-6">
        <div className="h-5 w-2/3 animate-pulse rounded bg-subtle" />
        <div className="h-3 w-1/3 animate-pulse rounded bg-subtle" />
        <div className="h-16 w-full animate-pulse rounded-xl bg-subtle" />
      </div>
    </div>
  );
}

function NotFound() {
  return (
    <article className="rounded-2xl border border-divider bg-surface p-10 text-center shadow-lg">
      <div className="mx-auto mb-4 flex size-14 items-center justify-center rounded-full bg-subtle">
        <span className="font-serif text-2xl italic text-border-strong">e</span>
      </div>
      <h1 className="text-lg font-bold text-foreground">제품을 찾을 수 없습니다</h1>
      <p className="mx-auto mt-2 max-w-[18rem] text-sm leading-relaxed text-muted-foreground">
        QR이 가리키는 제품이 더 이상 존재하지 않거나, 주소가 올바르지 않습니다.
      </p>
    </article>
  );
}
