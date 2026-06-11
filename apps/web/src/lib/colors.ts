/* 한글/영문 색상명 → 컬러칩(스와치) hex. 쇼룸 카드 등 "표시 전용"이며 가격/데이터와 무관.
 * 미매핑이면 null 반환 → 호출부에서 점선 칩으로 폴백한다.
 * 매칭 순서: ① 정확 일치 → ② 키워드 포함(가장 긴 토큰 우선) → ③ 연/진 모디파이어로 명도 보정. */

const BASE: Record<string, string> = {
  // 무채색
  블랙: "#1f1f1f", 검정: "#1f1f1f", 먹: "#272727",
  화이트: "#ffffff", 흰색: "#ffffff", 아이보리: "#f3ecda", 아이: "#f3ecda", 크림: "#f5eede",
  그레이: "#9aa0a6", 회색: "#9aa0a6", 차콜: "#3a3f44", 챠콜: "#3a3f44", 멜란지: "#b9bdc3",
  // 레드 계열
  레드: "#d23b3b", 빨강: "#d23b3b", 와인: "#7b2233", 버건디: "#6e1b2e", 브릭: "#a4452f",
  코랄: "#f0856b", 살구: "#f6b48a",
  // 핑크
  핑크: "#f2a4be", 체리핑크: "#e6517c", 인디핑크: "#d4899a", 로즈: "#d76a86",
  // 오렌지/옐로
  오렌지: "#e8843c", 옐로우: "#f2c43d", 노랑: "#f2c43d", 머스타드: "#c79a2e", 겨자: "#c79a2e", 레몬: "#eede55",
  // 그린
  그린: "#3f8f5b", 카키: "#6b6f3a", 민트: "#8fd6c0", 올리브: "#6b7a3a", 라임: "#9fbf3a", 세이지: "#9caa86",
  // 블루
  블루: "#3b6fd2", 파랑: "#3b6fd2", 네이비: "#1f2d5a", 스카이: "#7fb6e6", 소라: "#9cc1e6", 코발트: "#274bb0", 데님: "#42648f",
  // 퍼플
  퍼플: "#7a4fb0", 보라: "#7a4fb0", 라벤더: "#c7bce8",
  // 브라운/베이지
  베이지: "#d8c4a0", 카멜: "#bb8a52", 브라운: "#6e4a2e", 탄: "#c9a06a", 모카: "#8a6a4a", 코코아: "#5a4030",
  // 영문
  black: "#1f1f1f", white: "#ffffff", ivory: "#f3ecda", cream: "#f5eede",
  gray: "#9aa0a6", grey: "#9aa0a6", charcoal: "#3a3f44",
  red: "#d23b3b", wine: "#7b2233", burgundy: "#6e1b2e", coral: "#f0856b",
  pink: "#f2a4be", rose: "#d76a86", orange: "#e8843c",
  yellow: "#f2c43d", mustard: "#c79a2e", lemon: "#eede55",
  green: "#3f8f5b", khaki: "#6b6f3a", mint: "#8fd6c0", olive: "#6b7a3a", lime: "#9fbf3a", sage: "#9caa86",
  blue: "#3b6fd2", navy: "#1f2d5a", sky: "#7fb6e6", cobalt: "#274bb0", denim: "#42648f",
  purple: "#7a4fb0", lavender: "#c7bce8",
  beige: "#d8c4a0", camel: "#bb8a52", brown: "#6e4a2e", tan: "#c9a06a", mocha: "#8a6a4a",

  // ── 추가 매핑 (2026-06-07) — 위 기존 항목은 그대로, 소매 색상명만 확장 ──
  // ⚠️ '연/진/딥' 이 든 이름은 정확키로 넣지 않는다(정확매칭에도 모디파이어가 또 먹어 명도가 꼬임).
  //    대신 기준색만 넣고 연청/진청/딥그린 등은 키워드폴백+모디파이어로 자동 처리. (예: '진청'→'청'+어둡게)
  // 한글 기초색 보강(초·주·분·남 등 순우리말/한자어)
  초록: "#3f8f5b", 주황: "#e8843c", 분홍: "#f2a4be", 남색: "#1f2d5a", 곤색: "#1f2d5a",
  연두: "#8fb53a", 하늘: "#8fc0e8", 자주: "#8a2846", 다홍: "#e23b2e", 청: "#4a6c93",
  // 그린/블루 계열
  청록: "#2f8a8a", 틸: "#2f8a8a", 인디고: "#3b3f7a", 에메랄드: "#2fae82",
  포레스트: "#2f6b3a", 터콰이즈: "#3ec6c0", 아쿠아: "#5cc9c9",
  // 레드/핑크/퍼플 계열
  마젠타: "#c2348b", 푸시아: "#cc3a91", 살몬: "#f08a72", 피치: "#f7b58e",
  라일락: "#c8a8d8", 자두: "#7a3b5a",
  // 뉴트럴/브라운 계열
  실버: "#c4c8cc", 골드: "#c9a24b", 오트밀: "#e3d8c2", 샌드: "#d8c39a", 토프: "#b8a894",
  그레이지: "#b3a99a", 스모키: "#6e7378", 초콜릿: "#4a3225", 캐러멜: "#bb8a52",
  // 영문 보강
  teal: "#2f8a8a", emerald: "#2fae82", forest: "#2f6b3a", turquoise: "#3ec6c0", aqua: "#5cc9c9",
  indigo: "#3b3f7a", magenta: "#c2348b", fuchsia: "#cc3a91", salmon: "#f08a72", peach: "#f7b58e",
  violet: "#7a4fb0", plum: "#7a3b5a", lilac: "#c8a8d8",
  silver: "#c4c8cc", gold: "#c9a24b", oatmeal: "#e3d8c2", sand: "#d8c39a", taupe: "#b8a894",
  chocolate: "#4a3225", caramel: "#bb8a52", maroon: "#6e1b2e", crimson: "#b81d3a", apricot: "#f6b48a",
  // 기초 한글색 보강(순우리말 명사·형용사형) — '~색/~빛' 붙은 형태는 폴백으로 이미 처리됨
  갈색: "#6e4a2e", 하양: "#ffffff", 하얀: "#ffffff",
  빨간: "#d23b3b", 노란: "#f2c43d", 파란: "#3b6fd2", 검은: "#1f1f1f", 까만: "#1f1f1f",
  // 실데이터(product_skus) 전수 감사로 발견한 변형/오타 표기 보강 (2026-06-07)
  엘로우: "#f2c43d", 메란지: "#b9bdc3", 오트: "#e3d8c2",
  // ※ '도트·스트라이프·수채화꽃' 등은 색이 아니라 패턴/프린트 → 단색 칩 대신 점선 폴백이 정확.
};

// 긴 토큰이 먼저 매칭되도록 미리 정렬(모듈 1회)
const KEYS_BY_LEN = Object.keys(BASE).sort((a, b) => b.length - a.length);

function clamp(n: number): number {
  return Math.max(0, Math.min(255, Math.round(n)));
}
/** amt>0 = 흰색쪽으로(밝게), amt<0 = 검정쪽으로(어둡게). |amt|=0~1 비율. */
function adjust(hex: string, amt: number): string {
  const m = hex.replace("#", "");
  const r = parseInt(m.slice(0, 2), 16);
  const g = parseInt(m.slice(2, 4), 16);
  const b = parseInt(m.slice(4, 6), 16);
  const target = amt < 0 ? 0 : 255;
  const p = Math.abs(amt);
  const mix = (c: number) => clamp(c + (target - c) * p);
  const hx = (c: number) => mix(c).toString(16).padStart(2, "0");
  return `#${hx(r)}${hx(g)}${hx(b)}`;
}
function isLight(hex: string): boolean {
  const m = hex.replace("#", "");
  const r = parseInt(m.slice(0, 2), 16);
  const g = parseInt(m.slice(2, 4), 16);
  const b = parseInt(m.slice(4, 6), 16);
  return 0.299 * r + 0.587 * g + 0.114 * b > 200; // 밝으면 흰 배경서 안 보여 테두리 필요
}

export type Swatch = { hex: string; light: boolean };

/** 색상명 → 스와치. 매핑 불가 시 null. */
export function colorSwatch(name: string | null | undefined): Swatch | null {
  const raw = (name ?? "").trim();
  if (!raw) return null;
  const lower = raw.toLowerCase();
  let hex = BASE[raw] ?? BASE[lower];
  if (!hex) {
    const hit = KEYS_BY_LEN.find((k) => raw.includes(k) || lower.includes(k));
    if (hit) hex = BASE[hit];
  }
  if (!hex) return null;
  if (/연|라이트|light|페일|pale/.test(lower)) hex = adjust(hex, 0.32);
  else if (/진|딥|deep|dark|다크/.test(lower)) hex = adjust(hex, -0.28);
  return { hex, light: isLight(hex) };
}
