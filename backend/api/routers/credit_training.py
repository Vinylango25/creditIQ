"""
/api/credit-training — Credit Scoring Model Pipeline
Triggers, monitors, and exposes results of the credit scoring ML pipeline.
"""
from __future__ import annotations
import json, sys, os, threading
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import APIRouter, HTTPException
from sqlalchemy import desc

from pipeline.db import Session
from pipeline.credit_db import CreditModelRun

router = APIRouter()

_thread: threading.Thread | None = None


@router.post("/run")
def trigger_credit_pipeline():
    """Start the credit scoring pipeline in a background thread."""
    global _thread
    from pipeline.credit_pipeline import get_status, run_credit_pipeline

    status = get_status()
    if status["running"]:
        raise HTTPException(status_code=409, detail="Credit pipeline already running")

    def _bg():
        run_credit_pipeline()

    _thread = threading.Thread(target=_bg, daemon=True, name="credit-pipeline")
    _thread.start()
    return {"status": "started", "message": "Credit scoring pipeline running in background"}


@router.get("/status")
def get_credit_pipeline_status():
    try:
        from pipeline.credit_pipeline import get_status
        return get_status()
    except Exception as e:
        return {"running": False, "stage": None, "last_error": str(e)}


@router.get("/models")
def get_credit_models():
    """Return all trained credit scoring models."""
    session = Session()
    try:
        runs = session.query(CreditModelRun).order_by(desc(CreditModelRun.trained_at)).all()
        return [
            {
                "id":               r.id,
                "run_id":           r.run_id,
                "classifier_name":  r.classifier_name,
                "display_name":     r.display_name or r.classifier_name,
                "is_champion":      r.is_champion,
                "auc_roc":          round(r.auc_roc or 0, 4),
                "pr_auc":           round(r.pr_auc or 0, 4),
                "ks_statistic":     round(r.ks_statistic or 0, 4),
                "gini":             round(r.gini or 0, 4),
                "f1":               round(r.f1 or 0, 4),
                "precision":        round(r.precision or 0, 4),
                "recall":           round(r.recall or 0, 4),
                "threshold":        round(r.threshold or 0.5, 3),
                "n_train":          r.n_train,
                "default_rate":     round(r.default_rate or 0, 4),
                "training_duration_s": round(r.training_duration_s or 0, 1),
                "trained_at":       r.trained_at.isoformat() if r.trained_at else None,
            }
            for r in runs
        ]
    finally:
        session.close()


@router.get("/models/{model_id}/feature-importance")
def get_credit_feature_importance(model_id: int):
    session = Session()
    try:
        run = session.get(CreditModelRun, model_id)
        if not run:
            raise HTTPException(status_code=404, detail="Model not found")
        fi = json.loads(run.feature_importance or "[]")
        return fi
    finally:
        session.close()


@router.get("/champion")
def get_credit_champion():
    session = Session()
    try:
        champ = session.query(CreditModelRun).filter_by(is_champion=True)\
                       .order_by(desc(CreditModelRun.trained_at)).first()
        if not champ:
            return {"status": "no_model", "message": "Run the credit pipeline first"}
        return {
            "classifier_name": champ.classifier_name,
            "display_name":    champ.display_name,
            "auc_roc":         round(champ.auc_roc or 0, 4),
            "ks_statistic":    round(champ.ks_statistic or 0, 4),
            "gini":            round(champ.gini or 0, 4),
            "pr_auc":          round(champ.pr_auc or 0, 4),
            "f1":              round(champ.f1 or 0, 4),
            "threshold":       round(champ.threshold or 0.5, 3),
            "trained_at":      champ.trained_at.isoformat() if champ.trained_at else None,
        }
    finally:
        session.close()


@router.post("/ingest")
def trigger_home_credit_ingest(sample: int = 100000, force: bool = False):
    """Trigger Home Credit data ingestion in background."""
    def _bg():
        from pipeline.ingest_home_credit import run
        run(n_sample=sample, force=force)

    t = threading.Thread(target=_bg, daemon=True, name="hc-ingest")
    t.start()
    return {"status": "started", "sample": sample,
            "message": f"Ingesting {sample} Home Credit records in background"}


@router.get("/ingest-status")
def get_ingest_status():
    session = Session()
    try:
        from pipeline.credit_db import Applicant, Loan
        return {
            "applicants": session.query(Applicant).count(),
            "loans":      session.query(Loan).count(),
        }
    finally:
        session.close()
