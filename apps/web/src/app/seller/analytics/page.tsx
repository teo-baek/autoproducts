import { ComingSoon } from "@/components/ComingSoon";
import { Dashboard } from "@/components/icons";

/** 셀러 통계(ANALYTICS) — 준비 중(Phase 2). 도매 카탈로그/주문과 동일한 플레이스홀더. */
export default function SellerAnalyticsPage() {
  return (
    <ComingSoon
      title="통계"
      description="판매·재고 추이 등 셀러용 분석 대시보드입니다. 1차 개발 범위 외이며, 이후 단계에서 제공됩니다."
      icon={<Dashboard width={28} height={28} />}
    />
  );
}
