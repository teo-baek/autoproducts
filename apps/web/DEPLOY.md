# 프론트 배포 — Firebase Hosting (`make deploy-web`)

`apps/web`(Next.js 16, 순수 클라이언트 SPA)를 **정적 export(`out/`) → Firebase Hosting**으로 배포한다.
루트에서 `make deploy-web` 한 줄. (백엔드 = Cloud Run `make deploy-api` / 둘 다 = `make deploy`)

```
make deploy-web-login   # 맨 처음 1회: 전용 구글계정 브라우저 로그인 (격리)
make deploy-web         # 그 다음부터 이거만 — 정적 빌드 → 배포
```

- `next.config.ts` 에 `output: "export"` → `next build` 시 `out/` 생성(라우트별 HTML).
- Firebase는 `firebase.json` 의 `cleanUrls:true` 로 `/login` → `login.html` 매칭(SPA catch-all 안 씀 — Next export는 라우트별 HTML이라 catch-all이 오히려 깨뜨림).
- 빌드 시 `NEXT_PUBLIC_API_BASE_URL` = 백엔드 Cloud Run URL(`deploy.env` 의 `WEB_API_BASE_URL`)을 주입.
  Supabase 키(`NEXT_PUBLIC_SUPABASE_*`)는 `apps/web/.env.local` 에서 자동으로 읽힘.
- firebase CLI 인증은 `XDG_CONFIG_HOME=.firebase-ezmerce` 로 격리 → 개인/타 프로젝트 firebase 로그인과 안 섞임.

## 사전 1회
1. **GCP 프로젝트에 Firebase 연결**: https://console.firebase.google.com → **프로젝트 추가** →
   "기존 Google Cloud 프로젝트"에서 **`ezmerce` 선택** → 완료. (Hosting 기본 사이트 `ezmerce.web.app` 자동 생성)
2. `deploy.env` 의 `WEB_API_BASE_URL` = 백엔드 Cloud Run URL (이미 설정됨).
3. `make deploy-web-login` → 브라우저에서 **전용 구글계정**으로 로그인(개인계정 X).

## 배포
```bash
make deploy-web
```
끝나면 `https://ezmerce.web.app` (및 `*.firebaseapp.com`)로 접속.

## ⚠️ 주의
- **CORS**: 백엔드가 아직 `allow_origins=["*"]` 라 지금은 호출됨. 운영 굳히기 전,
  백엔드 CORS를 `https://ezmerce.web.app`(+커스텀 도메인)으로 좁히기.
- **백엔드 URL 바뀌면 재빌드**: `NEXT_PUBLIC_API_BASE_URL` 은 빌드타임에 구워짐 → `make deploy-web` 다시.
- **QR 카드**(`/p/{code}`)는 백엔드 라우트라 `PUBLIC_BASE_URL`(백엔드 deploy.env)이 백엔드 URL을 가리킴 — 프론트와 무관.
