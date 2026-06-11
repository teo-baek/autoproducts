"use client";
/* 상품 상세(읽기) 모달 — 목록에서 상품 클릭 시. 한 상품의 모든 SKU(색상×사이즈)를 표로 펼친다.
 * 정적 export 환경이라 /products/[id] 동적 경로 대신 인증 셸 안의 모달로 구현.
 * 데이터는 목록이 이미 들고 있는 Product(전체 skus 포함)를 그대로 사용 — 재요청 없음. */
import { useMemo, useState } from "react";
import { Badge, Button, Dialog } from "@/components/ui";
import { Box, Eye, ImageIcon, Pencil } from "@/components/icons";
import { API_BASE } from "@/lib/api";
import { isSoldOut, publicImageUrl, skuAvailable, skuReserved, won, type Product } from "@/lib/products";

type Props = {
  product: Product | null;
  open: boolean;
  onClose: () => void;
  onEdit: (p: Product) => void;
};

export function ProductDetailModal({ product, open, onClose, onEdit }: Props) {
  const [sel, setSel] = useState(0);
  // 상품이 바뀌면 갤러리 선택 초기화 — 렌더 중 상태 조정(React 권장 패턴, effect 불필요)
  const [seenId, setSeenId] = useState(product?.id);
  if (product?.id !== seenId) {
    setSeenId(product?.id);
    setSel(0);
  }

  const gallery = useMemo(() => {
    if (!product) return [];
    const urls = (product.images ?? []).map((im) => publicImageUrl(im.storage_path));
    if (urls.length === 0 && product.representative_image_url) urls.push(product.representative_image_url);
    return urls;
  }, [product]);

  if (!product) return null;

  // 색상 → 사이즈 순 정렬(색상별로 묶여 보이도록). 사이즈는 숫자 우선 자연정렬.
  const skus = [...product.skus].sort(
    (a, b) =>
      a.color.localeCompare(b.color, "ko") ||
      a.size.localeCompare(b.size, "ko", { numeric: true })
  );
  const wPrices = skus.map((s) => s.wholesale_price).filter((n): n is number => n != null);
  const priceRange = wPrices.length
    ? Math.min(...wPrices) === Math.max(...wPrices)
      ? won(wPrices[0])
      : `${won(Math.min(...wPrices))} ~ ${won(Math.max(...wPrices))}`
    : "—";
  const soldOut = isSoldOut(product);
  const availableTotal = skus.reduce((a, s) => a + skuAvailable(s), 0);
  const reservedTotal = skus.reduce((a, s) => a + skuReserved(s), 0);
  const main = gallery[sel] ?? null;
  const created = product.created_at
    ? new Date(product.created_at).toLocaleDateString("ko-KR")
    : "—";

  return (
    <Dialog
      open={open}
      onClose={onClose}
      size="lg"
      icon={<Box width={18} height={18} />}
      title="상품 상세"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            닫기
          </Button>
          <Button onClick={() => onEdit(product)}>
            <Pencil width={16} height={16} /> 상품 정보 수정
          </Button>
        </>
      }
    >
      {/* 상단: 이미지 갤러리 + 기본 정보 */}
      <div className="grid gap-7 md:grid-cols-[17rem_1fr]">
        <div>
          <div className="aspect-[4/5] w-full overflow-hidden rounded-[var(--radius-lg)] border border-divider bg-subtle">
            {main ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={main} alt={product.item_name} className="h-full w-full object-cover" />
            ) : (
              <div className="flex h-full w-full items-center justify-center text-border-strong">
                <ImageIcon width={30} height={30} />
              </div>
            )}
          </div>
          {gallery.length > 1 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {gallery.map((u, i) => (
                <button
                  key={`${u}-${i}`}
                  type="button"
                  onClick={() => setSel(i)}
                  className={`size-14 overflow-hidden rounded-[var(--radius)] border transition ${
                    i === sel ? "border-ink ring-2 ring-ink/15" : "border-border hover:border-border-strong"
                  }`}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={u} alt={`${product.item_name} ${i + 1}`} className="h-full w-full object-cover" />
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="min-w-0 space-y-5">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-xl font-bold tracking-tight text-foreground">{product.item_name}</h3>
              {product.status === "archived" && <Badge tone="neutral">보관됨</Badge>}
              {soldOut && <Badge tone="danger">SOLD OUT</Badge>}
            </div>
            <p className="mt-1.5 font-mono text-xs text-muted-foreground">
              품번 {product.source_p_number} · {product.platform_code}
            </p>
          </div>

          <dl className="grid grid-cols-2 gap-x-5 gap-y-3.5">
            <Field label="혼용률" value={product.fabric_composition} />
            <Field label="원산지" value={product.origin} />
            <Field label="작업기간" value={product.lead_time_days} />
            <Field label="등록일" value={created} />
          </dl>

          {product.description && (
            <div>
              <div className="mb-1.5 text-sm font-semibold text-[var(--color-text-secondary)]">설명</div>
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">{product.description}</p>
            </div>
          )}

          {/* QR / 공개 카드 */}
          <div className="flex items-center gap-4 rounded-[var(--radius-lg)] border border-divider bg-canvas p-3.5">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={`${API_BASE}/qr/${encodeURIComponent(product.platform_code)}.png`}
              alt={`${product.item_name} QR`}
              className="size-16 shrink-0 rounded-[var(--radius)] bg-white p-1"
            />
            <div className="min-w-0">
              <div className="text-sm font-semibold text-foreground">공개 QR 카드</div>
              <p className="mt-0.5 text-xs text-muted-foreground">스캔 시 제품 카드로 연결됩니다. 가격·재고는 로그인한 셀러에게만 역할별로 표시됩니다.</p>
              <a
                href={`/p?code=${encodeURIComponent(product.platform_code)}`}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-1.5 inline-flex items-center gap-1 text-xs font-semibold text-ink hover:underline"
              >
                <Eye width={13} height={13} /> 공개 카드 열기
              </a>
            </div>
          </div>
        </div>
      </div>

      {/* 옵션(SKU) — 한 상품의 모든 색상×사이즈 변형 */}
      <div className="mt-7">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <h4 className="text-sm font-bold text-foreground">옵션 (색상 × 사이즈)</h4>
          <Badge tone="neutral">{skus.length}개 변형</Badge>
          <span className="ml-auto flex items-center gap-4 text-xs text-muted-foreground">
            <span>
              가용 재고{" "}
              <strong className="tabular-nums text-foreground">
                {availableTotal.toLocaleString("ko-KR")}
              </strong>
            </span>
            {reservedTotal > 0 && (
              <span>
                예약{" "}
                <strong className="tabular-nums text-[var(--color-warning-fg)]">
                  {reservedTotal.toLocaleString("ko-KR")}
                </strong>
              </span>
            )}
            <span>
              도매가 <strong className="tabular-nums text-foreground">{priceRange}</strong>
            </span>
          </span>
        </div>

        <div className="overflow-hidden rounded-[var(--radius-lg)] border border-divider">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-divider bg-canvas text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <th className="px-4 py-2.5">색상</th>
                <th className="px-4 py-2.5">사이즈</th>
                <th className="px-4 py-2.5 text-right">도매가</th>
                <th className="px-4 py-2.5 text-right">판매가</th>
                <th className="px-4 py-2.5 text-right">재고</th>
                <th className="px-4 py-2.5 text-right">예약</th>
              </tr>
            </thead>
            <tbody>
              {skus.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-sm text-muted-foreground">
                    등록된 옵션이 없습니다.
                  </td>
                </tr>
              ) : (
                skus.map((s, i) => {
                  const newColor = i === 0 || s.color !== skus[i - 1].color;
                  const out = (s.stock ?? 0) <= 0;
                  const reserved = skuReserved(s);
                  return (
                    <tr
                      key={s.id ?? `${s.color}-${s.size}-${i}`}
                      className={`last:border-0 ${
                        newColor && i > 0 ? "border-t-2 border-t-divider" : "border-t border-divider/50"
                      }`}
                    >
                      <td className="px-4 py-2.5 font-medium text-foreground">{newColor ? s.color : ""}</td>
                      <td className="px-4 py-2.5 text-[var(--color-text-secondary)]">{s.size}</td>
                      <td className="px-4 py-2.5 text-right font-semibold tabular-nums text-foreground">
                        {won(s.wholesale_price)}
                      </td>
                      <td className="px-4 py-2.5 text-right tabular-nums text-[var(--color-text-secondary)]">
                        {won(s.retail_price)}
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        {out ? (
                          <Badge tone="danger">품절</Badge>
                        ) : (
                          <span className="font-medium tabular-nums text-foreground">
                            {(s.stock ?? 0).toLocaleString("ko-KR")}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        {reserved > 0 ? (
                          <span className="font-semibold tabular-nums text-[var(--color-warning-fg)]">
                            {reserved.toLocaleString("ko-KR")}
                          </span>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </Dialog>
  );
}

function Field({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div>
      <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 text-sm text-foreground">{value || "—"}</dd>
    </div>
  );
}
