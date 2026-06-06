"use client";
/* eslint-disable react-hooks/set-state-in-effect -- 서버 데이터/라우트 동기화 목적의 의도된 effect */

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  aggregateColors,
  aggregateSizes,
  archiveProduct,
  deleteProduct,
  downloadProductsXlsx,
  getMe,
  listProducts,
  productThumb,
  repWholesale,
  restoreProduct,
  won,
  type Product,
} from "@/lib/products";
import { SingleProductModal } from "@/components/SingleProductModal";
import { Badge, Button, Card, Dialog, Popover } from "@/components/ui";
import {
  Archive,
  ChevronLeft,
  ChevronRight,
  Download,
  FileUp,
  Filter,
  ImageIcon,
  Pencil,
  Plus,
  Restore,
  Save,
  Sort,
  Spinner,
  Table as TableIcon,
  Trash,
} from "@/components/icons";

const PAGE_SIZE = 8;

export default function ProductsPage() {
  const router = useRouter();
  const [wid, setWid] = useState<string>("");
  const [items, setItems] = useState<Product[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const tab = ""; // 카테고리 필터 임시 숨김(분류 기준 미정) — 항상 전체
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [manage, setManage] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Product | null>(null);
  const [confirm, setConfirm] = useState<Product | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    getMe().then((me) => setWid(me.wholesaler_id ?? "")).catch(() => {});
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listProducts({
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
        category: tab || undefined,
      });
      setItems(res.items);
      setTotal(res.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : "상품을 불러오지 못했습니다.");
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [page, tab]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3500);
    return () => clearTimeout(t);
  }, [toast]);

  function showToast(msg?: string) {
    if (msg) setToast(msg);
    load();
  }

  function openCreate() {
    setEditing(null);
    setModalOpen(true);
  }
  function openEdit(p: Product) {
    setEditing(p);
    setModalOpen(true);
  }

  async function onArchiveToggle(p: Product) {
    setBusyId(p.id);
    try {
      if (p.status === "archived") {
        await restoreProduct(p.id);
        setToast(`'${p.item_name}' 진열을 복구했습니다.`);
      } else {
        await archiveProduct(p.id);
        setToast(`'${p.item_name}' 을(를) 보관 처리했습니다.`);
      }
      await load();
    } catch (e) {
      setToast(e instanceof Error ? e.message : "처리에 실패했습니다.");
    } finally {
      setBusyId(null);
    }
  }

  async function onDelete() {
    if (!confirm) return;
    setBusyId(confirm.id);
    try {
      await deleteProduct(confirm.id);
      setToast(`'${confirm.item_name}' 을(를) 삭제했습니다.`);
      setConfirm(null);
      await load();
    } catch (e) {
      setToast(e instanceof Error ? e.message : "삭제에 실패했습니다.");
    } finally {
      setBusyId(null);
    }
  }

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="mx-auto max-w-6xl">
      {/* 헤더 */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-foreground">상품 데이터 관리</h1>
          <p className="mt-1.5 text-sm text-muted-foreground">
            도매 데이터베이스의 모든 상품 정보를 한눈에 관리하고 편집하세요.
          </p>
        </div>
        <div className="flex items-center gap-2.5">
          <Popover
            trigger={({ toggle }) => (
              <Button variant="secondary" onClick={toggle}>
                <FileUp width={16} height={16} /> 상품 업로드
              </Button>
            )}
          >
            {(close) => (
              <div className="text-sm">
                <PopItem
                  icon={<Plus width={16} height={16} />}
                  title="단일 상품 업로드"
                  desc="상품 1건을 직접 등록"
                  onClick={() => {
                    close();
                    openCreate();
                  }}
                />
                <PopItem
                  icon={<TableIcon width={16} height={16} />}
                  title="대량 상품 업로드"
                  desc="엑셀 + 이미지 마법사"
                  onClick={() => router.push("/products/bulk")}
                />
                <PopItem
                  icon={<ImageIcon width={16} height={16} />}
                  title="미매칭 상품 관리"
                  desc="이미지 ↔ 품번 수동 매칭"
                  onClick={() => router.push("/products/unmatched")}
                />
              </div>
            )}
          </Popover>
          <Button variant={manage ? "primary" : "secondary"} onClick={() => setManage((m) => !m)}>
            <Save width={16} height={16} /> 상품 정보 수정
          </Button>
        </div>
      </div>

      {/* 목록 카드 */}
      <Card className="mt-6">
        {/* 툴바 */}
        <div className="flex flex-wrap items-center gap-3 border-b border-divider px-5 py-4">
          <div className="flex items-center gap-2 text-sm font-bold text-foreground">
            상품 목록
            <span className="rounded-full bg-subtle px-2 py-0.5 text-xs font-semibold text-muted-foreground">
              {total}
            </span>
          </div>
          {/* 카테고리 필터 탭 임시 숨김 — 분류 기준 정해지면 복구 */}
          <div className="ml-auto flex items-center gap-2">
            {manage && (
              <Badge tone="info">
                <Pencil width={12} height={12} /> 관리 모드
              </Badge>
            )}
            <IconBtn title="필터">
              <Filter width={16} height={16} />
            </IconBtn>
            <IconBtn title="정렬">
              <Sort width={16} height={16} />
            </IconBtn>
          </div>
        </div>

        {/* 테이블 */}
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-left">
            <thead>
              <tr className="border-b border-divider text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <Th className="w-20">제품이미지</Th>
                <Th>품번</Th>
                <Th>상품명</Th>
                <Th>색상</Th>
                <Th>상세사이즈</Th>
                <Th>혼용률</Th>
                <Th className="text-right">도매가</Th>
                {manage && <Th className="text-right">작업</Th>}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={manage ? 8 : 7} className="py-20 text-center text-muted-foreground">
                    <Spinner width={24} height={24} className="mx-auto" />
                  </td>
                </tr>
              ) : error ? (
                <tr>
                  <td colSpan={manage ? 8 : 7} className="py-16 text-center text-sm text-[var(--color-danger-fg)]">
                    {error}
                  </td>
                </tr>
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={manage ? 8 : 7} className="py-20 text-center">
                    <div className="text-sm font-semibold text-foreground">등록된 상품이 없습니다</div>
                    <p className="mt-1 text-sm text-muted-foreground">
                      상단 “상품 업로드”로 첫 상품을 등록해 보세요.
                    </p>
                  </td>
                </tr>
              ) : (
                items.map((p) => {
                  const thumb = productThumb(p);
                  return (
                    <tr key={p.id} className="border-b border-divider/70 last:border-0 hover:bg-canvas">
                      <Td>
                        <div className="flex size-12 items-center justify-center overflow-hidden rounded-[var(--radius)] bg-subtle text-border-strong">
                          {thumb ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img src={thumb} alt={p.item_name} className="h-full w-full object-cover" />
                          ) : (
                            <ImageIcon width={18} height={18} />
                          )}
                        </div>
                      </Td>
                      <Td className="font-mono text-sm text-muted-foreground">{p.source_p_number}</Td>
                      <Td>
                        <div className="flex items-center gap-2 font-semibold text-foreground">
                          {p.item_name}
                          {p.status === "archived" && <Badge tone="neutral">보관됨</Badge>}
                          {p.is_sold_out && <Badge tone="danger">SOLD OUT</Badge>}
                        </div>
                        {p.category && <div className="text-xs text-muted-foreground">{p.category}</div>}
                      </Td>
                      <Td className="text-sm text-[var(--color-text-secondary)]">{aggregateColors(p)}</Td>
                      <Td className="text-sm text-[var(--color-text-secondary)]">{aggregateSizes(p)}</Td>
                      <Td className="text-sm text-[var(--color-text-secondary)]">{p.fabric_composition ?? "—"}</Td>
                      <Td className="text-right font-bold tabular-nums text-foreground">
                        {won(repWholesale(p))}
                      </Td>
                      {manage && (
                        <Td className="text-right">
                          <div className="flex justify-end gap-1">
                            <RowAction title="수정" onClick={() => openEdit(p)}>
                              <Pencil width={15} height={15} />
                            </RowAction>
                            <RowAction
                              title={p.status === "archived" ? "복구" : "보관"}
                              onClick={() => onArchiveToggle(p)}
                              busy={busyId === p.id}
                            >
                              {p.status === "archived" ? (
                                <Restore width={15} height={15} />
                              ) : (
                                <Archive width={15} height={15} />
                              )}
                            </RowAction>
                            <RowAction title="삭제" danger onClick={() => setConfirm(p)}>
                              <Trash width={15} height={15} />
                            </RowAction>
                          </div>
                        </Td>
                      )}
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* 페이지네이션 */}
        {pageCount > 1 && (
          <div className="flex items-center justify-center gap-1.5 border-t border-divider py-4">
            <PagerBtn disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
              <ChevronLeft width={16} height={16} />
            </PagerBtn>
            {pageNumbers(page, pageCount).map((n, i) =>
              n === -1 ? (
                <span key={`gap${i}`} className="px-1 text-muted-foreground">
                  …
                </span>
              ) : (
                <PagerBtn key={n} active={n === page} onClick={() => setPage(n)}>
                  {n + 1}
                </PagerBtn>
              )
            )}
            <PagerBtn disabled={page >= pageCount - 1} onClick={() => setPage((p) => p + 1)}>
              <ChevronRight width={16} height={16} />
            </PagerBtn>
          </div>
        )}
      </Card>

      {/* 엑셀 다운로드 */}
      <div className="mt-5 flex justify-end">
        <Button
          variant="secondary"
          onClick={() =>
            downloadProductsXlsx({ category: tab || undefined }).catch((e) =>
              setToast(e instanceof Error ? e.message : "다운로드 실패")
            )
          }
        >
          <Download width={16} height={16} /> 엑셀 다운로드
        </Button>
      </div>

      {/* 모달 */}
      {wid && (
        <SingleProductModal
          open={modalOpen}
          onClose={() => setModalOpen(false)}
          onSaved={showToast}
          wholesalerId={wid}
          editing={editing}
        />
      )}

      {/* 삭제 확인 */}
      <Dialog
        open={!!confirm}
        onClose={() => setConfirm(null)}
        size="sm"
        icon={<Trash width={18} height={18} />}
        title="상품 삭제"
        footer={
          <>
            <Button variant="secondary" onClick={() => setConfirm(null)}>
              취소
            </Button>
            <Button variant="danger" loading={busyId === confirm?.id} onClick={onDelete}>
              삭제
            </Button>
          </>
        }
      >
        <p className="text-sm leading-relaxed text-muted-foreground">
          <strong className="text-foreground">{confirm?.item_name}</strong> 을(를) 삭제하시겠습니까?
          연결된 SKU·이미지도 함께 처리됩니다. (soft delete — 복구 가능하나 목록에서는 사라집니다)
        </p>
      </Dialog>

      {/* 토스트 */}
      {toast && (
        <div className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-[var(--radius)] bg-ink px-5 py-3 text-sm font-medium text-white shadow-[var(--shadow-lg)]">
          {toast}
        </div>
      )}
    </div>
  );
}

/* ── 소형 컴포넌트 ──────────────────────────────────────────────────────── */
function Th({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <th className={`px-5 py-3 ${className}`}>{children}</th>;
}
function Td({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <td className={`px-5 py-3.5 align-middle ${className}`}>{children}</td>;
}
function IconBtn({ children, title }: { children: React.ReactNode; title: string }) {
  return (
    <button
      type="button"
      title={title}
      className="flex size-9 items-center justify-center rounded-[var(--radius)] border border-border bg-surface text-muted-foreground transition hover:bg-subtle hover:text-foreground"
    >
      {children}
    </button>
  );
}
function RowAction({
  children,
  title,
  onClick,
  danger,
  busy,
}: {
  children: React.ReactNode;
  title: string;
  onClick: () => void;
  danger?: boolean;
  busy?: boolean;
}) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      disabled={busy}
      className={`flex size-8 items-center justify-center rounded-[var(--radius)] border border-border bg-surface transition hover:bg-subtle disabled:opacity-50 ${
        danger ? "text-[var(--color-danger)] hover:border-[var(--color-danger)]" : "text-muted-foreground hover:text-foreground"
      }`}
    >
      {busy ? <Spinner width={14} height={14} /> : children}
    </button>
  );
}
function PagerBtn({
  children,
  active,
  disabled,
  onClick,
}: {
  children: React.ReactNode;
  active?: boolean;
  disabled?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`flex h-9 min-w-9 items-center justify-center rounded-[var(--radius)] px-2 text-sm font-semibold transition disabled:opacity-40 ${
        active
          ? "bg-ink text-white"
          : "border border-border bg-surface text-foreground hover:bg-subtle"
      }`}
    >
      {children}
    </button>
  );
}
function PopItem({
  icon,
  title,
  desc,
  onClick,
}: {
  icon: React.ReactNode;
  title: string;
  desc: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-center gap-3 rounded-[var(--radius)] px-3 py-2.5 text-left transition hover:bg-subtle"
    >
      <span className="flex size-9 shrink-0 items-center justify-center rounded-[var(--radius)] bg-subtle text-foreground">
        {icon}
      </span>
      <span>
        <span className="block font-semibold text-foreground">{title}</span>
        <span className="block text-xs text-muted-foreground">{desc}</span>
      </span>
    </button>
  );
}

/** 페이지 번호 배열(현재 주변 + 처음/끝, 생략은 -1). */
function pageNumbers(cur: number, count: number): number[] {
  if (count <= 7) return Array.from({ length: count }, (_, i) => i);
  const out = new Set<number>([0, count - 1, cur, cur - 1, cur + 1]);
  const sorted = [...out].filter((n) => n >= 0 && n < count).sort((a, b) => a - b);
  const res: number[] = [];
  for (let i = 0; i < sorted.length; i++) {
    if (i > 0 && sorted[i] - sorted[i - 1] > 1) res.push(-1);
    res.push(sorted[i]);
  }
  return res;
}
