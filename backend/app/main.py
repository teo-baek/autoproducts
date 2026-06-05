from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import admin, auth, catalog, products, public, uploads

app = FastAPI(title="ezmerce API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # RISK(breaking): 운영 전 화이트리스트로 좁힐 것
    allow_methods=["*"],
    allow_headers=["*"],
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
