import { ComingSoon } from "@/components/ComingSoon";
import { Book } from "@/components/icons";

export default function CatalogPage() {
  return (
    <ComingSoon
      title="카탈로그 관리"
      description="역할별 가격이 적용된 폐쇄형 카탈로그와 QR 카드를 구성·배포하는 화면입니다. 이후 단계에서 제공됩니다."
      icon={<Book width={28} height={28} />}
    />
  );
}
