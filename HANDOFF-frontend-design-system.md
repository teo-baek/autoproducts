# HANDOFF — 프론트엔드 디자인 시스템 구축 (apps/web)

> 다음 세션은 이 파일 경로로 시작: `HANDOFF-frontend-design-system.md`
> 작성: 2026-06-04 / 브랜치: `v2-dev` / 백엔드 상태·API는 [HANDOFF.md](HANDOFF.md), 할 일 전체는 [TODO.md](TODO.md) 참고.

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
- 실행: `cd apps/web && npm run dev` (package-lock 기준 npm).

> ⚠️ **최상위 `web/` 디렉토리는 떠돌이 빌드 산출물**(.next/node_modules/tsbuildinfo만, 소스 없음). 이미 .gitignore 처리됨. 헷갈리지 말 것 — 실제 프론트는 **apps/web**. (정리하려면 `rm -rf web/` 해도 무방)

## 🎨 디자인 소스 (Figma) — ⚠️ 접근 막힘
- 파일: **https://www.figma.com/design/qptdNAvYvLVwNdbedQtile/ezmerce?node-id=0-1**
- Figma MCP 연동돼 있으나 **접근 불가**. 원인: MCP 인증 계정 = **`jslee@goldenplanet.co.kr`**(팀 "이진섭의 팀", **View 시트 / Starter**)가 이 파일 권한 없음. + View/Starter는 MCP 읽기 **월 6회** 제한.
- **해결(다음 세션 시작 전 택1)**:
  1. Figma에서 파일을 **`jslee@goldenplanet.co.kr` 에 공유**(+가능하면 Dev/Full 시트로).
  2. **접근 권한 있는 계정으로 MCP 재인증**(`/mcp` → Figma).
  3. **PNG/PDF export 해서 채팅에 붙이기**(가장 빠름, 권한 불필요). `File → Export frames to PDF` 추천.
- 접근되면 도구: `mcp__claude_ai_Figma__get_metadata`(구조) → `get_screenshot`(시각) → `get_design_context`(코드/토큰). 스킬 `/figma-generate-design`, `/figma-use`(use_figma 전 필수).

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
1. **Figma 접근 해결**(공유/재인증/Export) → 토큰 추출(color/type/space/radius/shadow) + 핵심 화면 시안 확보.
2. **컴포넌트 라이브러리 결정·설치**(shadcn/ui 추천) + **Tailwind v4 `@theme` 토큰 매핑**(globals.css 정비).
3. **한글 폰트 적용**(Pretendard 등) + 타이포 스케일 정의.
4. **기본 컴포넌트** 구축: Button/Input/Select/Textarea/Checkbox/Card/Table/Badge/Tabs/Toast/Dialog/FileDropzone + 역할별 레이아웃(셀러/도매/admin 셸).
5. (선택) `/design` 미리보기 페이지 또는 Storybook 으로 컴포넌트 카탈로그.
6. 기존 스캐폴드 라우트(role 토글/업로드/카탈로그/라이브)를 디자인 시스템으로 재정비 → 이후 화면 구현.

## 🛠 유용한 스킬/도구
- `vercel:shadcn`(shadcn 설치/구성), `frontend-design`(고품질 UI), `vercel:nextjs`(App Router), `supabase`(Auth 클라이언트/SSR), `figma-generate-design`·`figma-use`(MCP, 접근 해결 후).
- 실행: `cd apps/web && npm install && npm run dev`.

## ✅ / ❌ 메모
- **됨**: 백엔드 API 16개 완성·라이브 검증(스모크 24/0), 스택 확정(Next16/React19/Tailwind4/zustand), 역할 라우트 스캐폴드 존재.
- **안 됨/막힘**: Figma MCP 접근(계정 권한 jslee/View/Starter) — 다음 세션 시작 전 해결 필요. 최상위 `web/` 떠돌이 디렉토리(무시/삭제).
