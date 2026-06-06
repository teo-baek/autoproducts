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
export type IngestResult = {
  job_id: string;
  created: unknown[];
  errors: { row?: number; reason: string; source_p_number?: string }[];
};

export function uploadExcel(file: File): Promise<IngestResult> {
  const fd = new FormData();
  fd.append("file", file);
  return api<IngestResult>("/uploads/excel", { method: "POST", body: fd, auth: true });
}

export const attachImages = (
  job_id: string,
  images: { original_filename: string; storage_path: string }[]
) =>
  api<{ matched: string[]; unmatched: string[]; images: unknown[] }>("/uploads/images", {
    method: "POST",
    body: JSON.stringify({ job_id, images }),
    auth: true,
  });

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
  const ext = file.name.split(".").pop() ?? "jpg";
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
