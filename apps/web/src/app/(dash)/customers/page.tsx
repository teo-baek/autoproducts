import { ComingSoon } from "@/components/ComingSoon";
import { Users } from "@/components/icons";

export default function CustomersPage() {
  return (
    <ComingSoon
      title="고객 관리"
      description="거래 셀러·에이전시 등 고객 계정을 관리하는 화면입니다. 1차 개발 범위 외이며, 이후 단계에서 제공됩니다."
      icon={<Users width={28} height={28} />}
    />
  );
}
