# HANDOFF — 프론트엔드 디자인 시스템 구축 (apps/web)

> 다음 세션은 이 파일 경로로 시작: `HANDOFF-frontend-design-system.md`
> 작성: 2026-06-04 / 브랜치: `v2-dev` / 백엔드 상태·API는 [HANDOFF.md](HANDOFF.md), 할 일 전체는 [TODO.md](TODO.md) 참고.
>
> ✅ **디자인 추출 완료(2026-06-04)** — 시안 PDF에서 디자인 시스템·이미지 추출됨. 산출물:
> - 디자인 시스템: [`apps/web/design/DESIGN-SYSTEM.md`](apps/web/design/DESIGN-SYSTEM.md) (색/타이포/컴포넌트/셸)
> - 토큰(바로 사용): [`apps/web/src/styles/ezmerce-tokens.css`](apps/web/src/styles/ezmerce-tokens.css) (Tailwind v4 `@theme`)
> - 36화면 인벤토리: [`apps/web/design/SCREEN-INVENTORY.md`](apps/web/design/SCREEN-INVENTORY.md)
> - 이미지 자산: `apps/web/public/{images,brand}/` + [`apps/web/design/ASSET-MANIFEST.md`](apps/web/design/ASSET-MANIFEST.md)

## 🎯 Goal
**apps/web 의 프론트엔드 디자인 시스템을 구축**한다 — 디자인 토큰(컬러/타이포/스페이싱/라운드/섀도) + 한글 폰트 + 기본 컴포넌트 라이브러리 + 역할별 레이아웃 토대. 이후 PoC/MVP 화면(상품등록·업로드·카탈로그·QR카드·관리자)을 이 시스템 위에 얹는다.
대상 제품: **ezmerce** — 폐쇄형 B2B 도매 카탈로그(고객 LALAS). UI 언어 = **한국어**. 역할 = 도매업체 / 소매셀러(라이브셀러) / 에이전시 / admin.

## 🧱 현재 프론트 스택 (확인됨)
- **모노레포**: `apps/web`(Next.js 웹), `apps/mobile`(React Native, 별개). **디자인 시스템 작업 = `apps/web`**.
- `apps/web`: **Next.js 16.2.6 (App Router)** · **React 19.2.4** · **Tailwind CSS v4**(`@tailwindcss/postcss`) · **zustand 5**(상태) · TypeScript 5 · ESLint 9.
- **UI 컴포넌트 라이브러리 없음**(아직). 디자인 토큰 최소(Geist 기본 + 라이트/다크 `prefers-color-scheme`).
- `apps/web/CLAUDE.md` → `@AGENTS.md` import (프론트 규칙은 `apps/web/AGENTS.md` 확인).

### 이미 있는 스캐폴드 (apps/web/src)
- 라우트(App Router): `/`(page), `/wholesaler/upload`, `/retailer/catalog`, `/retailer/live`
- `src/components/RoleToggle.tsx`, `src/store/useRoleStore.ts`(zustand 역할 토글)
- `src/app/globals.css`: `@import "tailwindcss"` + `@theme inline` + `--background/--foreground`, `--font-geist-*`. body 폰트는 Arial 폴백(= **한글 폰트 미적용**).
- 실행: `cd apps/web && npm run dev` (package-lock 기준 npm) → **localhost:3555**. 백엔드 = **localhost:8444** (`NEXT_PUBLIC_API_BASE_URL=http://localhost:8444`).

> ⚠️ **최상위 `web/` 디렉토리는 떠돌이 빌드 산출물**(.next/node_modules/tsbuildinfo만, 소스 없음). 이미 .gitignore 처리됨. 헷갈리지 말 것 — 실제 프론트는 **apps/web**. (정리하려면 `rm -rf web/` 해도 무방)

## 🎨 디자인 소스 — ✅ PDF 추출로 해소됨
- 시안 PDF(`~/Downloads/ezmerce.pdf`, 36p)를 받아 **디자인 시스템·이미지 전량 추출 완료**(Figma 접근 불필요).
  - 색상: PDF 벡터 fill에서 정확 추출(rgb%→hex) → `ezmerce-tokens.css`.
  - 폰트: PDF가 Type3(이름없음) 임베드라 자동추출 불가 → 시각 식별 + 웹폰트 대응안(Pretendard + Playfair Display) — DESIGN-SYSTEM.md §2.
  - 이미지: 348개→중복제거 192→큐레이션 22개(`public/images`·`public/brand`).
- (참고) 원본 Figma: https://www.figma.com/design/qptdNAvYvLVwNdbedQtile/ezmerce — 추후 직접 동기화가 필요하면 MCP 계정(`jslee@goldenplanet.co.kr`, View/Starter) 권한·재인증 해결 필요. 현재 작업엔 불필요.

## 🔌 연동할 백엔드 API (이미 완성·라이브 검증됨)
FastAPI, **JWT(Supabase JWKS) 인증**, 가격은 서버에서 역할별 셰이핑. 라우트 16개:
- **인증/계정**: `POST /auth/register`(가입,pending) · `GET /admin/accounts` · `POST /admin/accounts/{uid}/approve|reject|price-visibility`
- **상품**: `POST /products`(단건) · `PATCH /products/{pid}` · `DELETE /products/{pid}`(soft)
- **업로드**: `POST /uploads/excel`(multipart) · `POST /uploads/images`(매니페스트) · `GET /uploads/{job}/unmatched` · `POST /uploads/{job}/match`
- **카탈로그/출력**: `GET /catalog`(페이지네이션·역할별 가격) · `GET /catalog/export.xlsx`(QR열 포함)
- **공개**: `GET /qr/{platform_code}.png` · `GET /p/{platform_code}`(가격 미포함 카드 데이터)
- 인증: 프론트가 Supabase Auth 로그인 → JWT 를 `Authorization: Bearer` 로 전달. (Supabase 클라이언트 = `@supabase/ssr` 권장)
- 이미지 업로드 모델 = **프론트가 `product-images` Storage 버킷에 직접 업로드** 후 경로 매니페스트를 `/uploads/images` 로 전달. (버킷·RLS 아직 미생성 — TODO.md)

## 🧩 화면 목록 (디자인 시스템이 커버해야 할 것 — TODO.md PoC/MVP)
- **PoC(~6/13)**: 로그인/가입 · 상품 등록(단건 폼 + 표준 엑셀 업로드) · 이미지 대량 업로드+매칭(미매칭 목록/수작업 매칭) · 상품 관리(목록/수정/삭제/보관) · 엑셀 다운로드 버튼 · **QR 카드 페이지(인스타그램 비율 모바일 카드, 공개·가격 미노출)**
- **MVP**: 폐쇄형 **카탈로그 뷰**(승인 셀러/에이전시, 그리드, 역할별 가격) · 관리자 계정 승인 UI
- 참고: 카탈로그 "뷰 페이지"는 MVP 단계(PoC 제외). 백엔드 `GET /catalog`는 선구현됨.

## 🤔 다음 세션에서 정할 결정
- **컴포넌트 라이브러리**: shadcn/ui(Tailwind v4 기반, 추천 — 스킬 `vercel:shadcn` 있음) vs 직접 빌드 vs 기타(Park UI 등).
- **디자인 토큰 출처**: Figma 추출(접근 해결 시) vs 임시 정의 후 동기화.
- **한글 폰트**: Pretendard(추천) 등 — 현재 Geist는 라틴 위주, body가 Arial 폴백.
- **다크모드**: 지원 여부/방식(현재 prefers-color-scheme만).
- **데이터 패칭/폼/인증**: TanStack Query or SWR · react-hook-form(+zod) · `@supabase/ssr`.
- **반응형 기준**: 데스크톱(관리/업로드) vs 모바일(QR 카드는 인스타 비율 9:16 계열).

## 🔜 Next Steps (디자인 시스템 구축 순서 제안)
1. ~~Figma 접근 해결 → 토큰 추출~~ **✅ 완료** (PDF에서 토큰/이미지 추출 → `ezmerce-tokens.css`, `DESIGN-SYSTEM.md`).
2. **한글 폰트 설치·로딩**(Pretendard + Playfair Display) → `globals.css` body 폰트 교체(현재 Arial 폴백). DESIGN-SYSTEM §2.2.
3. **`globals.css`에 `@import "../styles/ezmerce-tokens.css";` 추가** → `bg-primary`/`text-muted`/`rounded-lg` 등 유틸리티 활성.
4. **컴포넌트 라이브러리 설치**(shadcn/ui 추천, 스킬 `vercel:shadcn`) → 테마를 본 토큰에 매핑.
5. **기본 컴포넌트** 구축: Button/Input/Select/Textarea/Checkbox/Card/Table/Badge(상태색 §1.4)/Tabs/Toast/Dialog/Popover/FileDropzone + 셸 A~D(인증스플릿/다크어드민/스토어프론트/에이전시).
6. (선택) `/design` 미리보기 페이지로 컴포넌트 카탈로그.
7. 기존 스캐폴드 라우트를 디자인 시스템으로 재정비 → PoC 화면(로그인/가입·상품등록·업로드·QR카드) 구현.

## 🛠 유용한 스킬/도구
- `vercel:shadcn`(shadcn 설치/구성), `frontend-design`(고품질 UI), `vercel:nextjs`(App Router), `supabase`(Auth 클라이언트/SSR), `figma-generate-design`·`figma-use`(MCP, 접근 해결 후).
- 실행: `cd apps/web && npm install && npm run dev`.

## ✅ / ❌ 메모
- **됨**: 백엔드 API 16개 완성·라이브 검증(스모크 24/0), 스택 확정(Next16/React19/Tailwind4/zustand), 역할 라우트 스캐폴드 존재.
- **안 됨/막힘**: Figma MCP 접근(계정 권한 jslee/View/Starter) — 다음 세션 시작 전 해결 필요. 최상위 `web/` 떠돌이 디렉토리(무시/삭제).
