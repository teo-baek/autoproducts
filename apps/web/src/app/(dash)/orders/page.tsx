import { ComingSoon } from "@/components/ComingSoon";
import { Cart } from "@/components/icons";

export default function OrdersPage() {
  return (
    <ComingSoon
      title="주문 관리"
      description="주문 접수·처리·배송 상태를 관리하는 화면입니다. 주문/결제/배송은 Phase 2 범위로, 이후 단계에서 제공됩니다."
      icon={<Cart width={28} height={28} />}
    />
  );
}
