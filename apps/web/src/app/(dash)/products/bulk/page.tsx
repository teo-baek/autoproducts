"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  attachImages,
  getMe,
  uploadExcel,
  uploadProductImage,
  type IngestResult,
} from "@/lib/products";
import { Stepper } from "@/components/Stepper";
import { Badge, Button, Card } from "@/components/ui";
import {
  AlertTriangle,
  Check,
  Cloud,
  Info,
  RefreshCw,
  Table as TableIcon,
  UploadCloud,
  X as XIcon,
} from "@/components/icons";

const STEPS = ["파일 업로드", "이미지 업로드", "데이터 검증", "등록 완료"];

type ImgItem = {
  file: File;
  name: string;
  size: number;
  status: "uploading" | "done" | "error";
  storage_path?: string;
};

export default function BulkPage() {
  const router = useRouter();
  const [wid, setWid] = useState("");
  const [step, setStep] = useState(0);

  // step 0
  const [excel, setExcel] = useState<File | null>(null);
  const [ingesting, setIngesting] = useState(false);
  const [ingest, setIngest] = useState<IngestResult | null>(null);
  const [ingestErr, setIngestErr] = useState<string | null>(null);

  // step 1
  const [images, setImages] = useState<ImgItem[]>([]);
  const [skipped, setSkipped] = useState(0); // 지원 안되는 형식(jpg/png 외) 제외 건수
  const [attaching, setAttaching] = useState(false);
  const [attachResult, setAttachResult] = useState<{ matched: string[]; unmatched: string[] } | null>(null);
  const [imgFailed, setImgFailed] = useState(false);

  useEffect(() => {
    getMe().then((me) => setWid(me.wholesaler_id ?? "")).catch(() => {});
  }, []);

  const errorStep =
    step === 2 && ingest && ingest.errors.length > 0 ? 2 : imgFailed && step === 1 ? 1 : undefined;

  /* ── step 0 → 1: 엑셀 인제스트 ── */
  async function goIngest() {
    if (!excel) return;
    setIngesting(true);
    setIngestErr(null);
    try {
      const res = await uploadExcel(excel);
      setIngest(res);
      setStep(1);
    } catch (e) {
      setIngestErr(e instanceof Error ? e.message : "파일 처리에 실패했습니다.");
    } finally {
      setIngesting(false);
    }
  }

  /* ── step 1: 이미지 업로드(스토리지 직접) ── */
  async function addImages(files: FileList | null) {
    if (!files || !wid) return;
    setImgFailed(false);
    const all = Array.from(files);
    const list = all.filter((f) => /\.(jpe?g|png)$/i.test(f.name));
    if (all.length - list.length > 0) setSkipped((s) => s + (all.length - list.length));
    const start = images.length;
    setImages((prev) => [
      ...prev,
      ...list.map((f) => ({ file: f, name: f.name, size: f.size, status: "uploading" as const })),
    ]);
    for (let i = 0; i < list.length; i++) {
      const f = list[i];
      const idx = start + i;
      try {
        const { storage_path } = await uploadProductImage(f, wid, `bulk/${Date.now()}-${i}-${f.name}`);
        setImages((prev) =>
          prev.map((it, j) => (j === idx ? { ...it, status: "done", storage_path } : it))
        );
      } catch {
        setImgFailed(true);
        setImages((prev) => prev.map((it, j) => (j === idx ? { ...it, status: "error" } : it)));
      }
    }
  }

  /* ── step 1 → 2: 매니페스트 자동매칭 ── */
  async function goAttach() {
    if (!ingest) return;
    const manifest = images
      .filter((i) => i.status === "done" && i.storage_path)
      .map((i) => ({ original_filename: i.name, storage_path: i.storage_path! }));
    setAttaching(true);
    try {
      if (manifest.length) {
        const res = await attachImages(ingest.job_id, manifest);
        setAttachResult({ matched: res.matched, unmatched: res.unmatched });
      } else {
        setAttachResult({ matched: [], unmatched: [] });
      }
      setStep(2);
    } catch {
      setImgFailed(true);
    } finally {
      setAttaching(false);
    }
  }

  function reset() {
    setStep(0);
    setExcel(null);
    setIngest(null);
    setIngestErr(null);
    setImages([]);
    setSkipped(0);
    setAttachResult(null);
    setImgFailed(false);
  }

  const createdCount = ingest?.created.length ?? 0;
  const errorCount = ingest?.errors.length ?? 0;
  const imgDone = images.filter((i) => i.status === "done").length;

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-6 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        상품 관리 › Bulk Registration
      </div>
      <h1 className="text-2xl font-extrabold tracking-tight text-foreground">대량 등록 마법사</h1>
      <p className="mt-1.5 text-sm text-muted-foreground">
        표준 엑셀(상품 데이터)과 제품 이미지를 업로드하여 마스터 카탈로그를 생성하세요.
      </p>

      <div className="my-9 px-2">
        <Stepper steps={STEPS} current={step} errorStep={errorStep} />
      </div>

      {step === 0 && (
        <StepFile
          excel={excel}
          onPick={setExcel}
          ingesting={ingesting}
          error={ingestErr}
          onNext={goIngest}
          onCancel={() => router.push("/products")}
        />
      )}

      {step === 1 &&
        (imgFailed ? (
          <StepImageError
            total={images.length}
            failed={images.filter((i) => i.status === "error").length}
            onRetry={() => setImgFailed(false)}
            onBack={() => setStep(0)}
            onNext={goAttach}
          />
        ) : (
          <StepImage
            images={images}
            skipped={skipped}
            onAdd={addImages}
            onRemove={(i) => setImages((prev) => prev.filter((_, j) => j !== i))}
            attaching={attaching}
            onBack={() => setStep(0)}
            onNext={goAttach}
          />
        ))}

      {step === 2 && (
        <StepValidate
          errors={ingest?.errors ?? []}
          onBack={() => setStep(1)}
          onNext={() => setStep(3)}
        />
      )}

      {step === 3 && (
        <StepDone
          created={createdCount}
          images={imgDone}
          errors={errorCount}
          unmatched={attachResult?.unmatched.length ?? 0}
          jobId={ingest?.job_id ?? ""}
          onRestart={reset}
        />
      )}
    </div>
  );
}

/* ── Step 1: 파일 업로드 ─────────────────────────────────────────────────── */
function StepFile({
  excel,
  onPick,
  ingesting,
  error,
  onNext,
  onCancel,
}: {
  excel: File | null;
  onPick: (f: File | null) => void;
  ingesting: boolean;
  error: string | null;
  onNext: () => void;
  onCancel: () => void;
}) {
  const ref = useRef<HTMLInputElement>(null);
  return (
    <Card className="p-7">
      <div className="text-xs font-semibold text-muted-foreground">1단계</div>
      <h2 className="mt-1 text-xl font-bold text-foreground">POS 데이터 파일 업로드</h2>

      <DropZone
        onClick={() => ref.current?.click()}
        onFiles={(f) => onPick(f[0] ?? null)}
        className="mt-6"
      >
        <span className="flex size-16 items-center justify-center rounded-full bg-[var(--color-info-bg)] text-[var(--color-info-fg)]">
          <UploadCloud width={26} height={26} />
        </span>
        {excel ? (
          <>
            <div className="mt-4 font-semibold text-foreground">{excel.name}</div>
            <div className="text-sm text-muted-foreground">{(excel.size / 1024).toFixed(0)} KB · 다시 선택하려면 클릭</div>
          </>
        ) : (
          <>
            <div className="mt-4 font-semibold text-foreground">드래그 앤 드롭 또는 클릭하여 파일 선택</div>
            <div className="text-sm text-muted-foreground">Excel (.xlsx) 파일을 업로드하세요.</div>
            <span className="mt-3 rounded-full bg-subtle px-3 py-1 text-xs font-medium text-muted-foreground">
              최대 용량: 50MB
            </span>
          </>
        )}
      </DropZone>
      <input
        ref={ref}
        type="file"
        accept=".xlsx,.csv"
        className="hidden"
        onChange={(e) => onPick(e.target.files?.[0] ?? null)}
      />

      <div className="mt-5 flex items-start gap-2.5 rounded-[var(--radius)] bg-surface-muted px-4 py-3.5 text-sm text-muted-foreground">
        <Info width={18} height={18} className="mt-0.5 shrink-0" />
        <span>
          처음이신가요?{" "}
          <button type="button" onClick={downloadSample} className="font-semibold text-ink underline">
            샘플 엑셀 템플릿 다운로드
          </button>
          를 통해 형식(품번·상품명·색상·사이즈·도매가·판매가)을 확인하세요.
        </span>
      </div>

      {error && (
        <div className="mt-4 rounded-[var(--radius)] bg-[var(--color-danger-bg)] px-4 py-3 text-sm text-[var(--color-danger-fg)]">
          {error}
        </div>
      )}

      <div className="mt-7 flex items-center justify-between border-t border-divider pt-5">
        <Button variant="secondary" onClick={onCancel}>
          취소
        </Button>
        <div className="flex items-center gap-3">
          {!excel && <span className="text-sm text-muted-foreground">필수 파일을 먼저 업로드해 주세요.</span>}
          <Button onClick={onNext} disabled={!excel} loading={ingesting}>
            다음 단계로
          </Button>
        </div>
      </div>
    </Card>
  );
}

/* ── Step 2: 이미지 업로드 ───────────────────────────────────────────────── */
function StepImage({
  images,
  skipped,
  onAdd,
  onRemove,
  attaching,
  onBack,
  onNext,
}: {
  images: ImgItem[];
  skipped: number;
  onAdd: (f: FileList | null) => void;
  onRemove: (i: number) => void;
  attaching: boolean;
  onBack: () => void;
  onNext: () => void;
}) {
  const ref = useRef<HTMLInputElement>(null);
  return (
    <div>
      <div className="text-xs font-semibold text-muted-foreground">2단계</div>
      <h2 className="mt-1 text-xl font-bold text-foreground">제품 이미지 업로드</h2>
      <p className="mt-1.5 text-sm text-muted-foreground">
        상품 데이터와 매칭할 제품 이미지를 업로드하세요. 파일명에 품번이 포함되면 자동 매칭됩니다. (선택)
      </p>

      <DropZone onClick={() => ref.current?.click()} onFiles={onAdd} className="mt-6">
        <span className="flex size-16 items-center justify-center rounded-full bg-surface-muted text-[var(--color-text-secondary)]">
          <Cloud width={26} height={26} />
        </span>
        <div className="mt-4 font-semibold text-foreground">이미지 파일을 드래그 앤 드롭하거나 클릭하여 선택하세요</div>
        <div className="text-sm text-muted-foreground">JPG, PNG 지원</div>
      </DropZone>
      <input
        ref={ref}
        type="file"
        accept="image/jpeg,image/png"
        multiple
        className="hidden"
        onChange={(e) => onAdd(e.target.files)}
      />

      {skipped > 0 && (
        <div className="mt-4 flex items-start gap-2.5 rounded-[var(--radius)] bg-[var(--color-warning-bg)] px-4 py-3 text-sm text-[var(--color-warning-fg)]">
          <AlertTriangle width={16} height={16} className="mt-0.5 shrink-0" />
          지원되지 않는 형식 {skipped}건이 제외되었습니다. (JPG·PNG만 허용)
        </div>
      )}

      {images.length > 0 && (
        <div className="mt-6">
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Currently Uploaded ({images.length})
          </div>
          <div className="space-y-2.5">
            {images.map((im, i) => (
              <Card key={`${im.name}-${i}`} className="flex items-center gap-3 px-4 py-3">
                <span className="flex size-9 shrink-0 items-center justify-center rounded-[var(--radius)] bg-subtle text-border-strong">
                  <TableIcon width={16} height={16} />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium text-foreground">{im.name}</div>
                  <div className="text-xs text-muted-foreground">{(im.size / 1024 / 1024).toFixed(1)} MB</div>
                </div>
                {im.status === "uploading" ? (
                  <span className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
                    <RefreshCw width={13} height={13} className="animate-spin" /> 업로드 중…
                  </span>
                ) : im.status === "error" ? (
                  <Badge tone="danger">실패</Badge>
                ) : (
                  <span className="flex items-center gap-1.5 text-xs font-semibold text-[var(--color-success-fg)]">
                    <Check width={13} height={13} /> 100%
                  </span>
                )}
                <button
                  type="button"
                  onClick={() => onRemove(i)}
                  className="text-border-strong transition hover:text-[var(--color-danger)]"
                  aria-label="제거"
                >
                  <XIcon width={16} height={16} />
                </button>
              </Card>
            ))}
          </div>
        </div>
      )}

      <div className="mt-7 flex items-center justify-end gap-3 border-t border-divider pt-5">
        <Button variant="secondary" onClick={onBack}>
          이전으로
        </Button>
        <Button onClick={onNext} loading={attaching}>
          다음 단계로
        </Button>
      </div>
    </div>
  );
}

/* ── Step 2 (에러): 이미지 업로드 실패 ──────────────────────────────────── */
function StepImageError({
  total,
  failed,
  onRetry,
  onBack,
  onNext,
}: {
  total: number;
  failed: number;
  onRetry: () => void;
  onBack: () => void;
  onNext: () => void;
}) {
  return (
    <div className="text-center">
      <div className="text-left text-xs font-semibold text-muted-foreground">2단계</div>
      <h2 className="mb-8 mt-1 text-left text-xl font-bold text-foreground">제품 이미지 업로드</h2>

      <span className="mx-auto flex size-20 items-center justify-center rounded-full bg-[var(--color-danger-bg)] text-[var(--color-danger)]">
        <AlertTriangle width={34} height={34} />
      </span>
      <h3 className="mt-6 text-xl font-bold text-foreground">제품 이미지 업로드 실패</h3>
      <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-muted-foreground">
        전체 {total}개의 이미지 중 {failed}개의 파일 업로드가 중단되었습니다.
      </p>

      <Card className="mx-auto mt-6 max-w-lg p-5 text-left">
        <div className="flex items-center gap-2 text-sm font-bold text-[var(--color-danger-fg)]">
          <AlertTriangle width={16} height={16} /> 오류 상세 내역
        </div>
        <div className="mt-3 space-y-3 border-t border-divider pt-3 text-sm">
          <div>
            <div className="font-semibold text-[var(--color-danger-fg)]">스토리지 업로드 실패</div>
            <p className="text-muted-foreground">
              일부 파일이 Storage(product-images 버킷)에 업로드되지 못했습니다. 버킷 생성 여부와 네트워크 상태를 확인해 주세요.
            </p>
          </div>
        </div>
      </Card>

      <div className="mt-7 flex items-center justify-end gap-3 border-t border-divider pt-5">
        <Button variant="secondary" onClick={onRetry}>
          <RefreshCw width={15} height={15} /> 업로드 재시도
        </Button>
        <Button variant="secondary" onClick={onBack}>
          이전으로
        </Button>
        <Button onClick={onNext}>다음 단계로</Button>
      </div>
    </div>
  );
}

/* ── Step 3: 데이터 검증 ─────────────────────────────────────────────────── */
function StepValidate({
  errors,
  onBack,
  onNext,
}: {
  errors: IngestResult["errors"];
  onBack: () => void;
  onNext: () => void;
}) {
  const ok = errors.length === 0;
  return (
    <div className="text-center">
      <div className="text-left text-xs font-semibold text-muted-foreground">3단계</div>
      <h2 className="mt-1 text-left text-xl font-bold text-foreground">데이터 유효성 검사</h2>

      <h3 className="mt-6 text-3xl font-extrabold tracking-tight text-foreground">데이터 유효성 검사 결과</h3>
      <p className="mt-3 flex items-center justify-center gap-2 text-sm">
        {ok ? (
          <span className="flex items-center gap-1.5 font-semibold text-[var(--color-success-fg)]">
            <Check width={16} height={16} /> 오류가 발견되지 않았습니다.
          </span>
        ) : (
          <span className="flex items-center gap-1.5 font-semibold text-[var(--color-danger-fg)]">
            <AlertTriangle width={16} height={16} /> 총 <b>{errors.length}</b>건의 오류가 발견되었습니다.
          </span>
        )}
      </p>

      <Card className="mx-auto mt-6 max-w-2xl overflow-hidden text-left">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-divider bg-surface-muted text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              <th className="px-5 py-3">행 (Row)</th>
              <th className="px-5 py-3">필드 (Field)</th>
              <th className="px-5 py-3">오류 내용 (Error Description)</th>
            </tr>
          </thead>
          <tbody>
            {ok ? (
              <tr>
                <td colSpan={3} className="px-5 py-10 text-center text-muted-foreground">
                  모든 행이 정상 처리되었습니다.
                </td>
              </tr>
            ) : (
              errors.slice(0, 50).map((e, i) => (
                <tr key={i} className="border-b border-divider/70 last:border-0">
                  <td className="px-5 py-3.5 text-muted-foreground">{e.row != null ? `${e.row}행` : "—"}</td>
                  <td className="px-5 py-3.5 font-medium text-foreground">
                    {e.field ?? (e.source_p_number ? `품번 ${e.source_p_number}` : "—")}
                  </td>
                  <td className="px-5 py-3.5 font-medium text-[var(--color-danger-fg)]">{e.reason}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
        {errors.length > 50 && (
          <div className="border-t border-divider bg-surface-muted px-5 py-2.5 text-xs text-muted-foreground">
            표시 중: 1 – 50 / {errors.length}
          </div>
        )}
      </Card>

      <div className="mt-7 flex items-center justify-end gap-3 border-t border-divider pt-5">
        {!ok && (
          <Button variant="secondary" onClick={onNext}>
            오류 건너뛰기
          </Button>
        )}
        <Button variant="secondary" onClick={onBack}>
          이전으로
        </Button>
        <Button onClick={onNext}>다음 단계로</Button>
      </div>
    </div>
  );
}

/* ── Step 4: 완료 ────────────────────────────────────────────────────────── */
function StepDone({
  created,
  images,
  errors,
  unmatched,
  jobId,
  onRestart,
}: {
  created: number;
  images: number;
  errors: number;
  unmatched: number;
  jobId: string;
  onRestart: () => void;
}) {
  return (
    <div className="text-center">
      <span className="mx-auto flex size-20 items-center justify-center rounded-full bg-[var(--color-success-bg)] text-[var(--color-success-fg)]">
        <Check width={34} height={34} />
      </span>
      <h2 className="mt-6 text-2xl font-extrabold tracking-tight text-foreground">상품 등록 완료</h2>
      <p className="mt-2 text-sm text-muted-foreground">일괄 업로드 작업이 처리되었습니다.</p>

      <Card className="mx-auto mt-7 max-w-2xl p-7 text-left">
        <h3 className="text-lg font-bold text-foreground">요약</h3>
        <div className="mt-5 grid grid-cols-3 gap-4 border-t border-divider pt-5">
          <Summary label="등록된 상품" value={created} unit="건" />
          <Summary label="처리된 이미지" value={images} unit="개" />
          <div>
            <div className="text-sm text-muted-foreground">데이터 검증</div>
            <div className="mt-1.5">
              {errors === 0 ? (
                <span className="inline-flex items-center gap-1.5 text-base font-bold text-[var(--color-success-fg)]">
                  <Check width={18} height={18} /> Verified
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 text-base font-bold text-[var(--color-danger-fg)]">
                  <AlertTriangle width={18} height={18} /> 오류 {errors}건
                </span>
              )}
            </div>
          </div>
        </div>
      </Card>

      {unmatched > 0 && (
        <div className="mx-auto mt-5 flex max-w-2xl items-start gap-2.5 rounded-[var(--radius)] bg-[var(--color-warning-bg)] px-4 py-3.5 text-left text-sm text-[var(--color-warning-fg)]">
          <Info width={18} height={18} className="mt-0.5 shrink-0" />
          <span>
            {unmatched}개의 이미지가 품번과 매칭되지 않았습니다.{" "}
            <Link
              href={`/products/unmatched?job=${jobId}`}
              className="font-bold underline"
            >
              미매칭 상품 관리
            </Link>
            에서 수동으로 연결하세요.
          </span>
        </div>
      )}

      <div className="mt-7 flex items-center justify-center gap-3">
        <Button variant="secondary" onClick={onRestart}>
          새로운 업로드 시작
        </Button>
        <Link href="/products">
          <Button>전체 상품 보기</Button>
        </Link>
      </div>
    </div>
  );
}

function Summary({ label, value, unit }: { label: string; value: number; unit: string }) {
  return (
    <div>
      <div className="text-sm text-muted-foreground">{label}</div>
      <div className="mt-1 text-3xl font-extrabold tabular-nums text-foreground">
        {value}
        <span className="ml-1 text-base font-semibold text-muted-foreground">{unit}</span>
      </div>
    </div>
  );
}

/* ── 공용 드롭존 ────────────────────────────────────────────────────────── */
function DropZone({
  children,
  onClick,
  onFiles,
  className = "",
}: {
  children: React.ReactNode;
  onClick: () => void;
  onFiles: (f: FileList) => void;
  className?: string;
}) {
  const [over, setOver] = useState(false);
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onClick()}
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        if (e.dataTransfer.files?.length) onFiles(e.dataTransfer.files);
      }}
      className={`flex cursor-pointer flex-col items-center justify-center rounded-[var(--radius-lg)] border-2 border-dashed px-6 py-14 text-center transition ${
        over ? "border-ink bg-subtle" : "border-border bg-canvas hover:border-ink/40"
      } ${className}`}
    >
      {children}
    </div>
  );
}

/* 샘플 템플릿(CSV) — 표준 컬럼 가이드. */
function downloadSample() {
  const rows = [
    ["품번", "상품명", "색상", "사이즈", "도매가", "판매가"],
    ["F-SLK-001", "미니멀 실크 블라우스", "아이보리", "S", "180000", "290000"],
    ["F-SLK-001", "미니멀 실크 블라우스", "아이보리", "M", "180000", "290000"],
    ["O-COA-885", "클래식 울 오버코트", "차콜", "L", "420000", "690000"],
  ];
  const csv = "﻿" + rows.map((r) => r.join(",")).join("\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = "ezmerce-product-template.csv";
  a.click();
  URL.revokeObjectURL(url);
}
