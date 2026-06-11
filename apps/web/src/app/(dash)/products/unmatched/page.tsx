"use client";
/* eslint-disable react-hooks/set-state-in-effect -- 잡/서버 데이터 동기화 목적의 의도된 effect */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  listJobs,
  listProducts,
  listUnmatched,
  matchImage,
  productThumb,
  publicImageUrl,
  repWholesale,
  won,
  type Product,
  type ProductImage,
} from "@/lib/products";
import { Badge, Button, Card, Dialog } from "@/components/ui";
import { Filter, ImageIcon, Info, Save, Sort, Spinner, UploadCloud } from "@/components/icons";

export default function UnmatchedPage() {
  const router = useRouter();
  const [jobId, setJobId] = useState<string | null>(null);
  const [noJob, setNoJob] = useState(false);
  const [products, setProducts] = useState<Product[]>([]);
  // 우측 패널의 "연결 가능한 이미지" 풀 — 임시 매칭하면 풀에서 빠지고, 매칭 취소하면 풀로 돌아온다(로컬).
  const [pool, setPool] = useState<ProductImage[]>([]);
  const [loading, setLoading] = useState(true);
  const [dragId, setDragId] = useState<string | null>(null);
  const [overPid, setOverPid] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  // 화면 진입 시점의 미매칭 상품 id 스냅샷 — 이 행들만 노출(매칭해도 '매칭 완료'로 남는다).
  const [displayIds, setDisplayIds] = useState<string[] | null>(null);
  // 임시(미저장) 매칭: productId → 연결한 이미지. '저장'을 눌러야 서버에 확정된다.
  const [staged, setStaged] = useState<Record<string, ProductImage>>({});
  // 이탈 경고 모달 + 가로챈 이동 목적지(앱 내 링크 클릭 시)
  const [leaving, setLeaving] = useState(false);
  const [pendingHref, setPendingHref] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const dirty = Object.keys(staged).length > 0;

  // 잡 결정: ?job 우선, 없으면 최신 잡
  useEffect(() => {
    const fromUrl = new URLSearchParams(window.location.search).get("job");
    if (fromUrl) {
      setJobId(fromUrl);
      return;
    }
    listJobs()
      .then((r) => {
        if (r.jobs.length) setJobId(r.jobs[0].id);
        else setNoJob(true);
      })
      .catch(() => setNoJob(true));
  }, []);

  const load = useCallback(async () => {
    if (!jobId) return;
    setLoading(true);
    try {
      const [prods, imgs] = await Promise.all([
        listProducts({ limit: 50 }),
        listUnmatched(jobId),
      ]);
      setProducts(prods.items);
      setPool(imgs);
      setStaged({});
      // 진입(또는 저장 후 재조회) 시점의 미매칭만 노출 대상으로 스냅샷.
      setDisplayIds(prods.items.filter((p) => !productThumb(p)).map((p) => p.id));
    } catch (e) {
      setToast(e instanceof Error ? e.message : "불러오기 실패");
    } finally {
      setLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3000);
    return () => clearTimeout(t);
  }, [toast]);

  // 이탈 경고 ① 브라우저 새로고침/탭닫기 — 저장 안 한 변경이 있을 때만
  useEffect(() => {
    if (!dirty) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);

  // 이탈 경고 ② 앱 내 페이지 이동(사이드바 등 <a> 링크) — 캡처 단계에서 가로채 모달로
  useEffect(() => {
    if (!dirty) return;
    function onClickCapture(e: MouseEvent) {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const target = e.target as HTMLElement | null;
      const a = target?.closest?.("a");
      const href = a?.getAttribute("href");
      if (!href || !href.startsWith("/")) return;
      const dest = href.split("?")[0].split("#")[0];
      if (dest === window.location.pathname) return;
      e.preventDefault();
      e.stopPropagation();
      setPendingHref(href);
      setLeaving(true);
    }
    document.addEventListener("click", onClickCapture, true);
    return () => document.removeEventListener("click", onClickCapture, true);
  }, [dirty]);

  // 드롭 = 임시 매칭(로컬). 이미 매칭된 행에 다시 드롭하면 교체(기존 이미지는 풀로 복귀).
  function onDropImage(p: Product) {
    setOverPid(null);
    const imageId = dragId;
    setDragId(null);
    if (!imageId) return;
    const img = pool.find((i) => i.id === imageId);
    if (!img) return;
    const old = staged[p.id];
    setStaged({ ...staged, [p.id]: img });
    setPool((prev) => {
      const arr = prev.filter((i) => i.id !== imageId);
      return old ? [old, ...arr] : arr;
    });
    setToast(`'${p.item_name}' 에 임시 매칭했습니다 — 저장해야 확정됩니다.`);
  }

  // 매칭 취소 — 임시 매칭 해제, 이미지는 풀로 복귀(로컬). 저장 전 실수 정정용.
  function cancelMatch(p: Product) {
    const img = staged[p.id];
    if (!img) return;
    const next = { ...staged };
    delete next[p.id];
    setStaged(next);
    setPool((prev) => [img, ...prev]);
    setToast(`'${p.item_name}' 매칭을 취소했습니다.`);
  }

  // 저장 = 임시 매칭들을 서버에 일괄 확정.
  async function onSave() {
    if (!jobId || saving) return;
    const entries = Object.entries(staged);
    if (!entries.length) return;
    setSaving(true);
    let failed = 0;
    for (const [pid, img] of entries) {
      const prod = products.find((p) => p.id === pid);
      if (!prod) continue;
      try {
        await matchImage(jobId, img.id, prod.source_p_number);
      } catch {
        failed++;
      }
    }
    setSaving(false);
    if (failed) {
      setToast(`${entries.length - failed}건 저장, ${failed}건 실패 — 다시 시도해 주세요.`);
      await load(); // 서버 기준 재동기화(실패분은 풀로 복귀)
    } else {
      setToast(`${entries.length}건의 매칭을 저장했습니다.`);
      await load(); // 서버 기준 재동기화(저장된 상품은 목록에서 빠진다)
      setToast("저장되었습니다."); // 목록 갱신까지 끝난 시점에 확정 안내 한 번 더
    }
  }

  // 이탈 시도(취소 버튼 또는 가로챈 링크) → 변경 있으면 모달, 없으면 즉시 이동
  function requestLeave() {
    setPendingHref(null);
    if (dirty) setLeaving(true);
    else router.push("/products");
  }
  function confirmLeave() {
    const dest = pendingHref ?? "/products";
    setLeaving(false);
    setPendingHref(null);
    setStaged({}); // beforeunload/가로채기 재발동 방지
    router.push(dest);
  }
  function dismissLeave() {
    setLeaving(false);
    setPendingHref(null);
  }

  const rows = displayIds === null ? [] : products.filter((p) => displayIds.includes(p.id));
  const stagedInView = rows.filter((p) => staged[p.id]).length;
  const remainingUnmatched = rows.length - stagedInView;
  const progress = rows.length ? Math.round((stagedInView / rows.length) * 100) : 0;

  if (noJob) {
    return (
      <div className="mx-auto max-w-2xl">
        <h1 className="text-2xl font-extrabold tracking-tight text-foreground">미매칭 상품 데이터 관리</h1>
        <Card className="mt-6 grid place-items-center px-8 py-20 text-center">
          <span className="flex size-14 items-center justify-center rounded-full bg-surface-muted text-border-strong">
            <UploadCloud width={24} height={24} />
          </span>
          <h2 className="mt-5 text-lg font-bold text-foreground">진행 중인 업로드 작업이 없습니다</h2>
          <p className="mt-2 max-w-sm text-sm text-muted-foreground">
            대량 등록 마법사에서 엑셀·이미지를 먼저 업로드하면, 미매칭 이미지를 여기서 수동 연결할 수 있습니다.
          </p>
          <Link href="/products/bulk" className="mt-6">
            <Button>대량 등록 시작</Button>
          </Link>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-foreground">미매칭 상품 데이터 관리</h1>
          <p className="mt-1.5 text-sm text-muted-foreground">
            이미지를 상품 행으로 드래그하면 <strong className="font-semibold text-foreground">임시 매칭</strong>됩니다.
            상단 <strong className="font-semibold text-foreground">‘저장’</strong>을 눌러야 최종 반영돼요.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {dirty && (
            <span className="rounded-full bg-[var(--color-warning-bg)] px-3 py-1 text-xs font-semibold text-[var(--color-warning)]">
              미저장 {Object.keys(staged).length}건
            </span>
          )}
          <Button variant="secondary" onClick={requestLeave} disabled={saving}>
            취소
          </Button>
          <Button onClick={onSave} loading={saving} disabled={!dirty || saving}>
            <Save width={16} height={16} /> 저장
          </Button>
        </div>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_20rem]">
        {/* 좌: 상품 데이터 */}
        <Card>
          <div className="flex items-center gap-3 border-b border-divider px-5 py-4">
            <div className="text-sm font-bold text-foreground">
              미매칭 {remainingUnmatched}개의 상품 데이터
            </div>
            <div className="ml-auto flex gap-2">
              <span className="flex size-9 items-center justify-center rounded-[var(--radius)] border border-border text-muted-foreground">
                <Filter width={16} height={16} />
              </span>
              <span className="flex size-9 items-center justify-center rounded-[var(--radius)] border border-border text-muted-foreground">
                <Sort width={16} height={16} />
              </span>
            </div>
          </div>

          {loading ? (
            <div className="py-20 text-center">
              <Spinner width={24} height={24} className="mx-auto text-muted-foreground" />
            </div>
          ) : rows.length === 0 ? (
            <div className="py-20 text-center text-sm text-muted-foreground">
              {products.length === 0 ? "상품이 없습니다." : "미매칭 상품이 없습니다 🎉"}
            </div>
          ) : (
            <div className="max-h-[34rem] overflow-y-auto">
              <table className="w-full text-left text-sm">
                <thead className="sticky top-0 bg-surface">
                  <tr className="border-b border-divider text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    <th className="px-5 py-3">썸네일</th>
                    <th className="px-5 py-3">상품 정보</th>
                    <th className="px-5 py-3">품번</th>
                    <th className="px-5 py-3 text-right">단가</th>
                    <th className="px-5 py-3 text-center">상태</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((p) => {
                    const stagedImg = staged[p.id];
                    const matched = !!stagedImg;
                    const thumb = stagedImg ? publicImageUrl(stagedImg.storage_path) : null;
                    const isOver = overPid === p.id;
                    return (
                      <tr
                        key={p.id}
                        onDragOver={(e) => {
                          e.preventDefault();
                          setOverPid(p.id);
                        }}
                        onDragLeave={() => setOverPid((cur) => (cur === p.id ? null : cur))}
                        onDrop={() => onDropImage(p)}
                        className={`border-b border-divider/70 transition last:border-0 ${
                          isOver ? "bg-[var(--color-info-bg)] ring-1 ring-inset ring-[var(--color-info)]" : ""
                        }`}
                      >
                        <td className="px-5 py-3">
                          <div
                            className={`flex size-14 items-center justify-center overflow-hidden rounded-[var(--radius)] ${
                              matched ? "bg-subtle" : "border-2 border-dashed border-border bg-canvas text-border-strong"
                            }`}
                          >
                            {thumb ? (
                              // eslint-disable-next-line @next/next/no-img-element
                              <img src={thumb} alt={p.item_name} className="h-full w-full object-cover" />
                            ) : (
                              <ImageIcon width={18} height={18} />
                            )}
                          </div>
                        </td>
                        <td className="px-5 py-3">
                          <div className="font-semibold text-foreground">{p.item_name}</div>
                          {p.category && <div className="text-xs text-muted-foreground">{p.category}</div>}
                        </td>
                        <td className="px-5 py-3 font-mono text-muted-foreground">{p.source_p_number}</td>
                        <td className="px-5 py-3 text-right font-bold tabular-nums text-foreground">
                          {won(repWholesale(p))}
                        </td>
                        <td className="px-5 py-3 text-center">
                          {matched ? (
                            <div className="flex items-center justify-center gap-2">
                              <Badge tone="success">매칭 완료</Badge>
                              <button
                                type="button"
                                onClick={() => cancelMatch(p)}
                                className="text-xs font-semibold text-muted-foreground underline-offset-2 transition hover:text-[var(--color-danger)] hover:underline"
                              >
                                매칭 취소
                              </button>
                            </div>
                          ) : (
                            <Badge tone="danger">미매칭</Badge>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        {/* 우: 미연결 이미지 */}
        <Card className="flex h-fit flex-col p-5">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-foreground">연결되지 않은 이미지</h2>
            <span className="flex size-7 items-center justify-center rounded-full bg-ink text-xs font-bold text-white">
              {pool.length}
            </span>
          </div>

          <div className="mt-4 grid max-h-[34rem] grid-cols-2 gap-3 overflow-y-auto">
            {pool.length === 0 ? (
              <div className="col-span-2 rounded-[var(--radius-lg)] border-2 border-dashed border-border bg-canvas py-10 text-center text-sm text-muted-foreground">
                연결할 이미지가 없습니다 🎉
              </div>
            ) : (
              pool.map((im) => (
                <div
                  key={im.id}
                  draggable
                  onDragStart={() => setDragId(im.id)}
                  onDragEnd={() => setDragId(null)}
                  title={im.original_filename ?? ""}
                  className={`group aspect-square cursor-grab overflow-hidden rounded-[var(--radius-lg)] border border-divider bg-subtle active:cursor-grabbing ${
                    dragId === im.id ? "opacity-50 ring-2 ring-ink" : ""
                  }`}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={publicImageUrl(im.storage_path)}
                    alt={im.original_filename ?? "이미지"}
                    className="h-full w-full object-cover transition group-hover:scale-105"
                  />
                </div>
              ))
            )}
          </div>

          <div className="mt-5 flex items-start gap-2 border-t border-divider pt-4 text-xs text-muted-foreground">
            <Info width={15} height={15} className="mt-0.5 shrink-0" />
            이미지를 왼쪽 상품 행으로 드래그하면 임시 매칭됩니다. ‘매칭 취소’로 되돌릴 수 있고, 상단 ‘저장’을 눌러야 확정돼요.
          </div>

          <div className="mt-4">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">매칭 진행률</span>
              <span className="font-bold text-foreground">{progress}%</span>
            </div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-subtle">
              <div
                className="h-full rounded-full bg-[var(--color-success-solid)] transition-all"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        </Card>
      </div>

      {/* 이탈 경고 모달 */}
      <Dialog
        open={leaving}
        onClose={dismissLeave}
        title="저장하지 않은 매칭이 있어요"
        footer={
          <>
            <Button variant="secondary" onClick={dismissLeave}>
              계속 작업하기
            </Button>
            <Button variant="danger" onClick={confirmLeave}>
              저장 안 하고 나가기
            </Button>
          </>
        }
      >
        <p className="text-sm leading-relaxed text-foreground">
          임시로 매칭한 <strong className="font-bold">{Object.keys(staged).length}건</strong>이 아직 저장되지 않았습니다.
          지금 나가면 이 매칭은 모두 사라져요.
        </p>
        <p className="mt-2 text-sm text-muted-foreground">
          내용을 남기려면 ‘계속 작업하기’ 후 상단 ‘저장’을 눌러 주세요.
        </p>
      </Dialog>

      {toast && (
        <div className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-[var(--radius)] bg-ink px-5 py-3 text-sm font-medium text-white shadow-[var(--shadow-lg)]">
          {toast}
        </div>
      )}
    </div>
  );
}
