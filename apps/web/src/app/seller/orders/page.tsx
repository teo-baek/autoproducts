import { ComingSoon } from "@/components/ComingSoon";
import { Cart } from "@/components/icons";

/** 셀러 주문(ORDERS) — 준비 중(Phase 2). 도매 주문관리와 동일한 플레이스홀더. */
export default function SellerOrdersPage() {
  return (
    <ComingSoon
      title="주문"
      description="셀러가 발주·주문 현황을 관리하는 화면입니다. 1차 개발 범위 외이며, 이후 단계에서 제공됩니다."
      icon={<Cart width={28} height={28} />}
    />
  );
}
