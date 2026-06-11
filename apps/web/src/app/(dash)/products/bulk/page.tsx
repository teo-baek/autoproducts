"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  commitUpload,
  getMe,
  stageZip,
  uploadProductImage,
  validateExcel,
  type CommitResult,
  type ExcelPreview,
  type ImageManifestItem,
} from "@/lib/products";
import { Stepper } from "@/components/Stepper";
import { Badge, Button, Card, Dialog } from "@/components/ui";
import {
  AlertTriangle,
  Archive,
  Check,
  Cloud,
  ImageIcon,
  Info,
  RefreshCw,
  UploadCloud,
  X as XIcon,
} from "@/components/icons";

const STEPS = ["파일 업로드", "이미지 업로드", "데이터 검증", "등록 완료"];
const MAX_ZIP_MB = 100; // 서버 uploads.py _ZIP_MAX_BYTES 와 일치(운영 512Mi 메모리 보호)
const MAX_ZIP_BYTES = MAX_ZIP_MB * 1024 * 1024;

type ImgItem = {
  file: File;
  name: string;
  size: number;
  kind: "image" | "zip";
  status: "uploading" | "done" | "error";
  storage_path?: string; // 개별 이미지(스토리지 직접 업로드 경로)
  loaded?: number; // zip 진행률(바이트)
  total?: number;
  manifest?: ImageManifestItem[]; // zip staging 산출 매니페스트(커밋 때 합쳐 매칭)
};

export default function BulkPage() {
  const router = useRouter();
  const [wid, setWid] = useState("");
  const [step, setStep] = useState(0);

  // step 0 — 엑셀 검증(드라이런). 실제 저장은 4단계 commit 에서.
  const [excel, setExcel] = useState<File | null>(null);
  const [validating, setValidating] = useState(false);
  const [preview, setPreview] = useState<ExcelPreview | null>(null);
  const [validateErr, setValidateErr] = useState<string | null>(null);

  // step 1 — 이미지 Storage 업로드 / ZIP staging (등록 X)
  const [images, setImages] = useState<ImgItem[]>([]);
  const [skipped, setSkipped] = useState(0); // 지원 안되는 형식(jpg/png/zip 외) 제외 건수
  const [imgFailed, setImgFailed] = useState(false);
  const [imgErrMsg, setImgErrMsg] = useState<string | null>(null); // 업로드 실패 친화 메시지
  const [bigZipMsg, setBigZipMsg] = useState<string | null>(null); // 용량 초과 ZIP 안내(비차단)

  // step 2 → 3 — commit(상품 생성 + 이미지 매칭)
  const [committing, setCommitting] = useState(false);
  const [commitErr, setCommitErr] = useState<string | null>(null);
  const [commitResult, setCommitResult] = useState<CommitResult | null>(null);

  // '이전으로' 확인 모달 — 누르면 즉시 이동 대신 경고 후 진행(오클릭 방지).
  // pendingBack = 확인 시 실행할 이동 콜백(없으면 모달 닫힘).
  const [pendingBack, setPendingBack] = useState<(() => void) | null>(null);
  const requestBack = (fn: () => void) => setPendingBack(() => fn); // setState 에 함수 저장(즉시호출 방지)

  useEffect(() => {
    getMe().then((me) => setWid(me.wholesaler_id ?? "")).catch(() => {});
  }, []);

  const errorStep =
    step === 2 && preview && preview.errors.length > 0 ? 2 : imgFailed && step === 1 ? 1 : undefined;

  /* ── step 0 → 1: 엑셀 검증(드라이런 — 저장 안 함) ── */
  async function goValidate() {
    if (!excel) return;
    setValidating(true);
    setValidateErr(null);
    try {
      const res = await validateExcel(excel);
      setPreview(res);
      setStep(1);
    } catch (e) {
      setValidateErr(e instanceof Error ? e.message : "파일 검증에 실패했습니다.");
    } finally {
      setValidating(false);
    }
  }

  /* ── step 1: 이미지 Storage 업로드 / ZIP staging (등록은 4단계 commit 에서) ── */
  async function addImages(files: FileList | null) {
    if (!files || !wid) return;
    setImgFailed(false);
    setImgErrMsg(null);
    setBigZipMsg(null);
    const all = Array.from(files);
    const imgs = all.filter((f) => /\.(jpe?g|png)$/i.test(f.name));
    const allZips = all.filter((f) => /\.zip$/i.test(f.name));
    const zips = allZips.filter((f) => f.size <= MAX_ZIP_BYTES);
    const bigZips = allZips.filter((f) => f.size > MAX_ZIP_BYTES);
    const skip = all.length - imgs.length - allZips.length;
    if (skip > 0) setSkipped((s) => s + skip);
    if (bigZips.length) {
      // 차단형 에러 화면 대신 비차단 안내 — 나머지는 정상 진행
      setBigZipMsg(
        `${bigZips.map((f) => f.name).join(", ")} — ZIP은 최대 ${MAX_ZIP_MB}MB까지 올릴 수 있어요. 사진을 나눠서 올려주세요.`
      );
    }

    const stamp = Date.now();
    const start = images.length;
    setImages((prev) => [
      ...prev,
      ...imgs.map((f) => ({ file: f, name: f.name, size: f.size, kind: "image" as const, status: "uploading" as const })),
      ...zips.map((f) => ({
        file: f, name: f.name, size: f.size, kind: "zip" as const,
        status: "uploading" as const, loaded: 0, total: f.size,
      })),
    ]);

    // 개별 이미지 → 스토리지 직접 업로드 (매니페스트는 commit 때 합침)
    for (let i = 0; i < imgs.length; i++) {
      const f = imgs[i];
      const idx = start + i;
      try {
        // 저장 키는 ASCII(인덱스)만 — 한글 파일명은 매니페스트 original_filename 으로 따로 전달(매칭용)
        const { storage_path } = await uploadProductImage(f, wid, `bulk/${stamp}-${i}`);
        setImages((prev) => prev.map((it, j) => (j === idx ? { ...it, status: "done", storage_path } : it)));
      } catch (e) {
        setImgFailed(true);
        setImgErrMsg(e instanceof Error ? e.message : null);
        setImages((prev) => prev.map((it, j) => (j === idx ? { ...it, status: "error" } : it)));
      }
    }

    // ZIP → Storage staging(압축해제+썸네일). 등록/매칭은 commit 때. 진행률 표시.
    for (let z = 0; z < zips.length; z++) {
      const f = zips[z];
      const idx = start + imgs.length + z;
      try {
        const res = await stageZip(f, (loaded, total) =>
          setImages((prev) => prev.map((it, j) => (j === idx ? { ...it, loaded, total } : it)))
        );
        setImages((prev) =>
          prev.map((it, j) =>
            j === idx ? { ...it, status: "done", loaded: it.total, manifest: res.manifest } : it
          )
        );
      } catch (e) {
        setImgFailed(true);
        setImgErrMsg(e instanceof Error ? e.message : null);
        setImages((prev) => prev.map((it, j) => (j === idx ? { ...it, status: "error" } : it)));
      }
    }
  }

  /* ── step 2 → 3: 커밋 — 상품 생성 + 이미지 매칭을 한 번에(여기서 처음 DB 저장) ── */
  async function goCommit() {
    if (!excel || committing) return;
    const manifest: ImageManifestItem[] = [];
    for (const it of images) {
      if (it.status !== "done") continue;
      if (it.kind === "image" && it.storage_path) {
        manifest.push({ original_filename: it.name, storage_path: it.storage_path });
      } else if (it.kind === "zip" && it.manifest) {
        manifest.push(...it.manifest);
      }
    }
    setCommitting(true);
    setCommitErr(null);
    try {
      const res = await commitUpload(excel, manifest);
      setCommitResult(res);
      setStep(3);
    } catch (e) {
      setCommitErr(e instanceof Error ? e.message : "상품 등록에 실패했습니다.");
    } finally {
      setCommitting(false);
    }
  }

  function reset() {
    setStep(0);
    setExcel(null);
    setValidating(false);
    setPreview(null);
    setValidateErr(null);
    setImages([]);
    setSkipped(0);
    setImgFailed(false);
    setImgErrMsg(null);
    setBigZipMsg(null);
    setCommitting(false);
    setCommitErr(null);
    setCommitResult(null);
  }

  const createdCount = commitResult?.created.length ?? 0;
  const errorCount = commitResult?.errors.length ?? 0;
  const imgDone = (commitResult?.matched.length ?? 0) + (commitResult?.unmatched.length ?? 0);

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-6 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        상품 관리 › Bulk Registration
      </div>
      <h1 className="text-2xl font-extrabold tracking-tight text-foreground">대량 등록 마법사</h1>
      <p className="mt-1.5 text-sm text-muted-foreground">
        표준 엑셀(상품 데이터)과 제품 이미지를 올리면, 마지막 “완료” 단계에서 한 번에 등록됩니다.
      </p>

      <div className="my-9 px-2">
        <Stepper steps={STEPS} current={step} errorStep={errorStep} />
      </div>

      {step === 0 && (
        <StepFile
          excel={excel}
          onPick={setExcel}
          ingesting={validating}
          error={validateErr}
          onNext={goValidate}
          onCancel={() => router.push("/products")}
        />
      )}

      {step === 1 &&
        (imgFailed ? (
          <StepImageError
            total={images.length}
            failed={images.filter((i) => i.status === "error").length}
            message={imgErrMsg}
            onRetry={() => {
              setImgFailed(false);
              setImgErrMsg(null);
            }}
            onBack={() => requestBack(() => setStep(0))}
            onNext={() => setStep(2)}
          />
        ) : (
          <StepImage
            images={images}
            skipped={skipped}
            bigZipMsg={bigZipMsg}
            onAdd={addImages}
            onRemove={(i) => setImages((prev) => prev.filter((_, j) => j !== i))}
            onBack={() => requestBack(() => setStep(0))}
            onNext={() => setStep(2)}
          />
        ))}

      {step === 2 && (
        <StepValidate
          errors={preview?.errors ?? []}
          dropped={preview?.dropped ?? 0}
          committing={committing}
          commitErr={commitErr}
          onBack={() => requestBack(() => setStep(1))}
          onNext={goCommit}
        />
      )}

      {step === 3 && (
        <StepDone
          created={createdCount}
          images={imgDone}
          errors={errorCount}
          unmatched={commitResult?.unmatched.length ?? 0}
          jobId={commitResult?.job_id ?? ""}
          onRestart={reset}
        />
      )}

      {/* '이전으로' 확인 모달 — 오클릭 방지. 확인 시 보관해 둔 이동 콜백 실행. */}
      <Dialog
        open={pendingBack !== null}
        onClose={() => setPendingBack(null)}
        size="sm"
        icon={<AlertTriangle width={18} height={18} />}
        title="이전 단계로 이동할까요?"
        footer={
          <>
            <Button variant="secondary" onClick={() => setPendingBack(null)}>
              머무르기
            </Button>
            <Button
              variant="danger"
              onClick={() => {
                pendingBack?.();
                setPendingBack(null);
              }}
            >
              이전으로
            </Button>
          </>
        }
      >
        <p className="text-sm leading-relaxed text-muted-foreground">
          이전 단계로 돌아가면 현재 단계에서 진행한 내용이 꼬이거나 다시 작업해야 할 수 있어요. 그래도 이동하시겠어요?
        </p>
      </Dialog>
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
            <div className="text-sm text-muted-foreground">Excel (.xlsx / .xls) 또는 CSV (.csv) 파일을 업로드하세요.</div>
            <span className="mt-3 rounded-full bg-subtle px-3 py-1 text-xs font-medium text-muted-foreground">
              최대 용량: 50MB
            </span>
          </>
        )}
      </DropZone>
      <input
        ref={ref}
        type="file"
        accept=".xlsx,.xls,.csv"
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
  bigZipMsg,
  onAdd,
  onRemove,
  onBack,
  onNext,
}: {
  images: ImgItem[];
  skipped: number;
  bigZipMsg: string | null;
  onAdd: (f: FileList | null) => void;
  onRemove: (i: number) => void;
  onBack: () => void;
  onNext: () => void;
}) {
  const ref = useRef<HTMLInputElement>(null);
  const busy = images.some((i) => i.status === "uploading"); // 업로드 진행 중엔 다음 단계 잠금
  return (
    <div>
      <div className="text-xs font-semibold text-muted-foreground">2단계</div>
      <h2 className="mt-1 text-xl font-bold text-foreground">제품 이미지 업로드</h2>
      <p className="mt-1.5 text-sm text-muted-foreground">
        상품 데이터와 매칭할 제품 이미지들을 업로드하세요. 압축 파일(.zip) 또는 여러 개별 파일을 한꺼번에 올릴 수 있습니다.
      </p>

      <DropZone onClick={() => ref.current?.click()} onFiles={onAdd} className="mt-6">
        <span className="flex size-16 items-center justify-center rounded-full bg-surface-muted text-[var(--color-text-secondary)]">
          <Cloud width={26} height={26} />
        </span>
        <div className="mt-4 font-semibold text-foreground">이미지 파일을 드래그 앤 드롭하거나 클릭하여 선택하세요</div>
        <span className="mt-3 rounded-full bg-subtle px-3 py-1 text-xs font-medium text-muted-foreground">
          JPG · PNG · ZIP 지원 · ZIP 1개당 최대 {MAX_ZIP_MB}MB
        </span>
      </DropZone>
      <input
        ref={ref}
        type="file"
        accept="image/jpeg,image/png,.zip,application/zip,application/x-zip-compressed"
        multiple
        className="hidden"
        onChange={(e) => onAdd(e.target.files)}
      />

      {skipped > 0 && (
        <div className="mt-4 flex items-start gap-2.5 rounded-[var(--radius)] bg-[var(--color-warning-bg)] px-4 py-3 text-sm text-[var(--color-warning-fg)]">
          <AlertTriangle width={16} height={16} className="mt-0.5 shrink-0" />
          지원되지 않는 형식 {skipped}건이 제외되었습니다. (JPG·PNG·ZIP만 허용)
        </div>
      )}

      {bigZipMsg && (
        <div className="mt-4 flex items-start gap-2.5 rounded-[var(--radius)] bg-[var(--color-warning-bg)] px-4 py-3 text-sm text-[var(--color-warning-fg)]">
          <AlertTriangle width={16} height={16} className="mt-0.5 shrink-0" />
          {bigZipMsg}
        </div>
      )}

      {images.length > 0 && (
        <div className="mt-6">
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Currently Uploaded ({images.length})
          </div>
          <div className="space-y-2.5">
            {images.map((im, i) => (
              <ImageRow key={`${im.name}-${i}`} im={im} onRemove={() => onRemove(i)} />
            ))}
          </div>
        </div>
      )}

      <div className="mt-7 flex items-center justify-end gap-3 border-t border-divider pt-5">
        <Button variant="secondary" onClick={onBack}>
          이전으로
        </Button>
        <Button onClick={onNext} disabled={busy}>
          {busy ? "업로드 중…" : "다음 단계로"}
        </Button>
      </div>
    </div>
  );
}

function fmtMB(b: number) {
  return `${(b / 1024 / 1024).toFixed(1)} MB`;
}

/* 업로드 항목 1줄 — 개별 이미지 / ZIP(진행바) 공용. 시안(2페이지) 대응. */
function ImageRow({ im, onRemove }: { im: ImgItem; onRemove: () => void }) {
  const isZip = im.kind === "zip";
  const pct =
    im.status === "done"
      ? 100
      : im.total && im.loaded != null
        ? Math.min(99, Math.round((im.loaded / im.total) * 100))
        : 0;
  return (
    <Card className="overflow-hidden px-4 py-3">
      <div className="flex items-center gap-3">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-[var(--radius)] bg-subtle text-border-strong">
          {isZip ? <Archive width={16} height={16} /> : <ImageIcon width={16} height={16} />}
        </span>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-medium text-foreground">{im.name}</div>
          <div className="text-xs text-muted-foreground">
            {isZip && im.status === "uploading" && im.total
              ? `${fmtMB(im.loaded ?? 0)} / ${fmtMB(im.total)}`
              : fmtMB(im.size)}
          </div>
        </div>
        {im.status === "uploading" ? (
          <div className="flex flex-col items-end gap-0.5 text-xs font-semibold text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <RefreshCw width={13} height={13} className="animate-spin" />
              {isZip ? `${pct}%` : "업로드 중…"}
            </span>
            {isZip && <span className="text-[11px] text-muted-foreground">업로드 중…</span>}
          </div>
        ) : im.status === "error" ? (
          <Badge tone="danger">실패</Badge>
        ) : (
          <span className="flex items-center gap-1.5 text-xs font-semibold text-[var(--color-success-fg)]">
            <Check width={13} height={13} /> 100%
          </span>
        )}
        <button
          type="button"
          onClick={onRemove}
          className="text-border-strong transition hover:text-[var(--color-danger)]"
          aria-label="제거"
        >
          <XIcon width={16} height={16} />
        </button>
      </div>

      {isZip && im.status === "uploading" && (
        <div className="mt-2.5 h-1.5 w-full overflow-hidden rounded-full bg-subtle">
          <div className="h-full rounded-full bg-ink transition-all" style={{ width: `${pct}%` }} />
        </div>
      )}
    </Card>
  );
}

/* ── Step 2 (에러): 이미지 업로드 실패 ──────────────────────────────────── */
function StepImageError({
  total,
  failed,
  message,
  onRetry,
  onBack,
  onNext,
}: {
  total: number;
  failed: number;
  message: string | null;
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
            <div className="font-semibold text-[var(--color-danger-fg)]">업로드 실패</div>
            <p className="text-muted-foreground">
              {message ?? "일부 파일을 업로드하지 못했습니다. 네트워크 상태를 확인한 뒤 다시 시도해 주세요."}
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
  dropped,
  committing,
  commitErr,
  onBack,
  onNext,
}: {
  errors: ExcelPreview["errors"];
  dropped: number;
  committing: boolean;
  commitErr: string | null;
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

      {dropped > 0 && (
        <div className="mx-auto mt-4 flex max-w-2xl items-start gap-2.5 rounded-[var(--radius)] bg-surface-muted px-4 py-3 text-left text-sm text-muted-foreground">
          <Info width={16} height={16} className="mt-0.5 shrink-0" />
          품번이 없는 {dropped}개 행은 자동으로 제외했습니다.
        </div>
      )}

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

      {commitErr && (
        <div className="mx-auto mt-5 max-w-2xl rounded-[var(--radius)] bg-[var(--color-danger-bg)] px-4 py-3 text-left text-sm text-[var(--color-danger-fg)]">
          {commitErr}
        </div>
      )}

      <p className="mt-6 text-xs text-muted-foreground">
        “{ok ? "상품 등록" : "오류 건너뛰고 등록"}”을 누르면 이때 실제로 상품이 등록됩니다.
      </p>
      <div className="mt-3 flex items-center justify-end gap-3 border-t border-divider pt-5">
        <Button variant="secondary" onClick={onBack} disabled={committing}>
          이전으로
        </Button>
        <Button onClick={onNext} loading={committing}>
          {ok ? "상품 등록" : "오류 건너뛰고 등록"}
        </Button>
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
