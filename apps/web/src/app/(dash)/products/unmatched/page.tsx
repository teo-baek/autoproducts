"use client";
/* eslint-disable react-hooks/set-state-in-effect -- 잡/서버 데이터 동기화 목적의 의도된 effect */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
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
import { Badge, Button, Card } from "@/components/ui";
import { Filter, ImageIcon, Info, Save, Sort, Spinner, UploadCloud } from "@/components/icons";

export default function UnmatchedPage() {
  const [jobId, setJobId] = useState<string | null>(null);
  const [noJob, setNoJob] = useState(false);
  const [products, setProducts] = useState<Product[]>([]);
  const [images, setImages] = useState<ProductImage[]>([]);
  const [loading, setLoading] = useState(true);
  const [dragId, setDragId] = useState<string | null>(null);
  const [overPid, setOverPid] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

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
      setImages(imgs);
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

  async function onDropImage(p: Product) {
    setOverPid(null);
    if (!dragId || !jobId) return;
    const imageId = dragId;
    setDragId(null);
    try {
      await matchImage(jobId, imageId, p.source_p_number);
      setImages((prev) => prev.filter((im) => im.id !== imageId));
      setToast(`'${p.item_name}' 에 이미지를 매칭했습니다.`);
      load();
    } catch (e) {
      setToast(e instanceof Error ? e.message : "매칭 실패");
    }
  }

  const matchedCount = products.filter((p) => productThumb(p)).length;
  const score = products.length ? Math.round((matchedCount / products.length) * 100) : 0;

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
            업로드된 데이터와 이미지를 검토하고, 매칭되지 않은 이미지를 드래그 앤 드롭으로 연결하세요.
          </p>
        </div>
        <Button onClick={() => setToast("매칭 상태가 저장되었습니다.")}>
          <Save width={16} height={16} /> 저장
        </Button>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_20rem]">
        {/* 좌: 상품 데이터 */}
        <Card>
          <div className="flex items-center gap-3 border-b border-divider px-5 py-4">
            <div className="text-sm font-bold text-foreground">
              총 {products.length}개의 상품 데이터
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
          ) : products.length === 0 ? (
            <div className="py-20 text-center text-sm text-muted-foreground">상품이 없습니다.</div>
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
                  {products.map((p) => {
                    const thumb = productThumb(p);
                    const matched = !!thumb;
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
                            <Badge tone="success">매칭 완료</Badge>
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
              {images.length}
            </span>
          </div>

          <div className="mt-4 grid grid-cols-2 gap-3">
            {images.length === 0 ? (
              <div className="col-span-2 rounded-[var(--radius-lg)] border-2 border-dashed border-border bg-canvas py-10 text-center text-sm text-muted-foreground">
                미연결 이미지가 없습니다 🎉
              </div>
            ) : (
              images.map((im) => (
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
            이미지를 왼쪽 상품 행으로 드래그하여 수동 매칭을 완료할 수 있습니다.
          </div>

          <div className="mt-4">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">자동 매칭 점수</span>
              <span className="font-bold text-foreground">{score}%</span>
            </div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-subtle">
              <div
                className="h-full rounded-full bg-[var(--color-success-solid)] transition-all"
                style={{ width: `${score}%` }}
              />
            </div>
          </div>
        </Card>
      </div>

      {toast && (
        <div className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-[var(--radius)] bg-ink px-5 py-3 text-sm font-medium text-white shadow-[var(--shadow-lg)]">
          {toast}
        </div>
      )}
    </div>
  );
}
