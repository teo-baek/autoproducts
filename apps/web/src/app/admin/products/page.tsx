"use client";
/* eslint-disable react-hooks/set-state-in-effect -- 서버 데이터 동기화 목적의 의도된 effect */

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { listAdminProducts, won, type AdminProduct } from "@/lib/products";
import { Badge, Card } from "@/components/ui";
import { Box, ChevronLeft, ChevronRight, Search, Spinner } from "@/components/icons";

const STATUS_TABS = [
  { value: "", label: "전체" },
  { value: "active", label: "판매중" },
  { value: "archived", label: "보관" },
];
const PAGE = 30;

/** SKU 가격 범위(최저~최고). admin 은 도매가/판매가 둘 다 본다(FR-5/FR-8). */
function priceRange(p: AdminProduct, key: "wholesale_price" | "retail_price"): string {
  const vals = p.skus.map((s) => s[key]).filter((n): n is number => n != null);
  if (!vals.length) return "—";
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  return min === max ? won(min) : `${won(min)}~${won(max)}`;
}
function optionSummary(p: AdminProduct): string {
  const colors = new Set(p.skus.map((s) => s.color)).size;
  const sizes = new Set(p.skus.map((s) => s.size)).size;
  return `${colors}색 · ${sizes}사이즈`;
}

export default function AdminProductsPage() {
  const [tab, setTab] = useState("");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [rows, setRows] = useState<AdminProduct[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
      <h1 className="text-2xl font-extrabold tracking-tight text-foreground">상품 관리</h1>
      <p className="mt-1.5 text-sm text-muted-foreground">
        소속 도매업체 전체의 상품을 합산해 보여줍니다. 행마다 어느 도매 것인지 표시됩니다.
      </p>

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
                <th className="px-5 py-3">품번</th>
                <th className="px-5 py-3">상품명</th>
                <th className="px-5 py-3">도매 출처</th>
                <th className="px-5 py-3">옵션</th>
                <th className="px-5 py-3 text-right">도매가</th>
                <th className="px-5 py-3 text-right">판매가</th>
                <th className="px-5 py-3 text-center">상태</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7} className="py-16 text-center">
                    <Spinner width={22} height={22} className="mx-auto text-muted-foreground" />
                  </td>
                </tr>
              ) : error ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-sm text-[var(--color-danger-fg)]">
                    {error}
                  </td>
                </tr>
              ) : rows.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-16 text-center text-sm text-muted-foreground">
                    상품이 없습니다.
                  </td>
                </tr>
              ) : (
                rows.map((p) => (
                  <tr key={p.id} className="border-b border-divider/70 last:border-0 hover:bg-canvas">
                    <td className="px-5 py-3.5 font-mono text-xs text-muted-foreground">{p.source_p_number}</td>
                    <td className="px-5 py-3.5 font-medium text-foreground">{p.item_name}</td>
                    <td className="px-5 py-3.5">
                      <span className="inline-flex items-center gap-1.5 text-[var(--color-text-secondary)]">
                        <Box width={14} height={14} className="text-muted-foreground" />
                        {p.wholesaler_name ?? "—"}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-[var(--color-text-secondary)]">{optionSummary(p)}</td>
                    <td className="px-5 py-3.5 text-right font-medium text-foreground">
                      {priceRange(p, "wholesale_price")}
                    </td>
                    <td className="px-5 py-3.5 text-right text-[var(--color-text-secondary)]">
                      {priceRange(p, "retail_price")}
                    </td>
                    <td className="px-5 py-3.5 text-center">
                      <Badge tone={p.status === "active" ? "success" : "neutral"}>
                        {p.status === "active" ? "판매중" : "보관"}
                      </Badge>
                    </td>
                  </tr>
                ))
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
    </div>
  );
}
