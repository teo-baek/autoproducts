# ezmerce 이미지 자산 manifest

> 출처: `ezmerce.pdf` 임베드 이미지 추출(2026-06-04). 원본 348개 → 중복제거 192 → 마스크/래스터텍스트/UI패널 제외 → **재사용 가능한 22개 큐레이션**.
> 위치: `apps/web/public/` (앱에서 서빙) · 참조 컨택트시트: `apps/web/design/assets/`
>
> ⚠️ **공통 주의**: 모두 시안용 **목업 해상도(대개 512px급)** + AI/stock 생성 placeholder. **실배포 전 고해상·실상품 이미지로 교체** 전제. 상품 사진은 데모/카탈로그 골격 확인용.

## marketing — `public/images/marketing/`
| 파일 | 크기 | 용도 | 원본 |
|---|---|---|---|
| `hero-showroom.jpg` | 512×343 | 인증 스플릿(셸A) 좌측 풀블리드 히어로, 마케팅 | img-000 |
| `flatlay-documents.jpg` | 512×512 | 빈 상태/온보딩/마케팅 보조컷(서류 플랫레이) | img-200 |

## people / editorial / still-life — `public/images/people/`
| 파일 | 크기 | 용도 | 원본 |
|---|---|---|---|
| `model-blazer-cream.jpg` | 512×512 | 에디토리얼(스토어프론트는 흑백 filter 적용) | img-294 |
| `model-coat-charcoal.jpg` | 512×512 | 에디토리얼 | img-292 |
| `avatar-businessman.jpg` | 156×156 | 프로필/테스티모니얼 아바타 (placeholder) | img-130 |
| `stilllife-jewelry.jpg` | 128×128 | 에이전시 무드샷 (주얼리) | img-324 |
| `stilllife-texture-dark.jpg` | 128×128 | 에이전시 무드샷 (다크 텍스처/배경) | img-322 |
| `stilllife-boxes.jpg` | 128×128 | 에이전시 무드샷 (패키징 박스) | img-320 |

## products (데모 placeholder) — `public/images/products/`
| 파일 | 크기 | 품목 | 원본 |
|---|---|---|---|
| `bag-cognac.jpg` | 512×512 | 코냑 가죽 탑핸들백 | img-296 |
| `bag-black-tote.jpg` | 512×512 | 블랙 구조형 토트백 | img-254 |
| `dress-ivory-satin.jpg` | 512×512 | 아이보리 새틴 슬립 드레스 | img-252 |
| `knit-top-ivory.jpg` | 420×420 | 아이보리 니트 톱(폼) | img-060 |
| `blazer-ivory-hanger.jpg` | 512×512 | 아이보리 블레이저(행어) | img-256 |
| `blazer-gray-hanger.jpg` | 556×730 | 그레이 블레이저(행어) | img-282 |
| `blazer-black.jpg` | 512×512 | 블랙 블레이저 | img-250 |

## brand marks — `public/brand/` ⚠️ 검증 필요
> 시안에 래스터로 박힌 마크. **템플릿 placeholder 추정** — 실제 ezmerce 브랜드 자산이 아닐 수 있음(시안 워드마크 `ezmerce`는 세리프 **폰트 텍스트**라 별도 자산 불필요). LALAS/실브랜드 확정 후 교체.
| 파일 | 크기 | 비고 | 원본(+mask) |
|---|---|---|---|
| `mark-L.png` | 64×64 | "L" 세리프 레터마크(흰 배경). ezmerce와 무관 → LALAS/템플릿 추정 | img-338(+339) |
| `emblem-seal.png` | 64×64 | 다크 원형 씰 엠블럼(장식, 템플릿 추정) | img-340(+341) |

> (img-138 "emblem"은 실제로 **소프트 글로우/그림자 레이어**라 콘텐츠 없음 → 제외함.)

## 참조 컨택트시트 — `design/assets/`
- `contact-products.jpg` — 상품 사진 12타일(파일명 라벨).
- `contact-editorial.jpg` — 히어로/모델 고해상 컷.
- `contact-small.jpg` — 소형 이미지(로고/아바타/정물/썸네일).

## 제외한 것 (자산 아님)
- 다크 네이비 **UI 패널**, "Elevate your wholesale management." **래스터 헤딩**, 텍스트/네비 strip, 전체 페이지 **UI 스크린샷**(2576px) — 토큰+컴포넌트로 재구성하므로 미추출.
- smask(알파 마스크) 86개 — 로고 3건만 합성에 사용.

## 재추출 방법 (필요 시)
```bash
pdfimages -all ezmerce.pdf /tmp/out/img        # 원본 추출
# 중복제거: md5 기준 / 색공간: sips -g space (RGB=사진, Gray=마스크)
# 컨택트시트: magick montage <files> -tile 6x -geometry 260x260 -label '%t %wx%h' sheet.png
```
