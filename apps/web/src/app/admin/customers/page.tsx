"use client";
/* eslint-disable react-hooks/set-state-in-effect -- 서버 데이터 동기화 목적의 의도된 effect */

import { useCallback, useEffect, useState } from "react";
import { CustomerTable } from "@/components/CustomerTable";
import {
  type Customer,
  listCustomers,
  listManagedWholesalers,
  type ManagedWholesaler,
} from "@/lib/products";
import { Spinner } from "@/components/icons";

const TABS = [
  { value: "customers", label: "소매 거래처" },
  { value: "wholesalers", label: "도매업체" },
];

function fmtDate(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return isNaN(d.getTime())
    ? "—"
    : d.toLocaleDateString("ko-KR", { year: "2-digit", month: "2-digit", day: "2-digit" });
}

/** 도매관리자 고객관리 — 도매업체 + 소매 거래처 둘 다(테넌트 전체). 소매를 도매에 배정. */
export default function AdminCustomersPage() {
  const [tab, setTab] = useState("customers");
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [wholesalers, setWholesalers] = useState<ManagedWholesaler[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [cs, ws] = await Promise.all([listCustomers(), listManagedWholesalers()]);
      setCustomers(cs);
      setWholesalers(ws);
    } catch (e) {
      setError(e instanceof Error ? e.message : "불러오기 실패");
      setCustomers([]);
      setWholesalers([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="mx-auto max-w-6xl">
      <h1 className="text-2xl font-extrabold tracking-tight text-foreground">고객 관리</h1>
      <p className="mt-1.5 text-sm text-muted-foreground">
        도매업체와 소매 거래처를 함께 관리합니다. 소매를 도매에 배정하면 해당 도매의 고객 목록에 나타납니다.
      </p>

      <div className="mt-6 flex gap-1.5">
        {TABS.map((t) => (
          <button
            key={t.value}
            type="button"
            onClick={() => setTab(t.value)}
            className={`rounded-full px-4 py-1.5 text-sm font-medium transition ${
              tab === t.value
                ? "bg-ink text-white"
                : "border border-border text-muted-foreground hover:bg-subtle hover:text-foreground"
            }`}
          >
            {t.label}
            {t.value === "wholesalers" && wholesalers.length > 0 && (
              <span className="ml-1.5 text-xs opacity-70">{wholesalers.length}</span>
            )}
          </button>
        ))}
      </div>

      <div className="mt-5">
        {tab === "customers" ? (
          <CustomerTable
            rows={customers}
            role="admin"
            wholesalers={wholesalers}
            loading={loading}
            error={error}
            onChanged={load}
          />
        ) : (
          <WholesalerList rows={wholesalers} loading={loading} error={error} />
        )}
      </div>
    </div>
  );
}

/** 도매업체 목록 — 이름/사업자번호/등록일/배정 소매 수. (도매관리자 전용) */
function WholesalerList({
  rows,
  loading,
  error,
}: {
  rows: ManagedWholesaler[];
  loading?: boolean;
  error?: string | null;
}) {
  return (
    <div className="overflow-x-auto rounded-[var(--radius-lg)] border border-divider bg-surface">
      <table className="w-full min-w-[640px] text-left text-sm">
        <thead>
          <tr className="border-b border-divider bg-subtle text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            <th className="px-5 py-3">도매업체</th>
            <th className="px-5 py-3">사업자번호</th>
            <th className="px-5 py-3">등록일</th>
            <th className="px-5 py-3 text-right">연결 소매</th>
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <tr>
              <td colSpan={4} className="py-16 text-center">
                <Spinner width={22} height={22} className="mx-auto text-muted-foreground" />
              </td>
            </tr>
          ) : error ? (
            <tr>
              <td colSpan={4} className="py-12 text-center text-sm text-[var(--color-danger-fg)]">
                {error}
              </td>
            </tr>
          ) : rows.length === 0 ? (
            <tr>
              <td colSpan={4} className="py-16 text-center text-sm text-muted-foreground">
                소속 도매업체가 없습니다.
              </td>
            </tr>
          ) : (
            rows.map((w) => (
              <tr key={w.id} className="border-b border-divider/70 last:border-0 hover:bg-canvas">
                <td className="px-5 py-3.5 font-semibold text-foreground">{w.name}</td>
                <td className="px-5 py-3.5 text-[var(--color-text-secondary)]">{w.biz_number ?? "—"}</td>
                <td className="px-5 py-3.5 text-muted-foreground">{fmtDate(w.created_at)}</td>
                <td className="px-5 py-3.5 text-right font-semibold tabular-nums text-foreground">
                  {w.connected_count}곳
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
