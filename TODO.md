# ezmerce — 할 일 (TODO)

> 앞으로의 작업 정리. 상태/인수인계는 [HANDOFF.md](HANDOFF.md), 설계/변경이력은 `docs/features/2026-06-03-ezmerce-v2-backend/`.
> 기준: **개발정의서.pptx** — p.1 타임라인(PoC/MVP), p.2 Phase 1(코어 엔진), p.3 Phase 2(주문/배송).
> 최종 갱신: 2026-06-07

## 단계 정의 (개발정의서 p.1)
| 단계 | 데드라인 | 범위 |
|---|---|---|
| **PoC** | 라이브 방송 2~3일 전 (**~6/13**) | 상품 등록 · 엑셀 출력 · QR 연동 |
| **MVP / Deathline** | 이후 | 위 + **폐쇄형 카탈로그 뷰** |
| **Phase 2** | 후속 | 주문 자동 라우팅 · 배송 동기화 대시보드 · 그리드 UI |

---

## 0. 현재 상태 (한눈에)
- **백엔드**: PoC 범위 + 카탈로그 뷰 엔드포인트까지 **구현 완료**. 단위 **65 passed**, **라이브 스모크 24/0 PASS**. DB 마이그레이션 `_v2_core`~`_05` 라이브 적용됨.
- **프론트(web/, Next.js)**: 스캐폴드만 존재, API 연동 화면 **미착수**.
- **남은 핵심**: 프론트 화면 + Storage 버킷 + 배포. (백엔드 API는 거의 다 나옴)

---

## 1. PoC (~6/13) — 남은 일  🔴 최우선
백엔드 API는 완료. 남은 건 **프론트 + 인프라**.

### 백엔드/인프라
- [ ] **product-images Storage 버킷 생성**(비공개) + `storage.objects` RLS — 이미지 대량 업로드용. (프론트가 직접 업로드 → 백엔드는 경로 기록·매칭. *현재 매칭 API는 매니페스트만으로 동작하므로 실파일 업로드 화면이 붙을 때 필요*)
- [ ] **CORS 화이트리스트** — `app/main.py` 현재 `allow_origins=["*"]`(개발용). 운영 도메인으로 좁히기.
- [ ] **배포** — FastAPI 호스팅(서버/컨테이너) + `.env`(SUPABASE_URL/SERVICE_KEY/PUBLIC_BASE_URL) 주입. `PUBLIC_BASE_URL` = QR 카드 실도메인으로 설정.
- [ ] **프론트 로그인 → JWT 흐름** — 프론트가 Supabase Auth 로그인 후 받은 JWT 를 백엔드 `Authorization: Bearer` 로 전달(백엔드는 JWKS 검증 완료). 

### 프론트 (web/)
- [ ] **상품 등록 화면** — 단건 등록 폼(`POST /products`) + **표준 엑셀 템플릿 대량 업로드**(`POST /uploads/excel`).
- [ ] **이미지 대량 업로드 + 매칭 화면** — Storage 직접 업로드 → `POST /uploads/images` → **미매칭 목록**(`GET /uploads/{job}/unmatched`) → **수작업 매칭**(`POST /uploads/{job}/match`).
- [ ] **상품 관리** — 목록 + 수정/삭제/**보관(Archive=PATCH status)**. *상세(읽기) 모달 완료(2026-06-06): 목록 행 클릭 → `ProductDetailModal`(이미지 갤러리·기본정보·**모든 색상×사이즈 SKU 표**·QR/공개카드 링크). 정적 export라 `/products/[id]` 대신 모달. 목록이 든 Product(전체 skus)를 재요청 없이 사용.*
- [ ] **엑셀 다운로드 버튼** — `GET /catalog/export.xlsx`(셀러/에이전시 역할별 셰이핑) · `GET /products/export.xlsx`(도매 본인 관리뷰). *백엔드는 **사진·QR 박은 A~K 스타일**(`build_render_xlsx`, jinsup 방송제품목록 동일) 완료(2026-06-06) — 폼텍 대체. 프론트 `downloadProductsXlsx` 이미 연결됨.* *QR 열(K): catalog·products export **둘 다 QR 이미지 대신 링크 URL 텍스트**(`qr_as_link=True`, 2026-06-07) — products export 도 링크로 통일.*
- [x] **QR 카드 페이지** — `apps/web/src/app/p/page.tsx`(공개, **인스타 4:5 카드**, 가격 미노출). 정적 export라 **`/p?code=EZM-…` 쿼리+클라 페치**(`GET /p/{code}` JSON). QR URL도 이 형식(`qr_target_url`). `PUBLIC_BASE_URL`=프론트 주소(dev :3555). ⚠️ **정적 export+클라페치라 폰 스캔 시 백엔드도 그 기기에서 닿아야 함**(폰 테스트=LAN IP 양쪽, 운영=Firebase+Cloud Run).

---

## 2. MVP — 폐쇄형 카탈로그 뷰  🟡
- [x] **셀러 쇼룸현황(프론트)** — `/seller/showroom`. 승인 셀러 로그인 → **카드 1장 = (상품 × 색상)**, 사이즈는 카드 안에 `사이즈→재고` 표(기획 확정 2026-06-06; 도매 상품관리=상품1행, SKU 단위 카드 X). 노출 필드 = **품번 · 이미지 · 색상 · 재고·예약(사이즈별) · 도매가**. *예약(committed)은 별도 데이터가 아니라 **`product_skus.stock` 음수분**으로 표현(현장 규칙): `stock=-1` → 재고 0 / 예약 1 (`available=max(0,stock)`, `committed=max(0,-stock)`, `lib/catalog.ts`).* `GET /catalog`(역할별 가격 셰이핑) 연동, **내보내기**=`GET /catalog/export.xlsx` 연결. 셸=에디토리얼 상단 네비(SHOWROOM/ORDERS/ANALYTICS), `SellerGate`(retail_seller 전용)·`SellerShell`. ORDERS/ANALYTICS 는 준비중(`ComingSoon`). *백엔드: `GET /catalog` 응답에 `source_p_number`(품번)·`fabric_composition`(혼용률)·`representative_image_url`·skus.`stock`·`created_at` 노출 추가(마이그레이션 없음, 기존 컬럼).* *컬러칩(2026-06-07): 색상명 옆 스와치 표시 — 한글/영문 색상명→hex 매핑(`lib/colors.ts`, 연/진 명도 보정 + 미매핑은 점선 칩 폴백). 혼용률도 카드에 표기.* ⚠️ 색상별 이미지 데이터는 없어 같은 상품의 색상 카드들은 **대표 이미지를 공유**(색상별 이미지 필요 시 `product_images` 색상 태깅 선행). 상품명은 기획 5필드 외지만 가독성용으로 보조 노출 중.
  - [ ] **쇼룸 필터/정렬** — 카테고리·시즌·재고상태 드롭다운 + 정렬 아이콘. **현재 마크업만 주석 보존**(`showroom/page.tsx` 헤더). 백엔드 `GET /catalog` 에 필터 파라미터 없음 + **`season`·`stock_status` 는 DB 컬럼 자체가 없음** → 백엔드(컬럼/파라미터) 선행 후 주석 해제.
  - [ ] **베스트셀러 배지** — 판매량 집계 데이터 없음 → 카드 마크업 주석 보존. 집계 백엔드 생기면 해제.
- [ ] **(에이전시) 카탈로그 뷰** — 에이전시 실운영 시. 1차 미운영.
- [ ] **관리자 계정 승인 UI** — `GET /admin/accounts` + approve/reject + `price-visibility` 설정 화면. *셀러 유형 구분 완료(2026-06-07): 어드민 "유형" 컬럼이 **라이브셀러(independent) vs 에이전시 소속(agency_affiliated)** 을 뱃지로 구분, 에이전시 소속이면 **소속 에이전시명**도 표기. 백엔드 `GET /admin/accounts` 가 `agency_id→name`(`SupabaseAdminRepo.agency_map` + `shape_account_rows`)으로 `agency_name` 보강 — **1차엔 에이전시 미운영이라 전부 라이브셀러로 표시**되지만, 운영 시작(가입 복구) 시 자동 노출.*

---

## 3. 기술부채 / 하드닝  🟢 (라이브 동작엔 지장 없음, 운영 전 정리 권장)
- [ ] **클라이언트 리사이즈 + 직통 업로드 (이미지)** — 기획 결정(2026-06-06). 고화질 불필요 → **업로드 시 브라우저에서 이미지를 가볍게 리사이즈해 Storage로 직접** 올린다(서버는 큰 바이트를 안 만짐). 그동안 겪은 저장용량·메모리·요청크기 문제를 뿌리부터 해소.
  - **스펙(확정)**: **WebP · 긴 변 1280px** · 품질 ~0.8 · **EXIF 회전 보정**(`createImageBitmap(blob, {imageOrientation:'from-image'})` 또는 canvas) · 장당 ~100KB 목표.
  - **범위**: 개별 이미지 + **폴더 선택(`webkitdirectory`)** + **ZIP(브라우저 JSZip 로 해제)** 모두 **클라에서 리사이즈 후 직통 업로드**. 수백 장은 **배치 처리**(브라우저 멈춤/메모리 방지). 큰 묶음은 **폴더 선택이 zip보다 유리**(zip 은 통째로 메모리에 풀어야 함).
  - **효과**: Supabase 무료 1GB 가 ~20–30배 더 감 / Cloud Run 메모리·요청 32MB·ZIP 100MB 한계 **사실상 해소** / egress↓ / 업로드 속도↑.
  - **백엔드 영향(단순화)**: `POST /uploads/zip/stage`·서버 썸네일(`services/image_process.py`)·`product_images.thumbnail_path`(`_08`) **제거/축소 가능**. `POST /uploads/commit`(엑셀+매니페스트)·`attach_images`(품번 매칭/기록)는 **유지**. 저장 키는 ASCII(이미 적용), 원본 한글 파일명은 `original_filename` 으로 매칭.
  - **주의**: 서버 권위 이미지 가공이 사라지므로 클라 산출물을 신뢰(B2B 카탈로그라 무방). 파일명→품번 매칭 로직은 그대로(매니페스트 `original_filename`).
- [ ] **대표 이미지 일원화(선택)** — 대량 업로드는 `product_images` 에만 기록하고 `products.representative_image_url` 은 비워둠(단일 업로드만 채움). 공개 카드는 읽기 시 폴백(`public._pick_image`)으로 해결(2026-06-06). 더 깔끔하려면 **이미지 매칭(`attach_images`) 시 대표 이미지를 `representative_image_url` 로 승격** → 목록/상세/카드/엑셀 한 소스 일관. 기존분은 1회 백필.
- [x] **엑셀 export 이미지 N+1 완화** (audit Critical, 2026-06-07) — `cell_image_bytes`에 **인스턴스 TTL 캐시(10분)** + `cell_image_path`로 **썸네일(`thumbnail_path`) 우선·원본 fallback**. `/catalog/export.xlsx`·`/products/export.xlsx` 동시 적용(공유 헬퍼). 결과물 동일·셀 110px 화질 무변. 실측: 원본 181KB→썸네일 91KB→셀 3.7KB, 반복 export 캐시 적중. ⚠️ **남은 것: export rate-limit(운영 직전 선택)**. 클라 리사이즈 TODO 들어오면 썸네일 개념 정리 필요.
- [x] **uploads 트랜잭션 / orphan 방지** (리뷰 #3 · audit A-3, 2026-06-07) — 엑셀 대량 등록 중 SKU 삽입 실패 시 방금 만든 상품을 **soft-delete 보상**(`ingest_excel` + `SupabaseUploadRepo.soft_delete_product`). 고아 상품 제거됨. *더 단단히 하려면 job-first 또는 `create_product_with_skus` RPC(plpgsql 단일 트랜잭션, DDL) — 선택.*
- [ ] **export 대표가격 폴백** (리뷰 #6) — `_export_row` 가 노출 모드를 명시적으로 받도록 리팩터(현재 첫 SKU 폴백 추론).
- [ ] **error_detail JSONB 직렬화** (리뷰 #8) — 엑셀에 날짜/Decimal 셀 섞이면 `raw` 직렬화 실패 가능 → `str()` 정규화.
- [ ] **upload_jobs RLS 정책** — 현재 정책 부재(앱레이어 소유권 가드로 방어 중, 서비스키라 RLS 우회). 방어선 보강용 SELECT/ALL 정책 추가 검토.
- [ ] **품번에 구분자(-/_/공백) 포함 시 이미지 자동매칭 한계** — 파일명 매처가 토큰 분리. 정확 stem 일치 또는 수작업 매칭으로 커버(현행). 필요 시 매칭 규칙 보강.
- [ ] **인증 강화 (나중에)** — 1차는 이메일+비밀번호(Supabase Auth)만으로 가입/로그인. 추후 **휴대폰 문자(SMS) 인증**(가입 시 번호 인증 / 2FA) 추가 예정. *(현재는 빡센 인증 의도적으로 생략)*

### 리스크 감사(audit) HIGH 후속 — 보안 / PII / 성능
> 출처: `docs/audit/2026-06-06-221326-audit-risk.html`(High 12건). 인계: [HANDOFF-audit-high-fixes.md](HANDOFF-audit-high-fixes.md). A 시각설명: `docs/cluster-a-orphan-compensation.html`.

- [x] **A. 트랜잭션 / 일관성 (4건)** — ✅ 완료(2026-06-07, **앱 보상**, DDL 없음, 백엔드 159 passed). 회원가입 orphan auth(`delete_auth_user`) · 상품/대량등록 orphan product(`soft_delete_product`) · 승인 orphan wholesaler(`soft_delete_wholesaler`). 보상 자체 실패 시 `log.warning` + 원래 예외 우선 전파.
- [ ] **B. PII 노출 / 평문 저장 (4건)** 🔴 운영 전 정리
  - [ ] **B-1** `app/routers/admin.py` `GET /admin/accounts` — `select("*")` → **필요 컬럼만**. ⚠️ 지금 응답에 `id_doc_path`·`business_cert_path`(신분증/사업자등록증 경로) + 내부 감사컬럼(created_by/updated_by)까지 노출 → 문서경로는 **제출여부 boolean** 또는 **signed-URL 별도 엔드포인트**로 분리. *(DDL 없음·즉효, 트레이드오프 X)*
  - [ ] **B-2** `app/core/auth.py` `get_current_user`(+`get_current_user_optional`) — `select("*")` → **CurrentUser 8필드만**(`id,role,status,seller_type,wholesaler_id,agency_id,price_visibility,company_name`). 응답 자체는 안전하나 매 인증요청마다 민감컬럼(phone·문서경로)이 Postgres→서버 와이어를 탐. *(DDL 없음·즉효)*
  - [ ] **B-3** `phone` 평문 저장(`migrations/2026-06-03_v2_core.sql`) — pgcrypto 암호화 **또는** RLS. *(DDL, 사장님 SQL 실행)*
  - [ ] **B-4** `id_doc_path`·`business_cert_path` 평문 저장(`migrations/..._06_register_fields.sql`) — 암호화 또는 RLS. DB 유출 시 서류 경로 단서. *(DDL)*
  - **결정 필요**: B-3/B-4 = **pgcrypto 암호화 vs RLS-only**. (서버가 service key라 RLS는 우회되지만 직접 DB접근 방어선 보강용.) 1차 운영 수준 합의 후 진행. B-1/B-2 먼저(안전·즉효) 권장.
- [ ] **C. 인젝션 + 성능 (3건)** 🟡 후순위(사용자 결정) — 단 C-1은 보안
  - [ ] **C-1 (보안·인젝션)** `app/routers/products.py:~110` — `.or_(f"item_name.ilike.{like},source_p_number.ilike.{like}")` **f-string DSL 주입**. `search`에 PostgREST 메타문자(`, . ( ) * :`) 화이트리스트 sanitize 또는 컬럼별 분리 호출. ⚠️ **C 중 우선순위 높음(보안).** 상단바 검색(`SearchProvider`) 실사용 중 — 동작 유지하며 sanitize.
  - [ ] **C-2 (성능)** `app/core/auth.py` — 매 요청 profiles 조회(캐시 없음, 전 엔드포인트 영향). user_id→CurrentUser **TTL(30~60초) in-process 캐시**. ⚠️ admin 승인/`price_visibility` 변경이 TTL만큼 반영 지연 → 짧게.
  - [ ] **C-3 (성능)** `app/services/uploads.py` `ingest_excel` — 상품당 `next_platform_seq` RPC **N+1**. `nextval(seq, N)` 배치 발급 RPC(DDL) 또는 호출 축소. SEQUENCE라 발급 자체는 원자적(중복 없음) — 순수 성능.

---

## 4. 명시적 비범위 (다음 단계)
- **비정형 엑셀 자동 파싱** — 1차는 **표준 템플릿만**(확정, requirements §비범위). 업체별 양식 자동 인식은 후속.
- **에이전시 실운영** — 역할/테이블/`agency_id` 데이터 모델만 forward-compat. 실제 운영 미구현. **에이전시 회원가입은 1차 비활성(코드 삭제 X, 주석 처리)** → 운영 시작 시 복구(아래 Phase 2 체크 항목 참조).

---

## 5. Phase 2 (개발정의서 p.3) — 후속
- [ ] **예약(Committed) — 재고 음수분 규칙** ⚠️ 예약은 별도 컬럼이 아니라 **`product_skus.stock` 이 음수로 내려간 분량**으로 표현(현장 규칙). 쇼룸 카드는 이미 `available=max(0,stock)` / `committed=max(0,-stock)` 로 사이즈별 재고·예약을 표시한다 → **추가 DB 컬럼 불필요**. 단 **stock 을 음수로 만드는 주문/예약 처리(라이프사이클)** 는 Phase 2: 셀러 발주/예약이 들어오면 해당 SKU `stock` 을 차감(음수 허용)하는 흐름. 주문 라우팅(아래)과 함께 설계. *(참고: 음수 재고가 일반 카탈로그/엑셀 등 다른 출력에서 어떻게 보일지도 그때 함께 점검.)*
- [ ] 셀러 자체 주문 엑셀 업로드 → 백엔드 파싱 → **도매업체별 주문 자동 라우팅/발주**.
- [ ] **실시간 배송 상태 동기화** — 도매상이 주문/대기/확정 수정, 셀러 전용 대시보드 즉시 반영.
- [ ] **그리드형 통합 관리 UI** — 엑셀 유사 웹 UI, 주문/배송 일괄 수정·완료.
- [ ] **영수증/견적서 출력** — 소매업체 유형별 가격 차등(에이전시 소속 셀러는 가격 미표시, 제품 정보만). ⚠️ 구현 시 반드시 `pricing.visible_price()` 통과(CLAUDE.md §가격 노출).
- [ ] **조직 위임 관리** — 에이전시/연합 리더가 소속 셀러를 직접 관리(가입·가격노출 등). 현재 admin 단일 관리 → 조직 단위 위임으로 확장.
- [ ] **에이전시 회원가입 복구** — 1차에서 의도적으로 비활성(코드는 주석으로 보존). 에이전시 실운영 적용 시 주석 해제로 복구. 풀 위치:
  - 프론트 `apps/web/src/app/register/page.tsx` — `MEMBER_OPTIONS` 의 `agency` 옵션 줄 주석 해제(`MemberType`/`COPY.agency` 는 이미 유지됨).
  - 백엔드 `app/services/accounts.py` — `_SELF_REGISTER_ROLES` 에 `"agency"` 추가(주석 해제). 추가하면 `role=="agency"` 친화 거부 분기는 자동 미도달.
  - 테스트 `backend/tests/test_register_service.py` — `test_register_agency_rejected_phase1` 제거 + 그 아래 주석된 `test_register_agency_role_has_null_seller_type` 복원.
  - (참고) `app/schemas/auth.py` docstring 의 "1차 비활성" 문구 원복.

---

## 6. 열린 질문 / 결정 필요
- [ ] PoC 배포 형태 — API 단독(내부용) vs 최소 프론트 동반? 6/13 데드라인 기준 우선순위.
- [ ] 프론트 인증 UX — Supabase Auth 직접 vs 백엔드 경유. (가입은 `POST /auth/register` 백엔드 확정)
- [ ] 호스팅 대상 — FastAPI 배포처(Fly/Render/Cloud Run 등) 결정.
