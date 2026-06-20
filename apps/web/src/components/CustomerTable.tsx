"use client";

import { useMemo, useState } from "react";
import {
  type Customer,
  disconnectCustomer,
  type ManagedWholesaler,
  PRICE_VIS_LABEL,
  reconnectCustomer,
  ROLE_LABEL,
  SELLER_TYPE_LABEL,
  setCustomerPriceVisibility,
} from "@/lib/products";
import { Badge, Button, Dialog, Select } from "@/components/ui";
import { Search, Spinner } from "@/components/icons";

// 매칭 모델: 테넌트 안 모든 소매↔도매 '기본 연결'. 관리자가 특정 쌍을 '취소'(excluded_wholesaler_ids).
// 등급(tier)은 1차 화면 제외(주문 기능 없어 기준 없음). 2차 자동등급으로 부활.
const VIS_OPTS = [
  { value: "wholesale", label: "도매가" },
  { value: "retail", label: "판매가" },
  { value: "none", label: "미노출" },
];

const STATUS_BADGE: Record<string, { label: string; tone: "warning" | "success" | "danger" | "neutral" }> = {
  pending: { label: "대기", tone: "warning" },
  approved: { label: "승인", tone: "success" },
  rejected: { label: "거절", tone: "danger" },
  suspended: { label: "정지", tone: "neutral" },
};

const visTone = (v: string | null) => (v === "none" || v == null ? "neutral" : "success");
const visText = (v: string | null) => (v == null ? "기본" : PRICE_VIS_LABEL[v] ?? v);

function fmtDate(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return isNaN(d.getTime())
    ? "—"
    : d.toLocaleDateString("ko-KR", { year: "2-digit", month: "2-digit", day: "2-digit" });
}

/**
 * 소매(거래처) 목록 테이블 — 도매/도매관리자 공용.
 * - role="wholesaler": 나와 연결된 소매(테넌트 전체 − 취소). 가격노출 편집.
 * - role="admin": 테넌트 전체 소매. + 연결 도매 컬럼 + 매칭 취소/복원(wholesalers 필요).
 * 등급·주문·미수금·정산은 1차 제외(Phase 2).
 */
export function CustomerTable({
  rows,
  role,
  wholesalers = [],
  loading,
  error,
  onChanged,
}: {
  rows: Customer[];
  role: "admin" | "wholesaler";
  wholesalers?: ManagedWholesaler[];
  loading?: boolean;
  error?: string | null;
  onChanged: () => void;
}) {
  const [q, setQ] = useState("");
  const [detailId, setDetailId] = useState<string | null>(null);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return rows;
    return rows.filter((c) =>
      `${c.company_name ?? ""}${c.full_name ?? ""}${c.email ?? ""}`.toLowerCase().includes(needle)
    );
  }, [rows, q]);

  const detail = detailId ? rows.find((c) => c.id === detailId) ?? null : null;
  const colCount = role === "admin" ? 5 : 4;

  return (
    <div className="flex flex-col gap-4">
      {/* 검색 */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative ml-auto w-full max-w-xs">
          <Search
            width={16}
            height={16}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-border-strong"
          />
          <input
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="거래처·담당자 검색…"
            className="w-full rounded-[var(--radius)] border border-border bg-subtle py-2 pl-9 pr-3 text-sm text-foreground outline-none transition placeholder:text-placeholder focus:border-ink focus:ring-2 focus:ring-ink/15"
          />
        </div>
      </div>

      <div className="overflow-x-auto rounded-[var(--radius-lg)] border border-divider bg-surface">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead>
            <tr className="border-b border-divider bg-subtle text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              <th className="px-5 py-3">거래처</th>
              <th className="px-5 py-3">담당자</th>
              <th className="px-5 py-3 text-center">가격 노출</th>
              {role === "admin" && <th className="px-5 py-3 text-center">연결 도매</th>}
              <th className="px-5 py-3 text-center">가입상태</th>
              <th className="px-5 py-3 text-right" />
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={colCount} className="py-16 text-center">
                  <Spinner width={22} height={22} className="mx-auto text-muted-foreground" />
                </td>
              </tr>
            ) : error ? (
              <tr>
                <td colSpan={colCount} className="py-12 text-center text-sm text-[var(--color-danger-fg)]">
                  {error}
                </td>
              </tr>
            ) : filtered.length === 0 ? (
              <tr>
                <td colSpan={colCount} className="py-16 text-center text-sm text-muted-foreground">
                  조건에 맞는 거래처가 없습니다.
                </td>
              </tr>
            ) : (
              filtered.map((c) => {
                const st = STATUS_BADGE[c.status] ?? { label: c.status, tone: "neutral" as const };
                const name = c.company_name || c.full_name || c.email || "—";
                const excluded = c.excluded_wholesaler_ids?.length ?? 0;
                const connected = Math.max(0, wholesalers.length - excluded);
                return (
                  <tr key={c.id} className="border-b border-divider/70 last:border-0 hover:bg-canvas">
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-3">
                        <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-subtle text-sm font-bold text-[var(--color-text-secondary)]">
                          {name.slice(0, 1)}
                        </span>
                        <span className="font-semibold text-foreground">{name}</span>
                      </div>
                    </td>
                    <td className="px-5 py-3.5 text-[var(--color-text-secondary)]">{c.full_name ?? "—"}</td>
                    <td className="px-5 py-3.5 text-center">
                      <Badge tone={visTone(c.price_visibility)}>{visText(c.price_visibility)}</Badge>
                    </td>
                    {role === "admin" && (
                      <td className="px-5 py-3.5 text-center text-[var(--color-text-secondary)]">
                        <span className="tabular-nums">{connected}곳</span>
                        {excluded > 0 && (
                          <span className="ml-1.5 text-xs text-muted-foreground">({excluded} 취소)</span>
                        )}
                      </td>
                    )}
                    <td className="px-5 py-3.5 text-center">
                      <Badge tone={st.tone}>{st.label}</Badge>
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      <Button
                        variant="secondary"
                        onClick={() => setDetailId(c.id)}
                        className="px-3 py-2 text-xs"
                      >
                        상세
                      </Button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      <CustomerDetailDialog
        customer={detail}
        role={role}
        wholesalers={wholesalers}
        onClose={() => setDetailId(null)}
        onChanged={onChanged}
      />
    </div>
  );
}

/** 거래처 상세 — 기본정보 + 가격노출 편집 + (admin) 도매 연결/취소. 등급·주문·미수금·정산 없음(1차). */
function CustomerDetailDialog({
  customer,
  role,
  wholesalers,
  onClose,
  onChanged,
}: {
  customer: Customer | null;
  role: "admin" | "wholesaler";
  wholesalers: ManagedWholesaler[];
  onClose: () => void;
  onChanged: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  if (!customer) return null;
  const c = customer;
  const name = c.company_name || c.full_name || c.email || "—";
  const excludedSet = new Set(c.excluded_wholesaler_ids ?? []);

  async function run(fn: () => Promise<unknown>) {
    setBusy(true);
    setErr(null);
    try {
      await fn();
      onChanged();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "처리에 실패했습니다.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={!!customer} onClose={onClose} title={name} size="md">
      <div className="flex flex-col gap-6">
        {/* 기본 정보 */}
        <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
          <Info label="이메일" value={c.email} />
          <Info label="담당자" value={c.full_name} />
          <Info label="역할" value={ROLE_LABEL[c.role] ?? c.role} />
          <Info
            label="유형"
            value={c.seller_type ? SELLER_TYPE_LABEL[c.seller_type] ?? c.seller_type : "—"}
          />
          <Info label="가입일" value={fmtDate(c.created_at)} />
          <Info label="가입상태" value={STATUS_BADGE[c.status]?.label ?? c.status} />
        </dl>

        {/* 가격 노출 */}
        <Select
          label="가격 노출"
          value={c.price_visibility ?? ""}
          placeholder="기본(자동)"
          options={VIS_OPTS}
          disabled={busy}
          onChange={(e) => e.target.value && run(() => setCustomerPriceVisibility(c.id, e.target.value))}
        />

        {/* (admin) 도매 연결/취소 — 기본 전부 연결, 거래 안 할 도매만 취소 */}
        {role === "admin" && (
          <div className="flex flex-col gap-2.5">
            <span className="text-sm font-semibold text-[var(--color-text-secondary)]">
              거래 도매 (기본 전부 연결 — 거래 안 할 곳만 취소)
            </span>
            {wholesalers.length === 0 ? (
              <span className="text-sm text-muted-foreground">등록된 도매업체가 없습니다.</span>
            ) : (
              <div className="flex flex-col divide-y divide-divider rounded-[var(--radius)] border border-border">
                {wholesalers.map((w) => {
                  const off = excludedSet.has(w.id);
                  return (
                    <div key={w.id} className="flex items-center gap-3 px-3.5 py-2.5">
                      <span className={`text-sm ${off ? "text-muted-foreground line-through" : "font-medium text-foreground"}`}>
                        {w.name}
                      </span>
                      <Badge tone={off ? "neutral" : "success"} className="ml-1">
                        {off ? "취소됨" : "연결됨"}
                      </Badge>
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() =>
                          run(() => (off ? reconnectCustomer(c.id, w.id) : disconnectCustomer(c.id, w.id)))
                        }
                        className="ml-auto rounded-[var(--radius)] border border-border px-2.5 py-1.5 text-xs font-semibold text-foreground transition hover:bg-subtle disabled:opacity-50"
                      >
                        {off ? "복원" : "취소"}
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {err && <p className="text-sm text-[var(--color-danger-fg)]">{err}</p>}
        <p className="text-xs text-muted-foreground">거래처의 기본 정보와 가격 노출을 관리합니다.</p>
      </div>
    </Dialog>
  );
}

function Info({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="font-medium text-foreground">{value || "—"}</dd>
    </div>
  );
}
