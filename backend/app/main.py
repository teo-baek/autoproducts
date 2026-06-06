from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routers import admin, auth, catalog, products, public, uploads

app = FastAPI(title="ezmerce API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # RISK(breaking): 운영 전 화이트리스트로 좁힐 것
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception):
    # 처리 안 된 예외의 500 은 CORSMiddleware 바깥(ServerErrorMiddleware)에서 만들어져
    # Access-Control-Allow-Origin 헤더가 빠진다 → 브라우저엔 'CORS 오류'로 보임.
    # 여기서 직접 ACAO 를 달아 실제 에러 메시지가 프론트에 도달하도록 한다(개발: allow_origins=*).
    return JSONResponse(
        status_code=500,
        content={"detail": f"서버 오류: {str(exc)[:200]}"},
        headers={"Access-Control-Allow-Origin": "*"},
    )

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(products.router)
app.include_router(public.router)
app.include_router(catalog.router)
app.include_router(uploads.router)


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    # 로컬 실행: `python -m app.main` (기본 포트 8444, PORT env 로 override 가능)
    import os

    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8444")),
        reload=True,
    )
