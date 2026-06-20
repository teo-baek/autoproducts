"use client";
/* eslint-disable react-hooks/set-state-in-effect -- editing prop → 폼 prefill 동기화(의도된 effect) */

import { useEffect, useRef, useState } from "react";
import {
  buildSkuMatrix,
  createProduct,
  productThumb,
  replaceSkus,
  updateProduct,
  uploadProductImage,
  type Product,
} from "@/lib/products";
import { Button, Dialog, NumberField, TextField } from "@/components/ui";
import { ImageIcon, Plus, Pencil } from "@/components/icons";

type Props = {
  open: boolean;
  onClose: () => void;
  onSaved: (msg?: string) => void;
  wholesalerId: string;
  editing?: Product | null;
};

const num = (s: string) => (s.trim() === "" ? 0 : Math.max(0, Math.floor(Number(s) || 0)));

/** 단일 상품 등록/수정 모달 (시안 p10). 색상×사이즈 → SKU 매트릭스. 이미지 직접 업로드. */
export function SingleProductModal({ open, onClose, onSaved, wholesalerId, editing }: Props) {
  const isEdit = !!editing;
  const [itemName, setItemName] = useState("");
  const [sku, setSku] = useState("");
  const [wholesale, setWholesale] = useState("");
  const [retail, setRetail] = useState("");
  const [colors, setColors] = useState("");
  const [sizes, setSizes] = useState("");
  const [fabric, setFabric] = useState("");
  const [description, setDescription] = useState("");
  const [stock, setStock] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  // 모달 열릴 때 prefill / 초기화
  useEffect(() => {
    if (!open) return;
    setError(null);
    setFile(null);
    if (editing) {
      setItemName(editing.item_name);
      setSku(editing.source_p_number);
      const s0 = editing.skus[0];
      const minW = Math.min(...editing.skus.map((s) => s.wholesale_price));
      setWholesale(String(isFinite(minW) ? minW : s0?.wholesale_price ?? ""));
      setRetail(s0?.retail_price != null ? String(s0.retail_price) : "");
      setColors([...new Set(editing.skus.map((s) => s.color))].join(", "));
      setSizes([...new Set(editing.skus.map((s) => s.size))].join(", "));
      setFabric(editing.fabric_composition ?? "");
      setDescription(editing.description ?? "");
      setStock(s0?.stock != null ? String(s0.stock) : "");
      setPreview(productThumb(editing));
    } else {
      setItemName(""); setSku(""); setWholesale(""); setRetail("");
      setColors(""); setSizes(""); setFabric(""); setDescription(""); setStock(""); setPreview(null);
    }
  }, [open, editing]);

  function pickFile(f: File | null) {
    setFile(f);
    if (f) setPreview(URL.createObjectURL(f));
  }

  async function onSubmit() {
    setError(null);
    if (!itemName.trim()) return setError("상품명을 입력해주세요.");
    if (!sku.trim()) return setError("품번(SKU)을 입력해주세요.");
    if (num(wholesale) <= 0) return setError("도매가를 입력해주세요.");
    // 이미지 필수 — 새 파일이 없고 기존 이미지(편집 시)도 없으면 차단
    if (!file && !preview) return setError("상품 이미지를 등록해주세요.");

    setLoading(true);
    try {
      const matrix = buildSkuMatrix(
        colors, sizes, num(wholesale), retail.trim() === "" ? null : num(retail), num(stock)
      );

      let productId: string;
      let platformCode: string;
      if (isEdit && editing) {
        await updateProduct(editing.id, {
          item_name: itemName.trim(),
          category: null,
          fabric_composition: fabric.trim() || null,
          description: description.trim() || null,
        });
        await replaceSkus(editing.id, matrix);
        productId = editing.id;
        platformCode = editing.platform_code;
      } else {
        const created = await createProduct({
          source_p_number: sku.trim(),
          item_name: itemName.trim(),
          category: null,
          fabric_composition: fabric.trim() || null,
          description: description.trim() || null,
          skus: matrix,
        });
        productId = created.id;
        platformCode = created.platform_code;
      }

      // 이미지(필수) — 단, 업로드 자체 실패(버킷 미생성·네트워크)는 상품 저장 유지 + 재시도 안내
      let warn = "";
      if (file) {
        try {
          const { publicUrl } = await uploadProductImage(file, wholesalerId, platformCode);
          await updateProduct(productId, { representative_image_url: publicUrl });
        } catch {
          warn = " (단, 이미지 업로드는 실패했어요 — 잠시 후 다시 시도해 주세요)";
        }
      }
      onSaved(`${isEdit ? "상품을 수정했습니다" : "상품을 등록했습니다"}${warn}`);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "저장에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      size="lg"
      icon={isEdit ? <Pencil width={18} height={18} /> : <Plus width={18} height={18} />}
      title={isEdit ? "상품 정보 수정" : "단일 상품 등록"}
      footer={
        <>
          {/* 경고는 등록 버튼 옆(고정 푸터)에 — 본문 맨 위면 스크롤해야 보여서 옮김 */}
          {error && (
            <p className="mr-auto max-w-[60%] text-left text-sm font-medium text-[var(--color-danger-fg)]">
              {error}
            </p>
          )}
          <Button variant="secondary" onClick={onClose} disabled={loading}>
            취소
          </Button>
          <Button onClick={onSubmit} loading={loading}>
            {isEdit ? "변경사항 저장" : "상품 등록"}
          </Button>
        </>
      }
    >
      <div className="grid gap-8 md:grid-cols-[1fr_18rem]">
        {/* 좌: 입력 */}
        <div className="space-y-6">
          <section className="space-y-4">
            <SectionTitle>기본 정보</SectionTitle>
            <TextField
              label="상품명 *"
              placeholder="예: 미니멀 실크 블라우스"
              value={itemName}
              onChange={(e) => setItemName(e.target.value)}
            />
            <TextField
              label="품번 (SKU) *"
              placeholder="예: F-SLK-001"
              value={sku}
              onChange={(e) => setSku(e.target.value)}
              disabled={isEdit}
            />{/* 카테고리 셀렉트 임시 숨김 — 분류 기준 정해지면 복구 */}
          </section>

          <section className="space-y-4">
            <SectionTitle>가격 정보</SectionTitle>
            <div className="grid gap-4 sm:grid-cols-2">
              <NumberField
                label="도매가 *"
                prefix="₩"
                placeholder="0"
                value={wholesale}
                onChange={(e) => setWholesale(e.target.value)}
              />
              <NumberField
                label="소매가 (권장)"
                prefix="₩"
                placeholder="0"
                value={retail}
                onChange={(e) => setRetail(e.target.value)}
              />
            </div>
          </section>

          <section className="space-y-4">
            <SectionTitle>상세 정보</SectionTitle>
            <div className="grid gap-4 sm:grid-cols-2">
              <TextField
                label="색상"
                placeholder="예: 아이보리, 블랙"
                value={colors}
                onChange={(e) => setColors(e.target.value)}
              />
              <TextField
                label="사이즈"
                placeholder="예: S, M, L / Free"
                value={sizes}
                onChange={(e) => setSizes(e.target.value)}
              />
            </div>
            <TextField
              label="혼용률"
              placeholder="예: Cotton 100%, Silk 100%"
              value={fabric}
              onChange={(e) => setFabric(e.target.value)}
            />
            <NumberField
              label="재고"
              placeholder="0"
              value={stock}
              inputMode="numeric"
              onChange={(e) => setStock(e.target.value.replace(/[^0-9]/g, ""))}
            />
            <p className="text-xs text-muted-foreground">
              색상·사이즈를 콤마로 여러 개 입력하면 조합별 SKU가 자동 생성됩니다. (가격·재고는 조합 공통)
            </p>
          </section>
        </div>

        {/* 우: 이미지 */}
        <div className="flex flex-col">
          <SectionTitle>상품 이미지 *</SectionTitle>
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            className="mt-4 flex aspect-[4/5] w-full flex-col items-center justify-center gap-3 overflow-hidden rounded-[var(--radius-lg)] border-2 border-dashed border-border bg-subtle text-center transition hover:border-ink/40"
          >
            {preview ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={preview} alt="미리보기" className="h-full w-full object-cover" />
            ) : (
              <>
                <span className="flex size-12 items-center justify-center rounded-full bg-surface text-border-strong">
                  <ImageIcon width={22} height={22} />
                </span>
                <span className="px-6 text-sm font-medium text-foreground">이미지 업로드</span>
                <span className="px-6 text-xs text-muted-foreground">
                  클릭하여 파일을 선택하거나 드래그 앤 드롭 하세요.
                </span>
                <span className="text-[11px] text-placeholder">JPG, PNG, WEBP (최대 5MB)</span>
              </>
            )}
          </button>
          {preview && (
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              className="mt-3 w-full text-center text-xs font-semibold text-ink hover:underline"
            >
              이미지 변경
            </button>
          )}
          <input
            ref={fileRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="hidden"
            onChange={(e) => pickFile(e.target.files?.[0] ?? null)}
          />

          <div className="mt-6 flex flex-1 flex-col pb-1">
            <label
              htmlFor="product-description"
              className="mb-2 block text-sm font-semibold text-[var(--color-text-secondary)]"
            >
              제품 상세 설명
            </label>
            <textarea
              id="product-description"
              rows={6}
              placeholder="제품에 대한 추가 정보·특징·주의사항 등을 입력하세요."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="min-h-[11rem] w-full flex-1 resize-y rounded-[var(--radius)] border border-border bg-subtle px-4 py-3 text-sm text-foreground outline-none transition placeholder:text-placeholder focus:border-ink focus:ring-2 focus:ring-ink/15"
            />
          </div>
        </div>
      </div>
    </Dialog>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3">
      <h3 className="text-sm font-bold text-foreground">{children}</h3>
      <span className="h-px flex-1 bg-divider" />
    </div>
  );
}
