"""FastAPI Application entrypoint for Real-Time Crypto Fraud Attribution System.

Shared backend integrating Member 1 (Tracing), Member 2 (Intelligence/Attribution),
and Member 3 (Frontend/Supabase).
"""

import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Load environment configuration from .env
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router as attribution_router
from backend.monitoring.provider import ConnectorTransactionProvider
from backend.monitoring.scheduler import global_background_worker

try:
    from backend.api.investigations import router as investigations_router
except ModuleNotFoundError:
    from api.investigations import router as investigations_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: plug live connectors into the monitoring worker, then start it
    global_background_worker.set_transaction_provider(ConnectorTransactionProvider())
    global_background_worker.start()
    yield
    # Shutdown: Stop worker gracefully
    global_background_worker.stop()


app = FastAPI(
    title="Real-Time Crypto Fraud Attribution System API",
    description="Forensic investigation API for multi-hop tracing, VASP attribution, explainable risk scoring, and evidence report generation.",
    version="1.0.0",
    lifespan=lifespan,
)

# Load allowed origin from environment (coordinated with Member 3's frontend URL)
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")

# Enable CORS for React frontend with credentials
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        FRONTEND_ORIGIN,
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from starlette.requests import Request

@app.middleware("http")
async def prefix_compat_middleware(request: Request, call_next):
    if request.url.path.startswith("/victim/") and not request.url.path.startswith("/victim/api/"):
        request.scope["path"] = "/api" + request.url.path
    return await call_next(request)

from backend.api.v1 import cases_router
from backend.api.victim import router as victim_router
from backend.api.intake import router as intake_router

# Mount Member Routers
app.include_router(attribution_router)
app.include_router(investigations_router)
app.include_router(cases_router)
app.include_router(victim_router)
app.include_router(intake_router)


@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "service": "crypto-fraud-attribution-backend",
        "role_member_2": "Member 2: Intelligence Engine (Attribution, Risk Scoring, Monitoring, and PDF Reports)",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)

