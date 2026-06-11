"use client";
/* eslint-disable react-hooks/set-state-in-effect -- 서버 데이터/라우트 동기화 목적의 의도된 effect */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  aggregateSizes,
  archiveProduct,
  colorSummary,
  deleteProduct,
  downloadProductsXlsx,
  getMe,
  isSoldOut,
  listProducts,
  productThumb,
  repWholesale,
  restoreProduct,
  won,
  type Product,
} from "@/lib/products";
import { SingleProductModal } from "@/components/SingleProductModal";
import { ProductDetailModal } from "@/components/ProductDetailModal";
import { useSearch } from "@/components/SearchProvider";
import { Badge, Button, Card, Dialog, Popover } from "@/components/ui";
import {
  Archive,
  Check,
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
  const { query } = useSearch(); // 상단바 검색어(상품명·품번)
  const [wid, setWid] = useState<string>("");
  const [allItems, setAllItems] = useState<Product[]>([]); // 전체 로드 후 클라에서 필터/정렬/페이지네이션
  const [page, setPage] = useState(0);
  // 필터/정렬(클라이언트) — 페이지네이션이 클라 슬라이스라 도매가(자식 SKU 최저가) 정렬도 정확.
  // 필터는 단일선택 보기 모드: 전체 / 품절만 / 보관(진열 내림)만.
  const [viewFilter, setViewFilter] = useState<"all" | "soldout" | "archived">("all");
  const [sortKey, setSortKey] = useState<"created" | "pnum" | "name" | "price">("created");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [manage, setManage] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Product | null>(null);
  const [detail, setDetail] = useState<Product | null>(null);   // 상세(읽기) 모달 대상
  const [confirm, setConfirm] = useState<Product | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    getMe().then((me) => setWid(me.wholesaler_id ?? "")).catch(() => {});
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const LIMIT = 100; // 백엔드 list 캡(le=100) — 전체를 페이지 루프로 모은다.
      const acc: Product[] = [];
      for (let off = 0; off <= 5000; off += LIMIT) {
        // 안전 상한 5000
        const res = await listProducts({ limit: LIMIT, offset: off });
        acc.push(...res.items);
        if (acc.length >= res.total || res.items.length === 0) break;
      }
      setAllItems(acc);
    } catch (e) {
      setError(e instanceof Error ? e.message : "상품을 불러오지 못했습니다.");
      setAllItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    // 다운로드 진행 중에는 "준비 중" 안내가 사라지지 않도록 자동 닫힘을 멈춘다.
    if (!toast || downloading) return;
    const t = setTimeout(() => setToast(null), 3500);
    return () => clearTimeout(t);
  }, [toast, downloading]);

  function showToast(msg?: string) {
    if (msg) setToast(msg);
    load();
  }

  async function onDownloadXlsx() {
    if (downloading) return;
    setDownloading(true);
    setToast("엑셀을 준비하고 있습니다. 잠시만 기다려 주세요…");
    try {
      await downloadProductsXlsx();
      setToast("엑셀 다운로드가 시작되었습니다.");
    } catch (e) {
      setToast(e instanceof Error ? e.message : "다운로드 실패");
    } finally {
      setDownloading(false);
    }
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

  // 필터 + 검색 + 정렬 적용 (클라이언트). 도매가 = SKU 최저가(repWholesale).
  const view = useMemo(() => {
    let arr = allItems;
    if (viewFilter === "soldout") arr = arr.filter((p) => isSoldOut(p));
    else if (viewFilter === "archived") arr = arr.filter((p) => p.status === "archived");
    const q = query.trim().toLowerCase();
    if (q)
      arr = arr.filter(
        (p) =>
          (p.item_name || "").toLowerCase().includes(q) ||
          (p.source_p_number || "").toLowerCase().includes(q)
      );
    const dir = sortDir === "asc" ? 1 : -1;
    return [...arr].sort((a, b) => {
      let c: number;
      switch (sortKey) {
        case "pnum":
          c = (a.source_p_number || "").localeCompare(b.source_p_number || "", "ko", { numeric: true });
          break;
        case "name":
          c = (a.item_name || "").localeCompare(b.item_name || "", "ko");
          break;
        case "price":
          c = (repWholesale(a) ?? Infinity) - (repWholesale(b) ?? Infinity);
          break;
        default: // created — 등록일
          c = (a.created_at || "").localeCompare(b.created_at || "");
      }
      return c * dir;
    });
  }, [allItems, viewFilter, query, sortKey, sortDir]);

  const total = view.length;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const pageItems = view.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE);
  const filterActive = viewFilter !== "all";

  // 필터/정렬 변경 시 첫 페이지로, 항목이 줄어 현재 페이지가 비면 클램프.
  useEffect(() => {
    setPage(0);
  }, [viewFilter, query, sortKey, sortDir]);
  useEffect(() => {
    if (page > pageCount - 1) setPage(pageCount - 1);
  }, [page, pageCount]);

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
            <Popover
              align="end"
              trigger={({ toggle }) => (
                <button
                  type="button"
                  title="필터"
                  onClick={toggle}
                  className={`relative flex size-9 items-center justify-center rounded-[var(--radius)] border transition ${
                    filterActive
                      ? "border-ink bg-ink text-white"
                      : "border-border bg-surface text-muted-foreground hover:bg-subtle hover:text-foreground"
                  }`}
                >
                  <Filter width={16} height={16} />
                  {filterActive && (
                    <span className="absolute -right-1 -top-1 size-2.5 rounded-full bg-[var(--color-warning)] ring-2 ring-surface" />
                  )}
                </button>
              )}
            >
              {(close) => {
                const pick = (v: typeof viewFilter) => {
                  setViewFilter(v);
                  close();
                };
                return (
                  <div className="text-sm">
                    <PopChoice label="전체 보기" active={viewFilter === "all"} onClick={() => pick("all")} />
                    <PopChoice label="품절만 보기" active={viewFilter === "soldout"} onClick={() => pick("soldout")} />
                    <PopChoice label="보관 상품만 보기" active={viewFilter === "archived"} onClick={() => pick("archived")} />
                  </div>
                );
              }}
            </Popover>
            <Popover
              align="end"
              trigger={({ open, toggle }) => (
                <IconBtn title="정렬" onClick={toggle} active={open}>
                  <Sort width={16} height={16} />
                </IconBtn>
              )}
            >
              {(close) => {
                const choose = (k: typeof sortKey, d: typeof sortDir) => {
                  setSortKey(k);
                  setSortDir(d);
                  close();
                };
                return (
                  <div className="text-sm">
                    <PopChoice label="최신 등록순" active={sortKey === "created" && sortDir === "desc"} onClick={() => choose("created", "desc")} />
                    <PopChoice label="품번 낮은순" active={sortKey === "pnum" && sortDir === "asc"} onClick={() => choose("pnum", "asc")} />
                    <PopChoice label="품번 높은순" active={sortKey === "pnum" && sortDir === "desc"} onClick={() => choose("pnum", "desc")} />
                    <PopChoice label="상품명순 (가나다)" active={sortKey === "name" && sortDir === "asc"} onClick={() => choose("name", "asc")} />
                    <PopChoice label="도매가 낮은순" active={sortKey === "price" && sortDir === "asc"} onClick={() => choose("price", "asc")} />
                    <PopChoice label="도매가 높은순" active={sortKey === "price" && sortDir === "desc"} onClick={() => choose("price", "desc")} />
                  </div>
                );
              }}
            </Popover>
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
              ) : view.length === 0 ? (
                <tr>
                  <td colSpan={manage ? 8 : 7} className="py-20 text-center">
                    <div className="text-sm font-semibold text-foreground">
                      {allItems.length === 0 ? "등록된 상품이 없습니다" : "조건에 맞는 상품이 없습니다"}
                    </div>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {allItems.length === 0
                        ? "상단 “상품 업로드”로 첫 상품을 등록해 보세요."
                        : "검색어나 필터를 조정해 보세요."}
                    </p>
                  </td>
                </tr>
              ) : (
                pageItems.map((p) => {
                  const thumb = productThumb(p);
                  const colors = colorSummary(p);
                  return (
                    <tr
                      key={p.id}
                      onClick={() => setDetail(p)}
                      className="cursor-pointer border-b border-divider/70 last:border-0 hover:bg-canvas"
                    >
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
                          {isSoldOut(p) && <Badge tone="danger">SOLD OUT</Badge>}
                        </div>
                        {p.category && <div className="text-xs text-muted-foreground">{p.category}</div>}
                      </Td>
                      <Td className="text-sm text-[var(--color-text-secondary)]">
                        <span title={colors.more ? colors.full : undefined}>{colors.text}</span>
                      </Td>
                      <Td className="text-sm text-[var(--color-text-secondary)]">{aggregateSizes(p)}</Td>
                      <Td className="text-sm text-[var(--color-text-secondary)]">{p.fabric_composition ?? "—"}</Td>
                      <Td className="text-right font-bold tabular-nums text-foreground">
                        {won(repWholesale(p))}
                      </Td>
                      {manage && (
                        <Td className="text-right">
                          {/* 작업 버튼 클릭은 행 클릭(상세 열기)으로 전파되지 않도록 차단 */}
                          <div className="flex justify-end gap-1" onClick={(e) => e.stopPropagation()}>
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
        <Button variant="secondary" loading={downloading} onClick={onDownloadXlsx}>
          {!downloading && <Download width={16} height={16} />}
          {downloading ? "다운로드 준비 중…" : "엑셀 다운로드"}
        </Button>
      </div>

      {/* 상세(읽기) 모달 — 클릭한 상품의 모든 SKU 표시. 수정 누르면 편집 모달로 전환 */}
      <ProductDetailModal
        product={detail}
        open={!!detail}
        onClose={() => setDetail(null)}
        onEdit={(p) => {
          setDetail(null);
          openEdit(p);
        }}
      />

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
function IconBtn({
  children,
  title,
  onClick,
  active,
}: {
  children: React.ReactNode;
  title: string;
  onClick?: () => void;
  active?: boolean;
}) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      className={`flex size-9 items-center justify-center rounded-[var(--radius)] border transition hover:bg-subtle hover:text-foreground ${
        active
          ? "border-ink bg-subtle text-foreground"
          : "border-border bg-surface text-muted-foreground"
      }`}
    >
      {children}
    </button>
  );
}
/** 필터/정렬 드롭다운의 단일 선택 행. */
function PopChoice({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-center justify-between gap-3 rounded-[var(--radius)] px-3 py-2 text-left transition hover:bg-subtle"
    >
      <span className={`font-medium ${active ? "text-foreground" : "text-muted-foreground"}`}>{label}</span>
      {active && <Check width={14} height={14} className="text-ink" />}
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
