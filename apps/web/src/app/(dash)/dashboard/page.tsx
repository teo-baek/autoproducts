import { ComingSoon } from "@/components/ComingSoon";
import { Dashboard } from "@/components/icons";

export default function DashboardPage() {
  return (
    <ComingSoon
      title="대시보드"
      description="매출·주문·재고 KPI와 차트를 한눈에 보는 대시보드입니다. 1차 개발에서는 상품 관리에 집중하며, 이후 단계에서 제공됩니다."
      icon={<Dashboard width={28} height={28} />}
    />
  );
}
