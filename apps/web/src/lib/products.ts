import { api, API_BASE } from "./api";
import { supabase } from "./supabase";

/* ── 타입 (백엔드 셰이핑과 1:1) ─────────────────────────────────────────── */
export type Me = {
  id: string;
  role: string;
  status: string;
  seller_type: string | null;
  wholesaler_id: string | null;
  agency_id: string | null;
  price_visibility: string | null;
  company_name: string | null;
};

export type Sku = {
  id?: string;
  color: string;
  size: string;
  wholesale_price: number;
  retail_price: number | null;
  stock: number;
};

export type ProductImage = {
  id: string;
  storage_path: string;
  original_filename: string | null;
  is_representative: boolean;
  match_status: string | null;
};

export type Product = {
  id: string;
  platform_code: string;
  source_p_number: string;
  item_name: string;
  category: string | null;
  fabric_composition: string | null;
  origin: string | null;
  lead_time_days: string | null;
  description: string | null;
  representative_image_url: string | null;
  status: string;
  is_sold_out: boolean;
  created_at: string | null;
  skus: Sku[];
  images: ProductImage[];
};

export type ProductList = {
  items: Product[];
  total: number;
  limit: number;
  offset: number;
};

export type Job = {
  id: string;
  status: string;
  total_rows: number;
  matched_rows: number;
  error_rows: number;
  error_detail: unknown;
  file_path: string | null;
  created_at: string | null;
  completed_at: string | null;
};

export type ProductCreatePayload = {
  source_p_number: string;
  item_name: string;
  category?: string | null;
  fabric_composition?: string | null;
  origin?: string | null;
  description?: string | null;
  skus: Omit<Sku, "id">[];
};

/* ── 상수 ───────────────────────────────────────────────────────────────── */
export const PRODUCT_BUCKET = "product-images";
export const CATEGORY_OPTIONS = [
  { value: "의류", label: "의류" },
  { value: "잡화", label: "잡화" },
];

/* ── 사용자 ─────────────────────────────────────────────────────────────── */
export const getMe = () => api<Me>("/auth/me", { auth: true });

/* ── 관리자(admin) — 계정 승인 ─────────────────────────────────────────── */
export type Account = {
  id: string;
  email: string | null;
  role: string;
  status: string;
  seller_type: string | null;
  company_name: string | null;
  full_name: string | null;
  wholesaler_id: string | null;
  price_visibility: string | null;
  created_at?: string | null;
};

export const listAccounts = (status: string) =>
  api<Account[]>(`/admin/accounts?status=${encodeURIComponent(status)}`, { auth: true });
export const approveAccount = (uid: string) =>
  api(`/admin/accounts/${uid}/approve`, { method: "POST", auth: true });
export const rejectAccount = (uid: string) =>
  api(`/admin/accounts/${uid}/reject`, { method: "POST", auth: true });

export const ROLE_LABEL: Record<string, string> = {
  admin: "관리자",
  wholesaler: "도매",
  retail_seller: "소매셀러",
  agency: "에이전시",
};
export const SELLER_TYPE_LABEL: Record<string, string> = {
  independent: "라이브셀러",
  agency_affiliated: "에이전시 소속",
};

/* ── 상품 CRUD ──────────────────────────────────────────────────────────── */
export function listProducts(params: {
  limit?: number;
  offset?: number;
  category?: string;
  search?: string;
  status?: string;
} = {}): Promise<ProductList> {
  const q = new URLSearchParams();
  if (params.limit != null) q.set("limit", String(params.limit));
  if (params.offset != null) q.set("offset", String(params.offset));
  if (params.category) q.set("category", params.category);
  if (params.search) q.set("search", params.search);
  if (params.status) q.set("status", params.status);
  const qs = q.toString();
  return api<ProductList>(`/products${qs ? `?${qs}` : ""}`, { auth: true });
}

export const getProduct = (id: string) => api<Product>(`/products/${id}`, { auth: true });

export const createProduct = (payload: ProductCreatePayload) =>
  api<Product>("/products", { method: "POST", body: JSON.stringify(payload), auth: true });

export const updateProduct = (id: string, patch: Record<string, unknown>) =>
  api<Product>(`/products/${id}`, { method: "PATCH", body: JSON.stringify(patch), auth: true });

export const replaceSkus = (id: string, skus: Omit<Sku, "id">[]) =>
  api<Product>(`/products/${id}/skus`, {
    method: "PUT",
    body: JSON.stringify({ skus }),
    auth: true,
  });

export const archiveProduct = (id: string) => updateProduct(id, { status: "archived" });
export const restoreProduct = (id: string) => updateProduct(id, { status: "active" });
export const deleteProduct = (id: string) =>
  api(`/products/${id}`, { method: "DELETE", auth: true });

/* ── 업로드 / 매칭 ──────────────────────────────────────────────────────── */
export type ParseError = { row?: number; field?: string; reason: string; source_p_number?: string };
export type ImageManifestItem = {
  original_filename: string;
  storage_path: string;
  thumbnail_path?: string | null;
};

// 1단계 검증(드라이런) 결과 — DB 미기록
export type ExcelPreview = {
  product_count: number;
  sku_count: number;
  errors: ParseError[];
  dropped: number;
};

// 2단계 ZIP staging 결과 — 매니페스트만(아직 등록 X)
export type StageResult = {
  manifest: ImageManifestItem[];
  processed: { ok: number; none: number; error: number };
};

// 4단계 커밋 결과 — 상품 생성 + 이미지 매칭
export type CommitResult = {
  job_id: string;
  created: unknown[];
  errors: ParseError[];
  dropped: number;
  matched: string[];
  unmatched: string[];
};

// 1단계: 엑셀 검증만(드라이런). 상품은 4단계 commit 에서 저장.
export function validateExcel(file: File): Promise<ExcelPreview> {
  const fd = new FormData();
  fd.append("file", file);
  return api<ExcelPreview>("/uploads/excel/validate", { method: "POST", body: fd, auth: true });
}

// 멀티파트 + 업로드 진행률(XHR) 공용 헬퍼. fetch 는 업로드 진행률 미지원이라 XHR 사용.
async function xhrUpload<T>(
  path: string,
  fd: FormData,
  onProgress?: (loaded: number, total: number) => void
): Promise<T> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  return new Promise<T>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}${path}`);
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress?.(e.loaded, e.total);
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as T);
        } catch {
          reject(new Error("서버 응답을 해석하지 못했습니다."));
        }
      } else {
        let detail = `업로드 실패 (${xhr.status})`;
        try {
          const b = JSON.parse(xhr.responseText);
          if (b?.detail) detail = typeof b.detail === "string" ? b.detail : JSON.stringify(b.detail);
        } catch {
          /* 본문 없음 */
        }
        reject(new Error(detail));
      }
    };
    xhr.onerror = () => reject(new Error("네트워크 오류로 업로드에 실패했습니다."));
    xhr.send(fd);
  });
}

// 2단계: ZIP 을 Storage(staging) 에 올리고 매니페스트만 받음(아직 등록 X).
export function stageZip(
  file: File,
  onProgress?: (loaded: number, total: number) => void
): Promise<StageResult> {
  const fd = new FormData();
  fd.append("file", file);
  return xhrUpload<StageResult>("/uploads/zip/stage", fd, onProgress);
}

// 4단계: 검증한 엑셀 + staging 매니페스트를 한 번에 커밋(상품 생성 + 이미지 매칭).
export function commitUpload(
  file: File,
  manifest: ImageManifestItem[],
  onProgress?: (loaded: number, total: number) => void
): Promise<CommitResult> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("images", JSON.stringify(manifest));
  return xhrUpload<CommitResult>("/uploads/commit", fd, onProgress);
}

export const listUnmatched = (job_id: string) =>
  api<ProductImage[]>(`/uploads/${job_id}/unmatched`, { auth: true });

export const matchImage = (job_id: string, image_id: string, source_p_number: string) =>
  api(`/uploads/${job_id}/match`, {
    method: "POST",
    body: JSON.stringify({ image_id, source_p_number }),
    auth: true,
  });

export const listJobs = () => api<{ jobs: Job[] }>("/uploads/jobs", { auth: true });

/* ── Storage (이미지 직접 업로드) ──────────────────────────────────────── */
export async function uploadProductImage(
  file: File,
  wholesalerId: string,
  key: string
): Promise<{ storage_path: string; publicUrl: string }> {
  // ⚠️ Supabase Storage 키는 ASCII 만 허용(한글/특수문자 → InvalidKey). 확장자도 ASCII 로 정리.
  const ext = (file.name.split(".").pop() || "jpg").replace(/[^a-zA-Z0-9]/g, "").toLowerCase() || "jpg";
  const storage_path = `${wholesalerId}/${key}.${ext}`;
  const { error } = await supabase.storage
    .from(PRODUCT_BUCKET)
    .upload(storage_path, file, { upsert: true, contentType: file.type });
  if (error) throw new Error(`이미지 업로드 실패: ${error.message}`);
  return { storage_path, publicUrl: publicImageUrl(storage_path) };
}

export function publicImageUrl(storagePath: string): string {
  return supabase.storage.from(PRODUCT_BUCKET).getPublicUrl(storagePath).data.publicUrl;
}

/** 상품 대표 이미지 URL 해석 — representative_image_url(완전URL) 우선, 없으면 첫 이미지 storage_path. */
export function productThumb(p: Product): string | null {
  if (p.representative_image_url) return p.representative_image_url;
  const img = p.images?.[0];
  return img ? publicImageUrl(img.storage_path) : null;
}

/* ── 엑셀 다운로드(인증 헤더 필요 → blob) ─────────────────────────────── */
export async function downloadProductsXlsx(params: {
  category?: string;
  search?: string;
  status?: string;
} = {}) {
  const q = new URLSearchParams();
  if (params.category) q.set("category", params.category);
  if (params.search) q.set("search", params.search);
  if (params.status) q.set("status", params.status);
  const { data } = await supabase.auth.getSession();
  const res = await fetch(`${API_BASE}/products/export.xlsx?${q.toString()}`, {
    headers: data.session ? { Authorization: `Bearer ${data.session.access_token}` } : {},
  });
  if (!res.ok) throw new Error("엑셀 다운로드 실패");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "ezmerce-products.xlsx";
  a.click();
  URL.revokeObjectURL(url);
}

/* ── 색상×사이즈 → SKU 매트릭스 (단일 등록 모달) ──────────────────────── */
export function splitCsv(s: string): string[] {
  return s
    .split(/[,/]/)
    .map((x) => x.trim())
    .filter(Boolean);
}

export function buildSkuMatrix(
  colorsStr: string,
  sizesStr: string,
  wholesale: number,
  retail: number | null,
  stock: number
): Omit<Sku, "id">[] {
  const colors = splitCsv(colorsStr);
  const sizes = splitCsv(sizesStr);
  const cs = colors.length ? colors : ["기본"];
  const ss = sizes.length ? sizes : ["FREE"];
  const out: Omit<Sku, "id">[] = [];
  for (const c of cs)
    for (const s of ss)
      out.push({ color: c, size: s, wholesale_price: wholesale, retail_price: retail, stock });
  return out;
}

/* ── 표시 헬퍼 ──────────────────────────────────────────────────────────── */
export const won = (n: number | null | undefined) =>
  n == null ? "—" : `₩${n.toLocaleString("ko-KR")}`;

export function aggregateColors(p: Product): string {
  return [...new Set(p.skus.map((s) => s.color))].join(", ") || "—";
}
export function aggregateSizes(p: Product): string {
  return [...new Set(p.skus.map((s) => s.size))].join(", ") || "—";
}
/** 대표 도매가 = SKU 중 최저 도매가(목록 단가 표시용). */
export function repWholesale(p: Product): number | null {
  const prices = p.skus.map((s) => s.wholesale_price).filter((n) => n != null);
  return prices.length ? Math.min(...prices) : null;
}
export function totalStock(p: Product): number {
  return p.skus.reduce((a, s) => a + (s.stock ?? 0), 0);
}
