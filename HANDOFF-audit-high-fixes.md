# HANDOFF — 리스크 감사 HIGH 처리 (다음 세션)

> 다음 세션 시작 경로: `HANDOFF-audit-high-fixes.md`
> 작성: 2026-06-07 / 브랜치: `v2-dev` / 백엔드 **150 passed**
> 감사 원본 리포트: `docs/audit/2026-06-06-221326-audit-risk.html` (gitignored — 브라우저로 열어 필터/검색 가능)
> 같이 보기: 규칙 [CLAUDE.md](CLAUDE.md) · [HANDOFF.md](HANDOFF.md) · [TODO.md](TODO.md)

## 🎯 목표
`/audit-risk` 결과의 **HIGH 등급을 마저 처리**한다. 리포트상 High는 **총 12건**인데 **1건(엑셀 export 원본 다운로드 루프)은 이미 Critical 수정 때 함께 해소**(썸네일 우선 + TTL 캐시, `excel_export.py`). 남은 **11건을 아래 3개 클러스터**로 묶었다.

> ✅ 이미 처리됨 (다시 하지 말 것): **api `products.py:159-198` 도매 export 이미지 루프** = Critical(`catalog.py` export 루프)과 같은 패턴이라 `cell_image_path`(썸네일 우선)+`cell_image_bytes` TTL 캐시로 동시 해결됨(2026-06-07, TODO §3 참고).

---

## ⚠️ 공통 제약 (반드시 지킬 것 — CLAUDE.md)
- **DDL/마이그레이션은 Claude가 실행 못 함** → `.sql` 파일만 작성하고 **사용자가 Supabase SQL Editor에서 실행**. (RPC 함수·컬럼 암호화·CHECK 제약 등 전부 해당)
- **soft delete 전면**: hard DELETE 금지(보상 로직도 `deleted_at` 사용). 단 회원가입 orphan auth user 정리는 GoTrue `auth.admin.delete_user`가 예외적으로 필요(아래 A-1).
- **가격은 `visible_price()` 단일 진실** 통과 — 이 작업들과 무관하지만 셰이핑 우회 금지.
- **service_role 키는 서버 전용**(RLS 우회 중). 프론트는 anon 키.
- **병행 작업 건드리지 말 것**: 사장님이 진행 중인 **셀러 쇼룸(`apps/web/.../seller/showroom`, `lib/catalog.ts`)** 과 **공개 카드 로그인 뷰(`public.py` `shape_card_skus`, `/p` login)**, **price_code 앞2자리 규칙**(`excel_export.py`) 은 그대로 둔다.
- **커밋은 사용자가 직접** — 작업 후 커밋하지 말 것.
- 테스트: `cd backend && .venv/bin/python -m pytest -q` (현재 150 passed 유지).

---

## 🅰️ 클러스터 A — 데이터 일관성 / 트랜잭션 부재 (High ×4) — ✅ 완료(2026-06-07, 앱 보상)
모두 `sensitive_logic / no-transaction`. supabase-py(PostgREST)는 다중 statement를 한 트랜잭션으로 못 묶어서, 단계 중 하나가 실패하면 **고아(orphan) 행**이 남는다.

> ✅ **사용자 결정 = 전부 앱레벨 보상**(RPC/DDL 없음). 2단계 실패 시 except 에서 1단계 산출물을 정리(되돌리기). best-effort 원자성(보상 자체가 실패하면 원래 예외 우선 전파 + `log.warning`). 백엔드 **159 passed**(보상 테스트 6개 추가). 라이브 반영엔 백엔드 재시작 필요(`make stop && make dev`).

| # | 위치 | 문제 | 보상 처리 |
|---|---|---|---|
| A-1 | `accounts.py register_account` | 회원가입: `create_auth_user()` 성공 후 `insert_profile()` 실패 → auth.users 고아 | ✅ `repo.delete_auth_user()` (GoTrue 하드 삭제 — soft-delete 대상 아님) |
| A-2 | `products.py register_product` | 상품 단건: `insert_product → insert_skus` 비원자 → SKU 없는 빈 product | ✅ `repo.soft_delete_product()` |
| A-3 | `uploads.py ingest_excel` | 대량 등록: product 생성 후 SKU 실패 → 고아 product | ✅ 그룹별 `soft_delete_product()` + 해당 그룹 error 기록 |
| A-4 | `accounts.py approve_account` | 승인: `create_wholesaler` 후 `set_status` 실패 → 고아 wholesaler | ✅ `repo.soft_delete_wholesaler()` |

추가된 repo 메서드: `SupabaseAuthRepo.delete_auth_user`(auth.py), `SupabaseProductRepo.soft_delete_product`(products.py), `SupabaseUploadRepo.soft_delete_product`(uploads.py), `SupabaseAdminRepo.soft_delete_wholesaler`(admin.py). 더 단단히 하려면 향후 A-2/A-3을 `create_product_with_skus` RPC(plpgsql 단일 트랜잭션)로 승격 가능(DDL 필요 — 보류).

<details><summary>원래 인계 내용(참고용)</summary>

| # | 위치 | 문제 |
|---|---|---|
| A-1 | `backend/app/services/accounts.py:53-70` | 회원가입: `create_auth_user()` 성공 후 `insert_profile()` 실패 → **auth.users 고아**. 같은 이메일 재가입 영구 불가 |
| A-2 | `backend/app/services/products.py:4-21` | 상품 단건 등록: `next_platform_code → insert_product → insert_skus` 비원자 → SKU 없는 빈 product + platform_code 소비 |
| A-3 | `backend/app/services/uploads.py:122-158` | 대량 등록(ingest_excel): product 생성 후 SKU 실패 → 고아 product(재업로드도 막힘) |
| A-4 | `backend/app/services/accounts.py:20-28` | 계정 승인: `create_wholesaler` 후 `set_status` 실패 → 고아 wholesaler + 승인 미연결 |

</details>

**권장 방향 (둘 중 택, 사용자 확인 필요):**
- **(권장) Postgres RPC(plpgsql) 단일 트랜잭션** — A-2/A-3은 `create_product_with_skus(product JSONB, skus JSONB[])` 한 함수로 묶기. **DDL이라 사용자가 SQL 실행**. 앱은 RPC 호출로 교체.
- **앱레벨 보상(try/except)** — A-1은 실패 시 `repo.sb.auth.admin.delete_user(auth_user['id'])`, A-4는 생성한 wholesaler를 soft-delete. RPC보다 빠르게 적용 가능(쉬운 시작점).
- **시작 순서 제안**: A-1·A-4는 보상 로직으로 즉시, A-2·A-3은 RPC(또는 insert_skus 실패 시 product soft-delete 보상).

**테스트**: fake repo로 "2단계에서 예외 주입 → 1단계 산출물이 정리(보상)되는지" 검증. 기존 `tests/test_register_service.py`, `tests/test_products_service.py`, `tests/test_accounts_service.py`, `tests/test_uploads_service.py` 패턴 활용.

---

## 🅱️ 클러스터 B — PII 과다 노출 / 평문 저장 (High ×4)
| # | 위치 | 문제 | 난이도 |
|---|---|---|---|
| B-1 | `backend/app/routers/admin.py:17-18` | `GET /admin/accounts`가 profiles `select('*')` 반환 → phone·full_name·**id_doc_path·business_cert_path**(신분증/사업자등록증 경로)까지 응답 | 쉬움 |
| B-2 | `backend/app/core/auth.py:53` | `get_current_user`가 profiles `select('*')` → 민감 컬럼 전부 네트워크 전송(응답엔 CurrentUser 필드만) | 쉬움 |
| B-3 | `backend/migrations/2026-06-03_v2_core.sql:33` | `phone` 평문 저장(암호화 없음) | 중(DDL) |
| B-4 | `backend/migrations/2026-06-05_v2_core_06_register_fields.sql:8-9` | `id_doc_path`·`business_cert_path` 평문 저장 → DB 유출 시 문서 접근 단서 | 중(DDL) |

**권장 방향:**
- **B-1/B-2 먼저(쉽고 안전)**: `select('*')` → **필요 컬럼만 명시**. admin 응답에서 문서 경로 제거하거나 **별도 signed-URL 조회 엔드포인트**로 분리. ⚠️ admin 화면이 어떤 필드를 쓰는지 `apps/web/src/lib/products.ts`의 `Account` 타입(이미 agency_id/agency_name 추가됨)·admin 페이지 확인 후 컬럼 목록 맞출 것.
- **B-3/B-4(DDL, 사용자 실행)**: pgcrypto 암호화 또는 최소한 RLS로 admin/본인만 SELECT. **암호화 택하면 phone 읽기/쓰기 전 경로에 encrypt/decrypt 래핑 필요**(회원가입·admin 조회 등) — 범위 크니 사용자와 1차 수준(암호화 vs RLS-only) 합의 후 진행.

**테스트**: admin 라우트 응답에 `id_doc_path`/`business_cert_path` 미포함 단언, get_current_user select 컬럼 축소 회귀.

---

## 🅲 클러스터 C — 인젝션 + 인증/등록 성능 (High ×3)
| # | 위치 | 문제 | 영역 |
|---|---|---|---|
| C-1 | `backend/app/routers/products.py:107-109` | **PostgREST `or_()` DSL 주입** — `search`를 f-string으로 `.or_(f"item_name.ilike.{like},source_p_number.ilike.{like}")`에 삽입. `search=foo,id.eq.<uuid>` 류로 필터 변조 가능 | governance/sql-injection |
| C-2 | `backend/app/core/auth.py:43-56` | 모든 요청마다 profiles 조회(캐시 없음) — 인증 의존성이라 전 엔드포인트 영향 | api/no-cache |
| C-3 | `backend/app/services/uploads.py:132-143` | 대량 등록 상품당 `next_platform_seq` RPC **N+1** | api/n-plus-1 |

**권장 방향:**
- **C-1(보안, 우선)**: `search` 입력에서 PostgREST 메타문자(`,` `.` `(` `)` `*` `:`)를 화이트리스트 정규식으로 제거하거나, `.or_` 대신 컬럼별 분리 호출. ⚠️ **상단바 검색(`SearchProvider`)이 실사용 중**(`products/page.tsx`) — 동작 유지하며 sanitize. (B-2와 같은 파일군이라 함께.)
- **C-2**: user_id→CurrentUser **TTL(30~60초) in-process 캐시** 또는 프로필 정보를 JWT custom claim에. 캐시 시 승인상태/price_visibility 변경 반영 지연 주의(짧은 TTL).
- **C-3**: `SELECT nextval('platform_code_seq', N)`로 N개 일괄 발급하는 **배치 RPC**(DDL, 사용자) 또는 호출 횟수 축소. SEQUENCE라 발급 자체는 원자적(중복 없음) — 순수 성능 이슈.

**테스트**: C-1은 `search` 악성 입력 시 필터 변조 안 됨(sanitize) 단언. C-3은 배치 발급 길이/유일성.

---

## ✅ 시작 전 체크 / 결정 필요 (다음 세션이 사용자에게 확인)
1. **트랜잭션 방식**: RPC(plpgsql, 사용자 SQL 실행) vs 앱 보상 — 클러스터 A 어디까지 RPC로 갈지.
2. **PII 저장(B-3/B-4)**: 암호화(pgcrypto) vs RLS-only — 1차 운영 수준 합의. (서버가 service key라 RLS는 방어선 보강용)
3. **우선순위 제안**: C-1(인젝션·보안) → B-1/B-2(select 좁히기, 저위험·즉효) → A-1/A-4(보상) → A-2/A-3(RPC) → B-3/B-4·C-2/C-3(DDL/성능). 보안 먼저, DDL 필요분은 묶어서 사용자 실행.

## 참고 위치
- 가격 셰이핑 `app/services/pricing.py` / 인증 `app/core/auth.py` / 업로드 `app/services/uploads.py` / 이미지 URL 헬퍼 `app/services/images.py`
- 마이그레이션 실행순서 `backend/migrations/README.md` (새 `.sql`은 다음 번호로 추가)
- 변경 시 `cd backend && .venv/bin/python -m pytest -q` 통과 유지(현재 150).
