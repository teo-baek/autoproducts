"use client";
/* eslint-disable react-hooks/set-state-in-effect -- 서버 데이터 동기화 목적의 의도된 effect */

import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  aggregateSizes,
  colorSummary,
  downloadAdminProductsXlsx,
  isSoldOut,
  listAdminProducts,
  productThumb,
  repWholesale,
  won,
  type AdminProduct,
} from "@/lib/products";
import { ProductDetailModal } from "@/components/ProductDetailModal";
import { Badge, Button, Card } from "@/components/ui";
import { Box, ChevronLeft, ChevronRight, Download, ImageIcon, Search, Spinner } from "@/components/icons";

const STATUS_TABS = [
  { value: "", label: "전체" },
  { value: "active", label: "판매중" },
  { value: "archived", label: "보관" },
];
const PAGE = 30;

export default function AdminProductsPage() {
  const [tab, setTab] = useState("");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [rows, setRows] = useState<AdminProduct[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [detail, setDetail] = useState<AdminProduct | null>(null);   // 상세(읽기) 모달 대상
  const [downloading, setDownloading] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listAdminProducts({
        limit: PAGE,
        offset,
        search: query || undefined,
        status: tab || undefined,
      });
      setRows(res.items);
      setTotal(res.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : "불러오기 실패");
      setRows([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [tab, query, offset]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    // 다운로드 진행 중에는 "준비 중" 안내가 사라지지 않도록 자동 닫힘을 멈춘다.
    if (!toast || downloading) return;
    const t = setTimeout(() => setToast(null), 3500);
    return () => clearTimeout(t);
  }, [toast, downloading]);

  async function onExport() {
    if (downloading) return;
    setDownloading(true);
    setToast("엑셀을 준비하고 있습니다. 잠시만 기다려 주세요…");
    try {
      await downloadAdminProductsXlsx({ search: query || undefined, status: tab || undefined });
      setToast("엑셀 추출이 시작되었습니다.");
    } catch (e) {
      setToast(e instanceof Error ? e.message : "추출 실패");
    } finally {
      setDownloading(false);
    }
  }

  function submitSearch(e: FormEvent) {
    e.preventDefault();
    setOffset(0);
    setQuery(search.trim());
  }
  function changeTab(v: string) {
    setOffset(0);
    setTab(v);
  }

  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + PAGE, total);

  return (
    <div className="mx-auto max-w-6xl">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-foreground">상품 관리</h1>
          <p className="mt-1.5 text-sm text-muted-foreground">
            소속 도매업체 전체의 상품을 합산해 보여줍니다. 행마다 어느 도매 것인지 표시됩니다.
          </p>
        </div>
        <Button variant="secondary" loading={downloading} onClick={onExport}>
          {!downloading && <Download width={16} height={16} />}
          {downloading ? "추출 준비 중…" : "엑셀 추출하기"}
        </Button>
      </div>

      <Card className="mt-6">
        <div className="flex flex-wrap items-center gap-3 border-b border-divider px-5 py-3.5">
          <div className="flex items-center gap-1">
            {STATUS_TABS.map((t) => (
              <button
                key={t.value}
                type="button"
                onClick={() => changeTab(t.value)}
                className={`rounded-full px-3.5 py-1.5 text-sm font-medium transition ${
                  tab === t.value
                    ? "bg-ink text-white"
                    : "text-muted-foreground hover:bg-subtle hover:text-foreground"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
          <form onSubmit={submitSearch} className="ml-auto">
            <div className="relative">
              <Search
                width={15}
                height={15}
                className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
              />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="상품명·품번 검색"
                className="w-56 rounded-[var(--radius)] border border-divider bg-surface py-2 pl-9 pr-3 text-sm outline-none focus:border-foreground/30"
              />
            </div>
          </form>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[920px] text-left text-sm">
            <thead>
              <tr className="border-b border-divider text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <th className="px-5 py-3">제품이미지</th>
                <th className="px-5 py-3">품번</th>
                <th className="px-5 py-3">상품명</th>
                <th className="px-5 py-3">도매 출처</th>
                <th className="px-5 py-3">색상</th>
                <th className="px-5 py-3">상세사이즈</th>
                <th className="px-5 py-3">혼용률</th>
                <th className="px-5 py-3 text-right">도매가</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={8} className="py-16 text-center">
                    <Spinner width={22} height={22} className="mx-auto text-muted-foreground" />
                  </td>
                </tr>
              ) : error ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-sm text-[var(--color-danger-fg)]">
                    {error}
                  </td>
                </tr>
              ) : rows.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-16 text-center text-sm text-muted-foreground">
                    상품이 없습니다.
                  </td>
                </tr>
              ) : (
                rows.map((p) => {
                  const thumb = productThumb(p);
                  const colors = colorSummary(p);
                  return (
                    <tr
                      key={p.id}
                      onClick={() => setDetail(p)}
                      className="cursor-pointer border-b border-divider/70 last:border-0 hover:bg-canvas"
                    >
                      <td className="px-5 py-3.5">
                        <div className="flex size-12 items-center justify-center overflow-hidden rounded-[var(--radius)] bg-subtle text-border-strong">
                          {thumb ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img src={thumb} alt={p.item_name} className="h-full w-full object-cover" />
                          ) : (
                            <ImageIcon width={18} height={18} />
                          )}
                        </div>
                      </td>
                      <td className="px-5 py-3.5 font-mono text-xs text-muted-foreground">{p.source_p_number}</td>
                      <td className="px-5 py-3.5">
                        <div className="flex items-center gap-2 font-medium text-foreground">
                          {p.item_name}
                          {p.status === "archived" && <Badge tone="neutral">보관됨</Badge>}
                          {isSoldOut(p) && <Badge tone="danger">SOLD OUT</Badge>}
                        </div>
                      </td>
                      <td className="px-5 py-3.5">
                        <span className="inline-flex items-center gap-1.5 text-[var(--color-text-secondary)]">
                          <Box width={14} height={14} className="text-muted-foreground" />
                          {p.wholesaler_name ?? "—"}
                        </span>
                      </td>
                      <td className="px-5 py-3.5 text-[var(--color-text-secondary)]">
                        <span title={colors.more ? colors.full : undefined}>{colors.text}</span>
                      </td>
                      <td className="px-5 py-3.5 text-[var(--color-text-secondary)]">{aggregateSizes(p)}</td>
                      <td className="px-5 py-3.5 text-[var(--color-text-secondary)]">{p.fabric_composition ?? "—"}</td>
                      <td className="px-5 py-3.5 text-right font-bold tabular-nums text-foreground">
                        {won(repWholesale(p))}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {!loading && !error && total > 0 && (
          <div className="flex items-center justify-between border-t border-divider px-5 py-3.5 text-sm text-muted-foreground">
            <span>
              {from}–{to} / 총 {total}개
            </span>
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => setOffset(Math.max(0, offset - PAGE))}
                disabled={offset === 0}
                className="inline-flex items-center gap-1 rounded-[var(--radius)] px-3 py-1.5 font-medium transition enabled:hover:bg-subtle disabled:opacity-40"
              >
                <ChevronLeft width={15} height={15} /> 이전
              </button>
              <button
                type="button"
                onClick={() => setOffset(offset + PAGE)}
                disabled={to >= total}
                className="inline-flex items-center gap-1 rounded-[var(--radius)] px-3 py-1.5 font-medium transition enabled:hover:bg-subtle disabled:opacity-40"
              >
                다음 <ChevronRight width={15} height={15} />
              </button>
            </div>
          </div>
        )}
      </Card>

      {/* 상세(읽기) 모달 — 합산 목록에서 상품 클릭. 도매관리자는 타 도매 상품 편집 권한 없음 → 읽기 전용(onEdit 미전달) */}
      <ProductDetailModal
        product={detail}
        open={!!detail}
        onClose={() => setDetail(null)}
        wholesalerName={detail?.wholesaler_name}
      />

      {toast && (
        <div className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-[var(--radius)] bg-ink px-5 py-3 text-sm font-medium text-white shadow-[var(--shadow-lg)]">
          {toast}
        </div>
      )}
    </div>
  );
}
