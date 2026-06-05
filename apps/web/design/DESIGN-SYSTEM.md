# ezmerce 디자인 시스템 (시안 추출본)

> 출처: `ezmerce.pdf` (36p 디자인 시안, 2026-06-04 추출) · 대상: `apps/web`
> 같이 보기: [SCREEN-INVENTORY.md](SCREEN-INVENTORY.md) (36화면 상세) · [ASSET-MANIFEST.md](ASSET-MANIFEST.md) (이미지 자산) · 토큰: [`src/styles/ezmerce-tokens.css`](../src/styles/ezmerce-tokens.css)
>
> ⚠️ **이 문서는 "추출/참조"용이다.** 페이지·컴포넌트는 아직 구현하지 않았다. 추후 화면 구현 시 여기 토큰/규칙을 근거로 만든다.

---

## 0. 미감 방향 (Aesthetic Direction)
**에디토리얼 럭셔리 미니멀** — 패션 부티크 감성의 B2B 도매 콘솔.
- 따뜻한 톤(누드/베이지) **사진** + 쿨한 **딥네이비·그레이** UI 크롬의 대비.
- 세리프 이탤릭 로고타입(`ezmerce`) + 헤비 그로테스크 헤딩 + 한글 산세리프 본문.
- 절제된 그림자, 8px 라운드, 넉넉한 여백. 화려함이 아니라 **정밀함**으로 고급스러움.
- 스토어프론트(셀러향)는 **흑백 에디토리얼**, 어드민은 **컬러 + 다크 사이드바**로 톤을 분리.

---

## 1. 색상 (Color)
PDF 벡터 fill에서 정확 추출(rgb% → hex). 전부 [`ezmerce-tokens.css`](../src/styles/ezmerce-tokens.css)에 토큰화됨.

### 1.1 브랜드 / 잉크 (딥네이비 스케일)
| 토큰 | HEX | 용도 |
|---|---|---|
| `--color-ink` (primary) | `#041627` | 주요 버튼·CTA·세그먼트 활성·브랜드 |
| `--color-ink-strong` | `#0F172A` | 다크 셸(어드민 사이드바) 배경 |
| `--color-ink-800` | `#1A2B3C` | 네이비-800, 차트1 |
| `--color-ink-700` | `#38485A` | 보조 다크 surface |
| `--color-ink-600` | `#545F72` | 보조 텍스트(슬레이트) |

### 1.2 뉴트럴 (쿨그레이, 살짝 블루틴트)
| 토큰 | HEX | 용도 |
|---|---|---|
| `--color-canvas` | `#F7F9FB` | 페이지 배경 |
| `--color-surface` | `#FFFFFF` | 카드/패널 |
| `--color-surface-muted` | `#F2F4F6` | 보조표면·비활성 탭 |
| `--color-subtle` | `#ECEEF0` | 인풋 배경·subtle fill |
| `--color-divider` | `#E0E3E5` | 구분선 |
| `--color-border` | `#C4C6CD` | 기본 보더 |
| `--color-border-strong` | `#94A3B8` | 강조 보더·아이콘 |

### 1.3 텍스트
| 토큰 | HEX | 용도 |
|---|---|---|
| `--color-text` | `#191C1E` | 본문/헤딩 |
| `--color-text-secondary` | `#44474C` | 보조 |
| `--color-text-muted` | `#545F72` | 약한 텍스트 |
| `--color-placeholder` | `#74777D` | placeholder |
| `--color-on-ink` | `#FFFFFF` | 다크 배경 위 텍스트 |

### 1.4 상태 색 (배지/알림) — 시안에서 발견된 시스템
각 상태는 **fg(텍스트) + bg(배경)** 쌍. soft 배지 = `bg-*` 배경 + `*-fg` 텍스트.

| 상태 | fg | bg | solid | 매핑(백엔드) |
|---|---|---|---|---|
| **success** 승인/활성 | `#0E5138` | `#DCFCE7` (강조 `#B1F0CE`) | `#619D7F` | `profiles.status='approved'`, `products.status='active'` |
| **warning** 대기 | `#92400E` | `#FEF3C7` | `#D97706` | `status='pending'`(가입 승인 대기) |
| **danger** 거절/위험 | `#93000A` | `#FFDAD6` | `#BA1A1A`/`#EF4444` | `status='rejected'`, SOLD OUT, 삭제 |
| **info** 정보 | `#1A3A7A` | `#D2E4FB` | `#2F6FEB` | 일반 정보/배지 |
| **grade** 등급(연보라) | `#5B3FA0` | `#D1C4E9` | — | 셀러 등급/티어 배지 |
| **neutral** 보관/기타 | `--color-text-muted` | `--color-subtle` | — | `status='archived'`, 회색 배지 |

### 1.5 차트 팔레트
`--color-chart-1..6` = navy / sage / slate / amber / red / violet. 라인·바·도넛·퍼널 공통.

> 색상 원리: **쿨네이비+쿨그레이 UI** ↔ **웜톤 사진**의 의도적 대비. 모든 회색은 미세한 블루틴트로 네이비와 한 가족. 가격/권한 등 민감정보는 색이 아니라 라벨로 구분(가격 노출은 서버 권위 — CLAUDE.md).

---

## 2. 타이포그래피 (Typography)
> ⚠️ PDF 폰트는 **Type3 임베드(이름 없음)** → 폰트명 자동추출 불가. 아래는 **시각 식별 + 웹폰트 대응안**(확정 전 검토 필요).

### 2.1 폰트 식별
| 역할 | 시안 모습 | 추천 웹폰트 | 비고 |
|---|---|---|---|
| **로고타입** `ezmerce` | 고대비 세리프 **이탤릭** (Didone풍) | **Playfair Display** _italic_ (대안: Fraunces, Newsreader) | 로고/에디토리얼 강조에만 |
| **디스플레이 헤딩** "Elevate your…" | 헤비 그로테스크(헬베티카 계열) | **Pretendard** (Latin이 헬베티카풍) 800/700 | 별도 라틴폰트 불필요 |
| **본문/UI/한글** | 깔끔한 한글 산세리프 | **Pretendard (Variable)** | KR+Latin 단일 패밀리로 커버 |
| **(선택) 모노** | 품번/코드 | Geist Mono / JetBrains Mono | `platform_code` 표시 등 |

**핵심**: Pretendard 하나로 한글 본문 + 헬베티카풍 볼드 헤딩까지 커버하고, **Playfair Display 이탤릭은 로고타입에만** 쓰면 시안과 거의 일치한다.

### 2.2 폰트 로딩 (구현 시)
- 권장: `pretendard` npm 패키지 또는 [Pretendard CDN](https://cdn.jsdelivr.net/gh/orioncactus/pretendard) `@font-face`. Playfair Display는 `next/font/google`.
- `next/font`로 CSS 변수(`--font-sans`, `--font-serif`) 주입 → `ezmerce-tokens.css`의 `--font-*`가 이미 그 변수를 참조하도록 맞추거나, 토큰의 폰트 스택을 그대로 사용.
- 현재 `globals.css` body는 `Arial` 폴백(한글 미적용) → 구현 시 교체 필요.

### 2.3 타입 스케일 (토큰)
`--text-xs`(12) · `sm`(13) · `base`(15, 본문/인풋) · `md`(16) · `lg`(18) · `xl`(22, 카드제목) · `2xl`(30, 페이지제목) · `3xl`(36) · `display`(64, 마케팅 히어로).
라벨(예: "Member Type (회원 유형)")은 13–14px / medium / 살짝 letter-spacing.

---

## 3. 스페이싱·라운드·그림자
- **스페이싱**: 4px 베이스 그리드(8/12/16/24/32 빈출). Tailwind 기본 스케일 그대로.
- **라운드**: 인풋·버튼 `--radius`(8px), 카드 `--radius-lg`(12), 큰카드·모달 `--radius-xl`(16), 배지/아바타 `--radius-full`.
- **그림자**: `--shadow-xs~lg` (네이비 틴트, 절제됨). 인풋=보더 위주, 카드=`sm`, 팝오버/모달=`md~lg`.

---

## 4. 레이아웃 셸 (4종)
시안 36화면은 4개 셸 위에 구성됨 (상세: SCREEN-INVENTORY).
- **A. 인증 스플릿** — 좌: 풀블리드 쇼룸 사진 + 로고/카피, 우: 폼(로그인/가입). (p1~4, 27)
- **B. 다크 사이드바 어드민** — 좌 `#0F172A` 사이드바 + 우 라이트 콘텐츠. (대시보드/업로드/상품·파트너·주문 관리)
- **C. 에디토리얼 스토어프론트** — 상단 미니멀 헤더 + 흑백 상품 그리드(셀러 쇼룸/카탈로그). (p26, 28~33)
- **D. 에이전시 어드민** — 통합 대시보드형. (p34~36)

---

## 5. 컴포넌트 카탈로그
추후 빌드할 핵심 컴포넌트(시안에서 도출, 백엔드 매핑 포함). 상세 출현 화면은 SCREEN-INVENTORY 참조.

**입력/폼**: Button(primary 네이비 / secondary 회색 / ghost), 아이콘 텍스트인풋(envelope·lock·eye 토글), Select, Textarea, Checkbox, **세그먼트 탭**(Retailer/Wholesaler/Agency), **FileDropzone**("파일 선택" + JPG/PNG/PDF MAX 5MB), 수량 스텝퍼.
**데이터 표시**: 상품 Card(썸네일·재고·BEST/SOLD OUT 배지), DataTable(+페이지네이션·정렬), KPI 카드(▲▼ 델타), 차트(라인/바/도넛/퍼널), **칸반 보드**(주문), 장바구니 라인 + 주문요약.
**상태/피드백**: 상태 Badge(§1.4 색 시스템), 등급 Badge(연보라), 빈 상태(empty), Toast.
**오버레이/내비**: Modal(품번 매칭실패·결제), Popover(업로드), 4-step **마법사 스텝퍼**(대량 업로드), 4종 앱셸, 드롭다운.
**가격 노출 토글박스** — 관리자가 셀러별 `price_visibility`(wholesale/retail/none) 설정. **서버 권위**(CLAUDE.md) — UI는 표시만.

**컴포넌트 라이브러리 추천**: **shadcn/ui**(Tailwind v4 기반, 스킬 `vercel:shadcn`) — 위 토큰을 `@theme`에 매핑해 그대로 사용 가능. Button/Input/Select/Table/Badge/Tabs/Dialog/Popover 등 대부분 커버.

---

## 6. 이미지 자산
[ASSET-MANIFEST.md](ASSET-MANIFEST.md) 참조. 요약:
- `public/images/marketing/` — 쇼룸 히어로, 서류 플랫레이.
- `public/images/people/` — 모델 에디토리얼 2, 아바타, 정물 무드샷 3.
- `public/images/products/` — 데모 상품 사진 7(가방·드레스·니트·블레이저). **실서비스 상품 이미지는 업로드로 대체** — 이건 시안/데모용 placeholder.
- `public/brand/` — 로고 마크(추정, **템플릿 placeholder일 수 있음 — 검증 필요**). 실제 브랜드 요소는 `ezmerce` **세리프 워드마크(=폰트 텍스트)**.
- ⚠️ 자산 대부분 **512px급 목업 해상도** → 실배포 전 고해상 교체 권장.

---

## 7. 범위/주의 (중요)
- **시안 범위 ⊃ 1차 백엔드**: PDF는 POS·주문 칸반·분석·장바구니·에이전시 운영까지 그린 **전체 제품 비전**. 현재 백엔드(1차)는 상품/업로드/카탈로그/QR/계정승인까지. 화면 구현은 **PoC 범위부터**(TODO.md) — 나머지는 미래 참조.
- **템플릿 잔재**: 시안 p10에 `VogueCore / voguecore.com` 문구 잔존 → ezmerce로 교체 필요. 로고 마크/일부 정물·인물 사진도 템플릿 stock일 가능성.
- p21 vs p22는 동일 화면 용어 변형("리테일러/반려됨" vs "소매업체/거절됨") — 용어 통일 필요.
- 명시적 **QR 카드 전용 화면은 시안에 없음**(상품목록·엑셀출력과 연계 추정). 백엔드 `GET /p/{code}`는 구현됨 → 인스타 비율 카드는 토큰 기반 신규 디자인.

---

## 8. 다음 단계 (구현 시)
1. 폰트 설치·로딩(Pretendard + Playfair Display) → `globals.css` body 폰트 교체.
2. `globals.css`에 `@import "../styles/ezmerce-tokens.css";` 추가 → 유틸리티 활성.
3. shadcn/ui 설치 후 컴포넌트 테마를 본 토큰에 매핑.
4. 셸 A~D 레이아웃 → PoC 화면(로그인/가입·상품등록·업로드·QR카드) 순으로 구현.
