"""
FastAPI application entry point — Credit Risk Intelligence Platform
(Fraud Detection + Credit Scoring + Risk Analytics + A/B Testing)
Run with: uvicorn api.main:app --reload --port 8000 --host 127.0.0.1
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.routers import (
    analytics, transactions, predictions, review,
    training, explainability, pipeline,
)
from api.routers.auth import router as auth_router
from api.routers.credit import router as credit_router
from api.routers.risk_analytics import router as risk_router
from api.routers.ab_testing import router as ab_router
from api.routers.cost_analysis import router as cost_router
from api.routers.credit_training import router as credit_training_router
from api.routers.insights import router as insights_router
from pipeline.db import init_db
from config.settings import FRONTEND_ORIGIN

app = FastAPI(
    title="Credit Risk Intelligence Platform",
    description=(
        "Unified platform: fraud detection, credit scoring, risk analytics, "
        "A/B testing, cost analysis — simulating a real mobile lending institution."
    ),
    version="2.0.0",
    openapi_url="/api/openapi.json",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        FRONTEND_ORIGIN,
        "https://browser-psi-opal.vercel.app",
        "https://browser-nckptephv-creditiq.vercel.app",
        "https://creditiq.vercel.app",
        "http://localhost:4200",
        "http://localhost:4300",
        "http://127.0.0.1:4300",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Public ───────────────────────────────────────────────────────────────────
app.include_router(auth_router, prefix="/api")

# ── Fraud Detection (existing) ────────────────────────────────────────────────
app.include_router(pipeline.router,        prefix="/api/pipeline",        tags=["Pipeline"])
app.include_router(analytics.router,       prefix="/api/analytics",       tags=["Analytics"])
app.include_router(transactions.router,    prefix="/api/transactions",    tags=["Transactions"])
app.include_router(predictions.router,     prefix="/api/predictions",     tags=["Predictions"])
app.include_router(review.router,          prefix="/api/review",          tags=["Review"])
app.include_router(training.router,        prefix="/api/training",        tags=["Training"])
app.include_router(explainability.router,  prefix="/api/explainability",  tags=["Explainability"])

# ── Credit Risk (new) ─────────────────────────────────────────────────────────
app.include_router(credit_router,          prefix="/api/credit",          tags=["Credit Scoring"])
app.include_router(risk_router,            prefix="/api/risk",            tags=["Risk Analytics"])
app.include_router(ab_router,              prefix="/api/ab",              tags=["A/B Testing"])
app.include_router(cost_router,            prefix="/api/cost",            tags=["Cost Analysis"])
app.include_router(credit_training_router, prefix="/api/credit-training", tags=["Credit Pipeline"])
app.include_router(insights_router,        prefix="/api/insights",        tags=["AI Insights"])


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "CreditIQ — Risk Intelligence Platform v2.0"}


@app.get("/api/ping")
def ping():
    """Keep-alive endpoint — called every 5 minutes to prevent Render cold start."""
    return {"pong": True}


@app.on_event("startup")
def on_startup():
    init_db()
    from pipeline.credit_db import init_credit_db
    init_credit_db()

    import threading
    from pipeline.db import Session as _Session, Transaction as _Transaction
    from pipeline.credit_db import Applicant as _Applicant
    from config.settings import RAW_DATA_DIR as _RAW
    from pathlib import Path as _Path

    session = _Session()
    try:
        txn_count = session.query(_Transaction).count()
        app_count = session.query(_Applicant).count()
    finally:
        session.close()

    # Auto-ingest fraud transactions if empty
    if txn_count == 0 and (_Path(_RAW) / "train.csv").exists():
        print("[STARTUP] Empty fraud DB — auto-ingesting raw CSVs...")
        from api.routers.pipeline import _ingest_bg
        t = threading.Thread(target=_ingest_bg, args=(_RAW,), daemon=True)
        t.start()

    # Auto-seed credit/risk data if empty
    if app_count == 0:
        print("[STARTUP] Empty credit DB — seeding dummy data...")
        from pipeline.dummy_data import run_seed
        t2 = threading.Thread(target=run_seed, daemon=True)
        t2.start()


# ── Serve Angular SPA (must come LAST) ───────────────────────────────────────
# Angular 17+ builder outputs to dist/<project>/browser/
_CANDIDATE_PATHS = [
    # Relative: works locally and when rootDir=backend on Render
    Path(__file__).resolve().parent.parent.parent / "frontend" / "dist" / "fraud-detection" / "browser",
    Path(__file__).resolve().parent.parent.parent / "frontend" / "dist" / "fraud-detection",
    # Absolute Render path
    Path("/opt/render/project/src/frontend/dist/fraud-detection/browser"),
    Path("/opt/render/project/src/frontend/dist/fraud-detection"),
]

_FRONTEND_DIST: Path | None = next((p for p in _CANDIDATE_PATHS if p.exists()), None)

if _FRONTEND_DIST:
    print(f"[SPA] Serving Angular from: {_FRONTEND_DIST}")
    # Serve static assets (js, css, images) directly
    app.mount("/assets", StaticFiles(directory=str(_FRONTEND_DIST / "assets")), name="assets") if (_FRONTEND_DIST / "assets").exists() else None

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str):
        # Skip API routes (shouldn't reach here, but safety net)
        if full_path.startswith("api/"):
            from fastapi import HTTPException
            raise HTTPException(status_code=404)
        candidate = _FRONTEND_DIST / full_path
        if candidate.is_file():
            return FileResponse(str(candidate))
        # All other paths → index.html (Angular client-side routing)
        return FileResponse(str(_FRONTEND_DIST / "index.html"))
else:
    print("[SPA] Angular dist not found — serving API only")

    @app.get("/", include_in_schema=False)
    def root():
        return {"status": "ok", "docs": "/api/docs", "health": "/api/health"}
