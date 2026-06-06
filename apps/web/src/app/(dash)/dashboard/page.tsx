"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { listJobs, listProducts, type Job } from "@/lib/products";
import { Badge, Button, Card } from "@/components/ui";
import { Box, FileUp, ImageIcon, Spinner, Table as TableIcon } from "@/components/icons";

type Stats = { total: number; archived: number; jobs: Job[] };

const JOB_STATUS: Record<string, { label: string; tone: "success" | "warning" | "danger" | "info" | "neutral" }> = {
  completed: { label: "완료", tone: "success" },
  needs_matching: { label: "매칭 대기", tone: "warning" },
  failed: { label: "실패", tone: "danger" },
  uploaded: { label: "처리 중", tone: "info" },
  parsing: { label: "처리 중", tone: "info" },
};

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleString("ko-KR", {
    year: "2-digit",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      listProducts({ limit: 1 }),
      listProducts({ limit: 1, status: "archived" }),
      listJobs(),
    ])
      .then(([all, arch, jobs]) =>
        setStats({ total: all.total, archived: arch.total, jobs: jobs.jobs })
      )
      .catch((e) => setError(e instanceof Error ? e.message : "불러오기 실패"));
  }, []);

  return (
    <div className="mx-auto max-w-6xl">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-foreground">대시보드</h1>
          <p className="mt-1.5 text-sm text-muted-foreground">
            상품 현황과 최근 제품 업로드 내역을 한눈에 확인하세요.
          </p>
        </div>
        <Link href="/products/bulk">
          <Button>
            <FileUp width={16} height={16} /> 대량 등록
          </Button>
        </Link>
      </div>

      {error ? (
        <Card className="mt-6 px-6 py-16 text-center text-sm text-[var(--color-danger-fg)]">{error}</Card>
      ) : !stats ? (
        <div className="mt-20 text-center">
          <Spinner width={26} height={26} className="mx-auto text-muted-foreground" />
        </div>
      ) : (
        <>
          {/* KPI */}
          <div className="mt-6 grid gap-4 sm:grid-cols-3">
            <Kpi icon={<Box width={20} height={20} />} label="등록 상품" value={stats.total} unit="건" />
            <Kpi
              icon={<TableIcon width={20} height={20} />}
              label="보관 상품"
              value={stats.archived}
              unit="건"
            />
            <Kpi
              icon={<ImageIcon width={20} height={20} />}
              label="최근 업로드 작업"
              value={stats.jobs.length}
              unit="건"
            />
          </div>

          {/* 제품 업로드 내역 */}
          <Card className="mt-6">
            <div className="flex items-center justify-between border-b border-divider px-5 py-4">
              <h2 className="text-sm font-bold text-foreground">제품 업로드 내역</h2>
              <Link href="/products" className="text-xs font-semibold text-ink hover:underline">
                상품 관리로 →
              </Link>
            </div>
            {stats.jobs.length === 0 ? (
              <div className="px-5 py-16 text-center">
                <div className="text-sm font-semibold text-foreground">업로드 내역이 없습니다</div>
                <p className="mt-1 text-sm text-muted-foreground">
                  대량 등록 마법사로 첫 일괄 업로드를 진행해 보세요.
                </p>
                <Link href="/products/bulk" className="mt-5 inline-block">
                  <Button variant="secondary">대량 등록 시작</Button>
                </Link>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px] text-left text-sm">
                  <thead>
                    <tr className="border-b border-divider text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      <th className="px-5 py-3">파일</th>
                      <th className="px-5 py-3 text-center">상태</th>
                      <th className="px-5 py-3 text-right">처리 행</th>
                      <th className="px-5 py-3 text-right">매칭 이미지</th>
                      <th className="px-5 py-3 text-right">오류</th>
                      <th className="px-5 py-3 text-right">일시</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stats.jobs.map((j) => {
                      const st = JOB_STATUS[j.status] ?? { label: j.status, tone: "neutral" as const };
                      return (
                        <tr key={j.id} className="border-b border-divider/70 last:border-0 hover:bg-canvas">
                          <td className="px-5 py-3.5 font-medium text-foreground">
                            {j.file_path ?? "(파일명 없음)"}
                          </td>
                          <td className="px-5 py-3.5 text-center">
                            <Badge tone={st.tone}>{st.label}</Badge>
                          </td>
                          <td className="px-5 py-3.5 text-right tabular-nums text-[var(--color-text-secondary)]">
                            {j.total_rows}
                          </td>
                          <td className="px-5 py-3.5 text-right tabular-nums text-[var(--color-text-secondary)]">
                            {j.matched_rows}
                          </td>
                          <td
                            className={`px-5 py-3.5 text-right tabular-nums font-semibold ${
                              j.error_rows > 0 ? "text-[var(--color-danger-fg)]" : "text-muted-foreground"
                            }`}
                          >
                            {j.error_rows}
                          </td>
                          <td className="px-5 py-3.5 text-right text-muted-foreground">{fmtDate(j.created_at)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  );
}

function Kpi({
  icon,
  label,
  value,
  unit,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  unit: string;
}) {
  return (
    <Card className="flex items-center gap-4 px-5 py-5">
      <span className="flex size-11 shrink-0 items-center justify-center rounded-[var(--radius)] bg-subtle text-foreground">
        {icon}
      </span>
      <div>
        <div className="text-sm text-muted-foreground">{label}</div>
        <div className="mt-0.5 text-2xl font-extrabold tabular-nums text-foreground">
          {value.toLocaleString("ko-KR")}
          <span className="ml-1 text-sm font-semibold text-muted-foreground">{unit}</span>
        </div>
      </div>
    </Card>
  );
}
