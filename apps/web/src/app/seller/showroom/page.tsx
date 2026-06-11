"use client";
/* eslint-disable react-hooks/set-state-in-effect -- 서버 데이터 동기화 목적의 의도된 effect */

import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  downloadCatalogXlsx,
  getAllCatalog,
  priceLabel,
  toShowroomCards,
  type ShowroomCard,
} from "@/lib/catalog";
import { colorSwatch } from "@/lib/colors";
import { ChevronLeft, ChevronRight, ImageIcon, Spinner } from "@/components/icons";
// 필터/정렬 UI 는 백엔드 연동 전이라 주석 처리(아래 헤더 우측 블록 참고). 풀 때 같이 import:
// import { ChevronDown, Sort } from "@/components/icons";

const PAGE_SIZE = 16; // 4열 × 4행

export default function ShowroomPage() {
  // 카드는 lib 에서 최신 등록순(created_at desc)으로 정렬되어 온다. 페이지네이션은 클라 슬라이스.
  const [cards, setCards] = useState<ShowroomCard[]>([]);
  const [page, setPage] = useState(0); // 0-indexed
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const items = await getAllCatalog();
      setCards(toShowroomCards(items));
      setPage(0);
    } catch (e) {
      setError(e instanceof Error ? e.message : "쇼룸을 불러오지 못했습니다.");
      setCards([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const totalPages = Math.max(1, Math.ceil(cards.length / PAGE_SIZE));
  const pageCards = useMemo(
    () => cards.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE),
    [cards, page]
  );

  function goPage(n: number) {
    setPage(Math.min(Math.max(0, n), totalPages - 1));
    if (typeof window !== "undefined") window.scrollTo({ top: 0, behavior: "smooth" });
  }

  useEffect(() => {
    // 다운로드 진행 중엔 "준비 중" 안내가 사라지지 않도록 자동 닫힘을 멈춘다.
    if (!toast || downloading) return;
    const t = setTimeout(() => setToast(null), 3500);
    return () => clearTimeout(t);
  }, [toast, downloading]);

  async function onExport() {
    if (downloading) return;
    setDownloading(true);
    setToast("엑셀을 준비하고 있습니다. 잠시만 기다려 주세요…");
    try {
      await downloadCatalogXlsx();
      setToast("엑셀 다운로드가 시작되었습니다.");
    } catch (e) {
      setToast(e instanceof Error ? e.message : "다운로드 실패");
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div>
      {/* ── 헤더 ── */}
      <div className="flex flex-col gap-6 border-b border-foreground pb-6 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-4xl font-extrabold tracking-tight text-foreground sm:text-5xl">
            쇼룸 현황
          </h1>
          <p className="mt-3 text-xs font-semibold uppercase tracking-[0.22em] text-muted-foreground">
            Collection Overview
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/*
            TODO(필터/정렬): 카테고리·시즌·재고상태 드롭다운 + 정렬 아이콘.
            현재 GET /catalog 는 category/season/stock-status 필터 파라미터를 지원하지 않는다
            (season·stock_status 는 DB 컬럼도 없음 → 백엔드 선행 필요). 데이터/파라미터가 붙으면
            아래 마크업의 주석을 풀고 onChange 로 getCatalog 재호출 + 정렬 state 를 연결한다.

            <FilterSelect label="카테고리" />
            <FilterSelect label="시즌" />
            <FilterSelect label="재고 상태" />
            <button type="button" aria-label="정렬"
              className="grid size-11 place-items-center text-foreground/70 transition hover:text-foreground">
              <Sort width={20} height={20} />
            </button>

            // FilterSelect 예시(풀 때 컴포넌트로):
            // function FilterSelect({ label }: { label: string }) {
            //   return (
            //     <button type="button"
            //       className="inline-flex items-center gap-1.5 text-sm font-medium text-muted-foreground transition hover:text-foreground">
            //       {label} <ChevronDown width={15} height={15} />
            //     </button>
            //   );
            // }
          */}

          <button
            type="button"
            onClick={onExport}
            disabled={downloading}
            className="inline-flex items-center justify-center gap-2 bg-ink px-7 py-3 text-sm font-semibold uppercase tracking-[0.08em] text-white transition hover:bg-ink-strong disabled:cursor-not-allowed disabled:opacity-60"
          >
            {downloading && <Spinner width={16} height={16} />}
            내보내기
          </button>
        </div>
      </div>

      {/* ── 본문 ── */}
      {loading ? (
        <div className="grid place-items-center py-32 text-muted-foreground">
          <Spinner width={28} height={28} />
        </div>
      ) : error ? (
        <div className="py-32 text-center text-sm text-[var(--color-danger-fg)]">{error}</div>
      ) : cards.length === 0 ? (
        <div className="py-32 text-center text-sm text-muted-foreground">
          표시할 상품이 없습니다.
        </div>
      ) : (
        <>
          <div className="flex items-center justify-between pt-8">
            <p className="text-xs uppercase tracking-[0.12em] text-muted-foreground">
              {cards.length}개 · 최신 등록순
            </p>
            <p className="text-xs uppercase tracking-[0.12em] text-muted-foreground">
              {page + 1} / {totalPages}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-x-6 gap-y-12 pt-6 md:grid-cols-3 lg:grid-cols-4">
            {pageCards.map((c) => (
              <ShowroomCardView key={c.key} card={c} />
            ))}
          </div>

          {totalPages > 1 && (
            <Pager page={page} totalPages={totalPages} onGo={goPage} />
          )}
        </>
      )}

      {toast && (
        <div className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-[var(--radius)] bg-ink px-5 py-3 text-sm font-medium text-white shadow-[var(--shadow-lg)]">
          {toast}
        </div>
      )}
    </div>
  );
}

/* ── 카드: (상품 × 색상) 1장, 사이즈는 카드 안에 재고 표 ───────────────────
   기획 5필드: 품번 · 이미지 · 색상 · 재고(사이즈별) · 도매가. */
function ShowroomCardView({ card }: { card: ShowroomCard }) {
  return (
    <div className={`flex flex-col ${card.soldOut ? "opacity-60" : ""}`}>
      {/* 이미지 (색상별 이미지 데이터는 없어 상품 대표 이미지 공유) */}
      <div className="relative aspect-[4/5] w-full overflow-hidden bg-subtle">
        {card.image ? (
          // 외부(Supabase Storage) 공개 URL → next/image 원격 설정 불필요한 plain img.
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={card.image}
            alt={card.item_name}
            className="h-full w-full object-cover"
            loading="lazy"
          />
        ) : (
          <div className="grid h-full w-full place-items-center text-border-strong">
            <ImageIcon width={32} height={32} />
          </div>
        )}

        {card.soldOut && (
          <div className="absolute inset-0 grid place-items-center bg-canvas/40">
            <span className="font-serif text-3xl italic tracking-wide text-foreground">
              SOLD OUT
            </span>
          </div>
        )}
      </div>

      {/* 품번 + 도매가 */}
      <div className="mt-4 flex items-baseline justify-between gap-2">
        <span className="truncate text-xs font-medium uppercase tracking-[0.1em] text-muted-foreground">
          {card.pnum}
        </span>
        <span className="shrink-0 text-sm font-bold text-foreground">{priceLabel(card.price)}</span>
      </div>

      {/* 상품명(보조) */}
      <h3 className="mt-1.5 truncate text-sm font-semibold leading-snug text-foreground">
        {card.item_name}
      </h3>

      {/* 색상 — 컬러칩 + 색상명 */}
      <div className="mt-1 flex items-center gap-1.5">
        <ColorChip name={card.color} />
        <span className="text-xs uppercase tracking-[0.1em] text-muted-foreground">{card.color}</span>
      </div>

      {/* 혼용률(상품 공통) */}
      {card.fabric && (
        <p
          className="mt-1.5 line-clamp-2 text-[11px] leading-snug text-muted-foreground"
          title={card.fabric}
        >
          <span className="text-border-strong">혼용률</span> {card.fabric}
        </p>
      )}

      {/* 사이즈별 재고 · 예약 (예약 = 재고 음수분: stock -1 → 재고 0 / 예약 1) */}
      <div className="mt-3 border-t border-divider pt-2.5">
        <div className="grid grid-cols-[1fr_auto_auto] items-center gap-x-4 text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
          <span>사이즈</span>
          <span className="w-7 text-right">재고</span>
          <span className="w-7 text-right">예약</span>
        </div>
        <ul className="mt-1.5 space-y-1">
          {card.sizes.map((s) => {
            const out = s.available <= 0;
            const low = !out && s.available <= 3;
            return (
              <li
                key={s.size}
                className="grid grid-cols-[1fr_auto_auto] items-center gap-x-4 text-sm tabular-nums"
              >
                <span className="font-medium uppercase text-foreground">{s.size}</span>
                <span
                  className={`w-7 text-right ${
                    out
                      ? "font-semibold text-border-strong"
                      : low
                        ? "font-bold text-[var(--color-danger-fg)]"
                        : "font-semibold text-foreground"
                  }`}
                >
                  {s.available}
                </span>
                <span
                  className={`w-7 text-right ${
                    s.committed > 0
                      ? "font-bold text-[var(--color-warning-fg)]"
                      : "font-medium text-border-strong"
                  }`}
                >
                  {s.committed}
                </span>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}

/* ── 컬러칩 — 색상명 → 스와치. 미매핑이면 점선 칩(색은 모르지만 표식). ──────── */
function ColorChip({ name }: { name: string }) {
  const sw = colorSwatch(name);
  if (!sw) {
    return (
      <span
        aria-hidden
        className="inline-block size-3.5 shrink-0 rounded-full border border-dashed border-border-strong"
        title={`${name} (색상 미정의)`}
      />
    );
  }
  return (
    <span
      aria-hidden
      title={name}
      className="inline-block size-3.5 shrink-0 rounded-full"
      // 밝은 색(흰색/아이보리 등)은 흰 배경에서 안 보이니 inset 테두리로 윤곽.
      style={{
        backgroundColor: sw.hex,
        boxShadow: sw.light ? "inset 0 0 0 1px var(--color-border)" : undefined,
      }}
    />
  );
}

/* ── 페이저 (‹ 1 2 … N ›) ───────────────────────────────────────────────── */
function Pager({
  page,
  totalPages,
  onGo,
}: {
  page: number; // 0-indexed
  totalPages: number;
  onGo: (n: number) => void;
}) {
  return (
    <nav className="mt-14 flex items-center justify-center gap-1.5" aria-label="페이지">
      <PagerArrow disabled={page === 0} onClick={() => onGo(page - 1)} label="이전">
        <ChevronLeft width={16} height={16} />
      </PagerArrow>
      {buildPages(page, totalPages).map((p, i) =>
        p === "…" ? (
          <span key={`e${i}`} className="px-2 text-sm text-muted-foreground">
            …
          </span>
        ) : (
          <button
            key={p}
            type="button"
            onClick={() => onGo(p - 1)}
            aria-current={p - 1 === page ? "page" : undefined}
            className={`grid size-9 place-items-center text-sm tabular-nums transition ${
              p - 1 === page
                ? "bg-ink font-bold text-white"
                : "font-medium text-muted-foreground hover:bg-subtle hover:text-foreground"
            }`}
          >
            {p}
          </button>
        )
      )}
      <PagerArrow
        disabled={page >= totalPages - 1}
        onClick={() => onGo(page + 1)}
        label="다음"
      >
        <ChevronRight width={16} height={16} />
      </PagerArrow>
    </nav>
  );
}

function PagerArrow({
  disabled,
  onClick,
  label,
  children,
}: {
  disabled: boolean;
  onClick: () => void;
  label: string;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      className="grid size-9 place-items-center text-foreground transition hover:bg-subtle disabled:cursor-not-allowed disabled:opacity-30"
    >
      {children}
    </button>
  );
}

/** 현재 페이지(0-indexed) 기준 1-indexed 페이지 라벨 윈도우(… 생략 포함). */
function buildPages(current0: number, total: number): (number | "…")[] {
  const c = current0 + 1;
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const keep = [1, total, c, c - 1, c + 1].filter((n) => n >= 1 && n <= total);
  const sorted = [...new Set(keep)].sort((a, b) => a - b);
  const out: (number | "…")[] = [];
  for (let i = 0; i < sorted.length; i++) {
    if (i > 0 && sorted[i] - sorted[i - 1] > 1) out.push("…");
    out.push(sorted[i]);
  }
  return out;
}
