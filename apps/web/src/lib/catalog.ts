import { api, API_BASE } from "./api";
import { supabase } from "./supabase";

/* ── 타입 (백엔드 shape_catalog_item 셰이핑과 1:1) ─────────────────────────
   가격은 서버가 역할별로 셰이핑한다(가격 노출 규칙 §). 셀러 응답 = 단일 `price`
   (노출 허용 시 number, 미노출 시 null). 관리뷰(admin/도매 본인)면 wholesale/retail
   둘 다 오지만, 쇼룸은 셀러 전용 게이트라 사실상 `price` 만 온다. */
export type CatalogSku = {
  color: string;
  size: string;
  stock: number | null;
  price?: number | null;
  wholesale_price?: number; // 관리뷰 전용 — 셀러 화면엔 안 옴
  retail_price?: number | null; // 관리뷰 전용
};

export type CatalogItem = {
  platform_code: string;
  item_name: string;
  source_p_number: string | null; // 쇼룸/엑셀 "품번"
  fabric_composition: string | null; // 혼용률
  representative_image_url: string | null;
  created_at: string | null; // 커서 페이지네이션용
  skus: CatalogSku[];
};

export type CatalogList = { items: CatalogItem[] };

/* ── 조회 ───────────────────────────────────────────────────────────────── */
export function getCatalog(
  params: { limit?: number; cursor?: string } = {}
): Promise<CatalogList> {
  const q = new URLSearchParams();
  if (params.limit != null) q.set("limit", String(params.limit));
  if (params.cursor) q.set("cursor", params.cursor);
  const qs = q.toString();
  return api<CatalogList>(`/catalog${qs ? `?${qs}` : ""}`, { auth: true });
}

/** 전체 카탈로그를 커서로 끝까지 모은다(백엔드 limit 캡 le=100 → created_at 커서 루프). */
export async function getAllCatalog(): Promise<CatalogItem[]> {
  const LIMIT = 100;
  const acc: CatalogItem[] = [];
  let cursor: string | undefined;
  for (let i = 0; i < 50; i++) {
    // 안전 상한 ≈ 5000 상품
    const res = await getCatalog({ limit: LIMIT, cursor });
    acc.push(...res.items);
    if (res.items.length < LIMIT) break;
    cursor = res.items[res.items.length - 1].created_at ?? undefined;
    if (!cursor) break; // created_at 없으면 더 못 넘김(중복 방지)
  }
  return acc;
}

/* ── 쇼룸 카드 모델 — (상품 × 색상) 단위, 사이즈는 카드 안에 재고 표로 ──────
   기획 확정(2026-06-06): 카드 1장 = (상품, 색상). 사이즈는 카드 내부에 `사이즈→재고` 행.
   노출 필드 = 품번 · 이미지 · 색상 · 재고(사이즈별) · 도매가.
   (도매 상품관리=상품1행, SKU 단위 카드 X.) */
// 예약(committed)은 별도 데이터가 아니라 stock 음수분으로 표현된다(현장 규칙):
//   stock = -1 → 가용(재고 표시) 0 / 예약 1.  =>  available = max(0, stock), committed = max(0, -stock)
export type ShowroomSize = { size: string; available: number; committed: number };
export type ShowroomCard = {
  key: string;
  pnum: string; // 품번 (source_p_number, 없으면 platform_code)
  item_name: string; // 상품명(보조 — 기획 5필드엔 없으나 가독성용)
  image: string | null;
  color: string;
  fabric: string | null; // 혼용률(상품 공통)
  price: number | null; // 대표 도매가(미노출=null → "가격 문의")
  sizes: ShowroomSize[]; // 사이즈별 재고(정렬됨)
  soldOut: boolean; // 모든 사이즈 재고 0
};

// 사이즈 표준 정렬(문자 사이즈 우선순위 → 숫자 사이즈 → 사전순).
const SIZE_ORDER = ["XXS", "XS", "S", "M", "L", "XL", "XXL", "XXXL", "FREE", "F", "OS"];
function sizeRank(s: string): number {
  const i = SIZE_ORDER.indexOf(s.trim().toUpperCase());
  return i === -1 ? 900 : i;
}
function bySize(a: ShowroomSize, b: ShowroomSize): number {
  const ra = sizeRank(a.size);
  const rb = sizeRank(b.size);
  if (ra !== rb) return ra - rb;
  const na = parseInt(a.size, 10);
  const nb = parseInt(b.size, 10);
  if (!Number.isNaN(na) && !Number.isNaN(nb)) return na - nb;
  return a.size.localeCompare(b.size);
}

export function toShowroomCards(items: CatalogItem[]): ShowroomCard[] {
  const cards: ShowroomCard[] = [];
  // 최신 등록순(created_at desc) — ISO 문자열 사전순=시간순(동일 포맷). null/누락은 뒤로.
  const ordered = [...items].sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""));
  for (const it of ordered) {
    // (색상)별 그룹핑 — 같은 색상 SKU 들을 한 카드로, 사이즈는 행으로.
    const byColor = new Map<string, CatalogSku[]>();
    for (const s of it.skus) {
      const arr = byColor.get(s.color) ?? [];
      arr.push(s);
      byColor.set(s.color, arr);
    }
    for (const [color, skus] of byColor) {
      const sizes = skus
        .map((s) => {
          const raw = s.stock ?? 0; // 음수 = 예약분(재고 -1 → 가용 0 / 예약 1)
          return { size: s.size, available: Math.max(0, raw), committed: Math.max(0, -raw) };
        })
        .sort(bySize);
      // 대표 도매가 = 그룹 내 노출가 중 최저(보통 사이즈별 동일). 전부 미노출이면 null.
      const prices = skus
        .map((s) => s.price ?? s.wholesale_price)
        .filter((n): n is number => n != null);
      cards.push({
        key: `${it.platform_code}-${color}`,
        pnum: it.source_p_number ?? it.platform_code,
        item_name: it.item_name,
        image: it.representative_image_url,
        color,
        fabric: it.fabric_composition,
        price: prices.length ? Math.min(...prices) : null,
        sizes,
        soldOut: sizes.every((x) => x.available <= 0), // 모든 사이즈 가용 0 → 품절
      });
    }
  }
  return cards;
}

/* ── 가격 표시: 미노출(null) → "가격 문의" (0원/빈값 금지, 가격 노출 규칙 §) ── */
export const priceLabel = (n: number | null | undefined) =>
  n == null ? "가격 문의" : `₩${n.toLocaleString("ko-KR")}`;

/* ── 엑셀 내보내기(셀러 카탈로그 — 인증 헤더 필요 → blob) ────────────────── */
export async function downloadCatalogXlsx() {
  const { data } = await supabase.auth.getSession();
  const res = await fetch(`${API_BASE}/catalog/export.xlsx`, {
    headers: data.session ? { Authorization: `Bearer ${data.session.access_token}` } : {},
  });
  if (!res.ok) throw new Error("엑셀 다운로드 실패");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "ezmerce-catalog.xlsx";
  a.click();
  URL.revokeObjectURL(url);
}
