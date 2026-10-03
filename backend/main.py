import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

try:
    from backend.api.investigations import router as investigations_router
except ModuleNotFoundError:
    from api.investigations import router as investigations_router

app = FastAPI(title="Real-Time Crypto Fraud Attribution API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(investigations_router)


@app.get("/health")
def health():
    return {"status": "ok"}
