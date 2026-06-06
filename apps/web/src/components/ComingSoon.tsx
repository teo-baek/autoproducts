import type { ReactNode } from "react";
import { Card } from "./ui";

/** 1차 미구현 메뉴(대시보드/고객/주문/카탈로그) 플레이스홀더 — "준비 중" 안내. */
export function ComingSoon({
  title,
  description,
  icon,
}: {
  title: string;
  description: string;
  icon?: ReactNode;
}) {
  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="text-2xl font-extrabold tracking-tight text-foreground">{title}</h1>
      <Card className="mt-6 grid place-items-center px-8 py-20 text-center">
        <div className="flex size-16 items-center justify-center rounded-full bg-surface-muted text-border-strong">
          {icon}
        </div>
        <h2 className="mt-6 text-xl font-bold text-foreground">준비 중입니다</h2>
        <p className="mt-2 max-w-md text-sm leading-relaxed text-muted-foreground">{description}</p>
        <span className="mt-5 inline-flex items-center gap-1.5 rounded-full bg-[var(--color-info-bg)] px-3 py-1 text-xs font-semibold text-[var(--color-info-fg)]">
          1차 개발 범위 외 · 추후 제공
        </span>
      </Card>
    </div>
  );
}
