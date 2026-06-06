"use client";
/* eslint-disable react-hooks/set-state-in-effect -- 서버 데이터/역할 동기화 목적의 의도된 effect */

import { useCallback, useEffect, useState } from "react";
import {
  approveAccount,
  getMe,
  listAccounts,
  rejectAccount,
  ROLE_LABEL,
  SELLER_TYPE_LABEL,
  type Account,
} from "@/lib/products";
import { ComingSoon } from "@/components/ComingSoon";
import { Badge, Button, Card } from "@/components/ui";
import { Check, Spinner, Users, X as XIcon } from "@/components/icons";

const STATUS_TABS = [
  { value: "pending", label: "승인 대기" },
  { value: "approved", label: "승인됨" },
  { value: "rejected", label: "거절됨" },
];
const STATUS_BADGE: Record<string, { label: string; tone: "warning" | "success" | "danger" | "neutral" }> = {
  pending: { label: "대기", tone: "warning" },
  approved: { label: "승인", tone: "success" },
  rejected: { label: "거절", tone: "danger" },
};

function fmtDate(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return isNaN(d.getTime())
    ? "—"
    : d.toLocaleDateString("ko-KR", { year: "2-digit", month: "2-digit", day: "2-digit" });
}

export default function CustomersPage() {
  const [role, setRole] = useState<string | null>(null);

  useEffect(() => {
    getMe().then((me) => setRole(me.role)).catch(() => setRole(""));
  }, []);

  if (role === null) {
    return (
      <div className="mt-20 text-center">
        <Spinner width={26} height={26} className="mx-auto text-muted-foreground" />
      </div>
    );
  }
  if (role !== "admin") {
    return (
      <ComingSoon
        title="고객 관리"
        description="거래 셀러·에이전시 등 고객 계정을 관리하는 화면입니다. 1차 개발 범위 외이며, 이후 단계에서 제공됩니다."
        icon={<Users width={28} height={28} />}
      />
    );
  }
  return <AdminApprovals />;
}

/* ── 관리자: 가입 승인 관리 ─────────────────────────────────────────────── */
function AdminApprovals() {
  const [tab, setTab] = useState("pending");
  const [rows, setRows] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setRows(await listAccounts(tab));
    } catch (e) {
      setError(e instanceof Error ? e.message : "불러오기 실패");
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [tab]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3000);
    return () => clearTimeout(t);
  }, [toast]);

  async function act(a: Account, kind: "approve" | "reject") {
    setBusyId(a.id);
    try {
      if (kind === "approve") {
        await approveAccount(a.id);
        setToast(`'${a.company_name || a.full_name || a.id}' 계정을 승인했습니다.`);
      } else {
        await rejectAccount(a.id);
        setToast(`'${a.company_name || a.full_name || a.id}' 계정을 거절했습니다.`);
      }
      await load();
    } catch (e) {
      setToast(e instanceof Error ? e.message : "처리에 실패했습니다.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="text-2xl font-extrabold tracking-tight text-foreground">고객 관리 · 가입 승인</h1>
      <p className="mt-1.5 text-sm text-muted-foreground">
        도매·셀러 가입 신청을 검토하고 승인/거절하세요. 도매 승인 시 도매업체가 자동 생성·연결됩니다.
      </p>

      <Card className="mt-6">
        <div className="flex items-center gap-1 border-b border-divider px-5 py-3.5">
          {STATUS_TABS.map((t) => (
            <button
              key={t.value}
              type="button"
              onClick={() => setTab(t.value)}
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

        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead>
              <tr className="border-b border-divider text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <th className="px-5 py-3">회사명</th>
                <th className="px-5 py-3">담당자</th>
                <th className="px-5 py-3">역할</th>
                <th className="px-5 py-3">유형</th>
                <th className="px-5 py-3">신청일</th>
                <th className="px-5 py-3 text-center">상태</th>
                {tab === "pending" && <th className="px-5 py-3 text-right">작업</th>}
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
                    해당 상태의 계정이 없습니다.
                  </td>
                </tr>
              ) : (
                rows.map((a) => {
                  const st = STATUS_BADGE[a.status] ?? { label: a.status, tone: "neutral" as const };
                  return (
                    <tr key={a.id} className="border-b border-divider/70 last:border-0 hover:bg-canvas">
                      <td className="px-5 py-3.5 font-semibold text-foreground">{a.company_name ?? "—"}</td>
                      <td className="px-5 py-3.5 text-[var(--color-text-secondary)]">{a.full_name ?? "—"}</td>
                      <td className="px-5 py-3.5 text-[var(--color-text-secondary)]">{ROLE_LABEL[a.role] ?? a.role}</td>
                      <td className="px-5 py-3.5 text-[var(--color-text-secondary)]">
                        {a.seller_type ? (SELLER_TYPE_LABEL[a.seller_type] ?? a.seller_type) : "—"}
                      </td>
                      <td className="px-5 py-3.5 text-muted-foreground">{fmtDate(a.created_at)}</td>
                      <td className="px-5 py-3.5 text-center">
                        <Badge tone={st.tone}>{st.label}</Badge>
                      </td>
                      {tab === "pending" && (
                        <td className="px-5 py-3.5">
                          <div className="flex justify-end gap-2">
                            <Button
                              variant="secondary"
                              onClick={() => act(a, "reject")}
                              disabled={busyId === a.id}
                              className="px-3 py-2 text-xs"
                            >
                              <XIcon width={14} height={14} /> 거절
                            </Button>
                            <Button
                              onClick={() => act(a, "approve")}
                              loading={busyId === a.id}
                              className="px-3 py-2 text-xs"
                            >
                              <Check width={14} height={14} /> 승인
                            </Button>
                          </div>
                        </td>
                      )}
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {toast && (
        <div className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-[var(--radius)] bg-ink px-5 py-3 text-sm font-medium text-white shadow-[var(--shadow-lg)]">
          {toast}
        </div>
      )}
    </div>
  );
}
