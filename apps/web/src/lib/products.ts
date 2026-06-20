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
  manager_id: string | null; // 연계된 도매관리자(테넌트) — 멀티테넌트 스코프 키
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
// 공개 이미지 URL prefix(GCS). ⚠️ 백엔드 gcs_public_base_url 과 동일해야 함(불일치 시 엑셀 역파서 누락).
const GCS_PUBLIC_BASE = (
  process.env.NEXT_PUBLIC_GCS_PUBLIC_BASE ?? "https://storage.googleapis.com/ezmerce-product-images"
).replace(/\/+$/, "");
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
  agency_id: string | null; // 에이전시 소속 셀러 → 소속 에이전시(1차 미운영이라 보통 null)
  agency_name: string | null; // 서버가 agency_id→name 으로 보강(어드민 유형 표시용)
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

/* ── 고객관리 (소매↔도매 매칭 취소 + 가격노출) ───────────────────────────── */
// 모델: 테넌트 안 모든 소매↔도매 '기본 연결', 관리자가 특정 쌍을 '취소'. 백엔드 /customers 셰이핑과 1:1.
export type Customer = Account & {
  tier: string | null; // 1차 화면 제외(2차 자동등급). 잠자는 필드
  excluded_wholesaler_ids?: string[]; // admin 뷰: 이 소매가 '거래 취소'된 도매 id (없으면 전부 연결)
};

// 도매업체 목록(도매관리자 전용 — 도매 탭 + 매칭 취소 대상)
export type ManagedWholesaler = {
  id: string;
  name: string;
  biz_number: string | null;
  created_at: string | null;
  connected_count: number; // 연결된 소매 수(= 테넌트 전체 − 취소)
};

export const PRICE_VIS_LABEL: Record<string, string> = {
  wholesale: "도매가",
  retail: "판매가",
  none: "미노출",
};

export const listCustomers = () => api<Customer[]>("/customers", { auth: true });
export const listManagedWholesalers = () =>
  api<ManagedWholesaler[]>("/customers/wholesalers", { auth: true });
// 매칭 취소(연결 끊기) / 복원(다시 연결) — 도매관리자 전용
export const disconnectCustomer = (uid: string, wholesaler_id: string) =>
  api(`/customers/${uid}/disconnect`, { method: "POST", body: JSON.stringify({ wholesaler_id }), auth: true });
export const reconnectCustomer = (uid: string, wholesaler_id: string) =>
  api(`/customers/${uid}/reconnect`, { method: "POST", body: JSON.stringify({ wholesaler_id }), auth: true });
export const setCustomerPriceVisibility = (uid: string, price_visibility: string) =>
  api(`/customers/${uid}/price-visibility`, {
    method: "POST",
    body: JSON.stringify({ price_visibility }),
    auth: true,
  });

/* ── 도매관리자(테넌트) — 소속 도매 합산 상품관리 (FR-5) ────────────────── */
export type AdminSku = {
  color: string;
  size: string;
  stock: number;
  wholesale_price: number; // admin 은 도매가+판매가 둘 다 노출
  retail_price: number;
};

export type AdminProduct = {
  id: string;
  platform_code: string;
  source_p_number: string;
  item_name: string;
  category: string | null;
  fabric_composition: string | null; // 상세 모달용(아래 필드들)
  origin: string | null;
  lead_time_days: string | null;
  description: string | null;
  status: string;
  is_sold_out: boolean;
  representative_image_url: string | null;
  created_at: string | null;
  wholesaler_id: string;
  wholesaler_name: string | null; // 행마다 어느 도매 것인지(도매 출처)
  skus: AdminSku[];
  images: ProductImage[]; // 상세 모달 갤러리 — Product 와 구조 호환(상세 모달 재사용)
};

export type AdminProductList = {
  items: AdminProduct[];
  total: number;
  limit: number;
  offset: number;
};

export function listAdminProducts(
  params: { limit?: number; offset?: number; search?: string; status?: string } = {}
): Promise<AdminProductList> {
  const q = new URLSearchParams();
  if (params.limit != null) q.set("limit", String(params.limit));
  if (params.offset != null) q.set("offset", String(params.offset));
  if (params.search) q.set("search", params.search);
  if (params.status) q.set("status", params.status);
  const qs = q.toString();
  return api<AdminProductList>(`/admin/products${qs ? `?${qs}` : ""}`, { auth: true });
}

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

/* ── Storage (이미지 직접 업로드) — GCS signed PUT URL ──────────────────── */
export async function uploadProductImage(
  file: File,
  _wholesalerId: string, // 서버가 토큰에서 도매 스코프({wid}/)를 강제 — 인자는 호출부 호환 유지용(미사용)
  key: string
): Promise<{ storage_path: string; publicUrl: string }> {
  // object name 은 ASCII 로(GCS 안전). 확장자 정리.
  const ext = (file.name.split(".").pop() || "jpg").replace(/[^a-zA-Z0-9]/g, "").toLowerCase() || "jpg";
  const ctype = file.type || "application/octet-stream";
  // 1) 백엔드에서 V4 signed PUT URL 발급(경로 prefix={wid}/ 는 서버가 토큰으로 강제 → IDOR 차단).
  const signed = await api<{ upload_url: string; storage_path: string; public_url: string; content_type: string }>(
    "/uploads/sign",
    { method: "POST", body: JSON.stringify({ object_key: `${key}.${ext}`, content_type: ctype }), auth: true }
  );
  // 2) 브라우저가 GCS 로 직접 PUT(서명한 content_type 과 동일 헤더 필수 — CORS 는 버킷에 설정됨).
  const res = await fetch(signed.upload_url, {
    method: "PUT",
    headers: { "Content-Type": signed.content_type },
    body: file,
  });
  if (!res.ok) throw new Error(`이미지 업로드 실패 (${res.status})`);
  return { storage_path: signed.storage_path, publicUrl: signed.public_url };
}

/** 공개 이미지 URL — GCS 공개 버킷. 백엔드 public_image_url 과 동일 형식(`{GCS_PUBLIC_BASE}/{path}`). */
export function publicImageUrl(storagePath: string): string {
  return `${GCS_PUBLIC_BASE}/${storagePath.replace(/^\/+/, "")}`;
}

/** 상품 대표 이미지 URL 해석 — representative_image_url(완전URL) 우선, 없으면 첫 이미지 storage_path. */
export function productThumb(p: Product): string | null {
  if (p.representative_image_url) return p.representative_image_url;
  const img = p.images?.[0];
  return img ? publicImageUrl(img.storage_path) : null;
}

/* ── 엑셀 다운로드(인증 헤더 필요 → blob) ─────────────────────────────── */
/** 다운로드 파일명용 타임스탬프 — YYYY_MM_DD_HH-mm-ss (로컬 시간; ':' 는 파일명 금지문자라 시간은 '-'). */
function xlsxStamp(): string {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}_${p(d.getMonth() + 1)}_${p(d.getDate())}_${p(d.getHours())}-${p(d.getMinutes())}-${p(d.getSeconds())}`;
}

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
  a.download = `상품목록_${xlsxStamp()}.xlsx`;
  a.click();
  URL.revokeObjectURL(url);
}

/** 도매관리자(테넌트) 합산 엑셀 추출 — 소속 도매 전체 상품. (인증 헤더 필요 → blob) */
export async function downloadAdminProductsXlsx(params: { search?: string; status?: string } = {}) {
  const q = new URLSearchParams();
  if (params.search) q.set("search", params.search);
  if (params.status) q.set("status", params.status);
  const { data } = await supabase.auth.getSession();
  const res = await fetch(`${API_BASE}/admin/products/export.xlsx?${q.toString()}`, {
    headers: data.session ? { Authorization: `Bearer ${data.session.access_token}` } : {},
  });
  if (!res.ok) throw new Error("엑셀 추출 실패");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `도매상품목록_${xlsxStamp()}.xlsx`;
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
/** 목록 표시용: 앞 max개 색상 + "외 N색". 전체 목록은 호출부에서 title 툴팁으로 노출. */
export function colorSummary(p: Product, max = 4): { text: string; full: string; more: number } {
  const colors = [...new Set(p.skus.map((s) => s.color))].filter(Boolean);
  const full = colors.join(", ") || "—";
  if (colors.length <= max) return { text: full, full, more: 0 };
  const more = colors.length - max;
  return { text: `${colors.slice(0, max).join(", ")} 외 ${more}색`, full, more };
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

/**
 * 음수 재고 규약: `stock < 0` = **품절이면서 |stock| 만큼 예약(주문 대기)**.
 * 예) stock=-4 → 가용 0 · 예약 4 / stock=5 → 가용 5 · 예약 0 / stock=0 → 품절·예약 0.
 */
export const skuReserved = (s: Pick<Sku, "stock">): number => ((s.stock ?? 0) < 0 ? -(s.stock ?? 0) : 0);
export const skuAvailable = (s: Pick<Sku, "stock">): number => ((s.stock ?? 0) > 0 ? (s.stock ?? 0) : 0);
/** 품절 판정 = 명시 품절 플래그 OR 총재고 0. (재고 없어도 예약주문은 받으므로 목록에서 '제외'하진 않고 '품절만 보기' 필터·뱃지에만 사용) */
export function isSoldOut(p: Product): boolean {
  return p.is_sold_out || totalStock(p) <= 0;
}
