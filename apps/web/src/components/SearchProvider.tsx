"use client";

import { createContext, useContext, useState, type ReactNode } from "react";

/** 상단바 검색어를 셸(Shell)과 목록 페이지(상품 관리 등)가 공유하기 위한 컨텍스트.
 *  URL 파라미터(useSearchParams) 대신 컨텍스트 사용 — 정적 export 시 Suspense 경계 불필요. */
type SearchCtx = { query: string; setQuery: (v: string) => void };

const Ctx = createContext<SearchCtx | null>(null);

export function SearchProvider({ children }: { children: ReactNode }) {
  const [query, setQuery] = useState("");
  return <Ctx.Provider value={{ query, setQuery }}>{children}</Ctx.Provider>;
}

/** 프로바이더 밖에서 호출돼도 크래시 없이 no-op 기본값 반환. */
export function useSearch(): SearchCtx {
  return useContext(Ctx) ?? { query: "", setQuery: () => {} };
}
