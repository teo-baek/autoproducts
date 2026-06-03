from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="ezmerce API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # RISK(breaking): 운영 전 화이트리스트로 좁힐 것
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}
