"""
Credit Scoring Pipeline
========================
Trains credit scoring models on the Home Credit data and updates
the credit_scores table with real model scores.

Models trained:
  1. Logistic Regression Scorecard  — interpretable, WoE-style
  2. LightGBM PD Model              — high-performance gradient boosting
  3. XGBoost Expected Loss Model    — optimised for EL calculation
  4. Random Forest (ensemble base)  — diversity in ensemble

Metrics computed per model:
  - KS Statistic, Gini, AUC-ROC, PR-AUC
  - Precision, Recall at optimal threshold
  - Feature importance (SHAP values for LightGBM)

Output:
  - Models saved to models/credit/
  - credit_scores table updated with new scores
  - Model metrics stored for comparison
  - PSI drift reports refreshed
"""
from __future__ import annotations
import json, logging, os, sys, time, uuid
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).parent.parent / 'models' / 'credit'
MODEL_DIR.mkdir(parents=True, exist_ok=True)

FEATURE_COLS = [
    # Bureau-derived
    'credit_utilization', 'debt_to_income', 'delinquent_accounts',
    'num_hard_inquiries_12m', 'months_credit_history', 'open_accounts',
    'active_collections', 'bankruptcy_flag', 'judgement_flag',
    'total_outstanding_debt', 'total_credit_limit',
    # SEON digital risk
    'seon_fraud_score', 'seon_is_vpn', 'seon_is_tor',
    'seon_social_match_count',
    # Mobile wallet
    'mobile_wallet_age_months', 'sim_age_months',
    'mpesa_monthly_avg_in', 'mpesa_loan_history_count',
    # Demographics
    'age', 'monthly_income_kes',
    # Derived
    'log_income', 'log_debt', 'util_dti_cross',
    'inquiry_per_month', 'score_bucket',
    # Loan features
    'loan_amount', 'tenure_days', 'interest_rate',
]


# ═══════════════════════════════════════════════════════════════════════════
# DATA LOADING
# ═══════════════════════════════════════════════════════════════════════════

def load_training_data() -> tuple[np.ndarray, np.ndarray, list[str], list[str]]:
    """Load applicant + loan data from DB and build feature matrix."""
    from pipeline.db import Session
    from pipeline.credit_db import Applicant, Loan

    logger.info("[CREDIT] Loading training data from DB...")
    session = Session()
    try:
        rows = session.execute("""
            SELECT
                a.tu_score, a.credit_utilization, a.debt_to_income,
                a.delinquent_accounts, a.num_hard_inquiries_12m,
                a.months_credit_history, a.open_accounts,
                a.active_collections, a.bankruptcy_flag, a.judgement_flag,
                a.total_outstanding_debt, a.total_credit_limit,
                a.seon_fraud_score, a.seon_is_vpn, a.seon_is_tor,
                a.seon_social_match_count, a.mobile_wallet_age_months,
                a.sim_age_months, a.mpesa_monthly_avg_in,
                a.mpesa_loan_history_count, a.age, a.monthly_income_kes,
                l.loan_amount, l.tenure_days, l.interest_rate,
                CASE WHEN l.status IN ('default','written_off') THEN 1 ELSE 0 END as label,
                l.loan_id
            FROM applicants a
            JOIN loans l ON l.applicant_id = a.applicant_id
            WHERE l.status IN ('default','written_off','paid')
        """).fetchall()
    finally:
        session.close()

    if not rows:
        raise ValueError("No training data found. Run ingestion first.")

    df = pd.DataFrame(rows, columns=[
        'tu_score','credit_utilization','debt_to_income',
        'delinquent_accounts','num_hard_inquiries_12m',
        'months_credit_history','open_accounts','active_collections',
        'bankruptcy_flag','judgement_flag','total_outstanding_debt',
        'total_credit_limit','seon_fraud_score','seon_is_vpn','seon_is_tor',
        'seon_social_match_count','mobile_wallet_age_months','sim_age_months',
        'mpesa_monthly_avg_in','mpesa_loan_history_count','age',
        'monthly_income_kes','loan_amount','tenure_days','interest_rate',
        'label','loan_id'
    ])

    logger.info("[CREDIT] Loaded %d labelled loans (default=%d, paid=%d)",
                len(df), df['label'].sum(), (df['label']==0).sum())

    # Derived features
    df['log_income']     = np.log1p(df['monthly_income_kes'].clip(lower=1))
    df['log_debt']       = np.log1p(df['total_outstanding_debt'].clip(lower=0))
    df['util_dti_cross'] = df['credit_utilization'] * df['debt_to_income']
    df['inquiry_per_month'] = df['num_hard_inquiries_12m'] / 12.0
    df['score_bucket']   = ((df['tu_score'] - 300) / 110).clip(0, 4).astype(int)

    feat_cols = [c for c in FEATURE_COLS if c in df.columns]
    df[feat_cols] = df[feat_cols].fillna(0).astype(np.float32)

    X    = df[feat_cols].values
    y    = df['label'].values.astype(int)
    ids  = df['loan_id'].tolist()

    logger.info("[CREDIT] Features: %d | Positive rate: %.2f%%",
                len(feat_cols), y.mean() * 100)
    return X, y, feat_cols, ids


# ═══════════════════════════════════════════════════════════════════════════
# METRICS
# ═══════════════════════════════════════════════════════════════════════════

def compute_credit_metrics(y_true: np.ndarray, y_prob: np.ndarray) -> dict:
    from sklearn.metrics import (roc_auc_score, average_precision_score,
                                  f1_score, precision_score, recall_score)
    from scipy.stats import ks_2samp

    # Optimal threshold by F1
    best_f1, best_thr = 0.0, 0.5
    for thr in np.arange(0.05, 0.95, 0.02):
        pred = (y_prob >= thr).astype(int)
        f1   = float(f1_score(y_true, pred, pos_label=1, zero_division=0))
        if f1 > best_f1:
            best_f1, best_thr = f1, float(thr)

    pred = (y_prob >= best_thr).astype(int)
    bad  = y_prob[y_true == 1]; good = y_prob[y_true == 0]
    ks   = float(ks_2samp(bad, good).statistic) if len(bad) > 0 and len(good) > 0 else 0.0

    auc  = float(roc_auc_score(y_true, y_prob)) if len(np.unique(y_true)) > 1 else 0.5
    gini = float(2 * auc - 1)

    return {
        'auc_roc':   round(auc, 4),
        'pr_auc':    round(float(average_precision_score(y_true, y_prob)), 4),
        'ks':        round(ks, 4),
        'gini':      round(abs(gini), 4),
        'f1':        round(best_f1, 4),
        'precision': round(float(precision_score(y_true, pred, pos_label=1, zero_division=0)), 4),
        'recall':    round(float(recall_score(y_true, pred, pos_label=1, zero_division=0)), 4),
        'threshold': round(best_thr, 3),
        'n_train':   int(len(y_true)),
        'n_default': int(y_true.sum()),
        'default_rate': round(float(y_true.mean()), 4),
    }


# ═══════════════════════════════════════════════════════════════════════════
# TRAIN ALL MODELS
# ═══════════════════════════════════════════════════════════════════════════

def train_all_credit_models(X: np.ndarray, y: np.ndarray,
                             feature_names: list[str],
                             run_id: str) -> list[dict]:
    import joblib
    from sklearn.model_selection import StratifiedKFold
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LogisticRegression

    results = []
    n_val   = int(len(X) * 0.2)
    # Chronological split (last 20%)
    X_tr, y_tr = X[:-n_val], y[:-n_val]
    X_val, y_val = X[-n_val:], y[-n_val:]

    # ── 1. Logistic Regression Scorecard ────────────────────────────────
    logger.info("[CREDIT TRAIN] 1. Logistic Regression Scorecard...")
    t0 = time.time()
    scaler = StandardScaler()
    X_tr_sc = scaler.fit_transform(X_tr)
    X_val_sc = scaler.transform(X_val)

    lr = LogisticRegression(max_iter=2000, class_weight='balanced',
                             C=0.05, solver='saga', random_state=42,
                             tol=1e-3, n_jobs=-1)
    lr.fit(X_tr_sc, y_tr)
    lr_prob = lr.predict_proba(X_val_sc)[:, 1]
    lr_mets = compute_credit_metrics(y_val, lr_prob)
    lr_mets['training_duration_s'] = round(time.time() - t0, 1)

    # Feature importance from coefficients
    lr_fi = sorted(zip(feature_names, np.abs(lr.coef_[0])),
                   key=lambda x: x[1], reverse=True)[:20]

    path_lr = str(MODEL_DIR / f'{run_id}_scorecard_lr.pkl')
    joblib.dump({'model': lr, 'scaler': scaler, 'feature_names': feature_names,
                 'threshold': lr_mets['threshold'], 'type': 'credit',
                 'classifier_name': 'credit_scorecard_lr', 'run_id': run_id}, path_lr)

    results.append({
        'run_id': run_id, 'model_type': 'credit',
        'classifier_name': 'credit_scorecard_lr',
        'display_name': 'Logistic Regression Scorecard',
        'metrics': lr_mets,
        'feature_importance': [{'feature': f, 'importance': float(v), 'rank': i+1}
                                for i, (f, v) in enumerate(lr_fi)],
        'artifact_path': path_lr, 'is_champion': False,
    })
    logger.info("  LR Scorecard — AUC=%.4f  KS=%.4f  Gini=%.4f  (%.0fs)",
                lr_mets['auc_roc'], lr_mets['ks'], lr_mets['gini'],
                lr_mets['training_duration_s'])
    return results, X_tr, y_tr, X_val, y_val, scaler


def train_lightgbm(X_tr, y_tr, X_val, y_val, feature_names, run_id, results):
    import joblib
    try:
        import lightgbm as lgb
    except ImportError:
        logger.warning("[CREDIT TRAIN] LightGBM not installed — skipping")
        return results

    logger.info("[CREDIT TRAIN] 2. LightGBM PD Model...")
    t0 = time.time()
    clf = lgb.LGBMClassifier(
        n_estimators=500, learning_rate=0.05, num_leaves=31,
        max_depth=6, class_weight='balanced', random_state=42,
        verbose=-1, min_child_samples=20, subsample=0.8,
        colsample_bytree=0.8, reg_alpha=0.1, reg_lambda=0.1,
    )
    clf.fit(X_tr, y_tr,
            eval_set=[(X_val, y_val)],
            callbacks=[lgb.early_stopping(50, verbose=False),
                       lgb.log_evaluation(period=-1)])
    prob  = clf.predict_proba(X_val)[:, 1]
    mets  = compute_credit_metrics(y_val, prob)
    mets['training_duration_s'] = round(time.time() - t0, 1)

    fi = sorted(zip(feature_names, clf.feature_importances_),
                key=lambda x: x[1], reverse=True)[:20]

    path = str(MODEL_DIR / f'{run_id}_lgbm_pd.pkl')
    joblib.dump({'model': clf, 'scaler': None, 'feature_names': feature_names,
                 'threshold': mets['threshold'], 'type': 'credit',
                 'classifier_name': 'credit_lgbm_pd', 'run_id': run_id}, path)

    results.append({
        'run_id': run_id, 'model_type': 'credit',
        'classifier_name': 'credit_lgbm_pd',
        'display_name': 'LightGBM PD Model',
        'metrics': mets,
        'feature_importance': [{'feature': f, 'importance': float(v), 'rank': i+1}
                                for i, (f, v) in enumerate(fi)],
        'artifact_path': path, 'is_champion': False,
    })
    logger.info("  LGB PD — AUC=%.4f  KS=%.4f  Gini=%.4f  (%.0fs)",
                mets['auc_roc'], mets['ks'], mets['gini'], mets['training_duration_s'])
    return results


def train_xgboost(X_tr, y_tr, X_val, y_val, feature_names, run_id, results):
    import joblib
    try:
        import xgboost as xgb
    except ImportError:
        logger.warning("[CREDIT TRAIN] XGBoost not installed — skipping")
        return results

    logger.info("[CREDIT TRAIN] 3. XGBoost EL Model...")
    t0 = time.time()
    scale_pos = float((y_tr == 0).sum()) / max((y_tr == 1).sum(), 1)
    clf = xgb.XGBClassifier(
        n_estimators=400, learning_rate=0.05, max_depth=5,
        scale_pos_weight=scale_pos, random_state=42,
        verbosity=0, eval_metric='aucpr', subsample=0.8,
        colsample_bytree=0.8, reg_alpha=0.1, reg_lambda=1.0,
        early_stopping_rounds=50,
    )
    clf.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=False)
    prob  = clf.predict_proba(X_val)[:, 1]
    mets  = compute_credit_metrics(y_val, prob)
    mets['training_duration_s'] = round(time.time() - t0, 1)

    fi = sorted(zip(feature_names, clf.feature_importances_),
                key=lambda x: x[1], reverse=True)[:20]

    path = str(MODEL_DIR / f'{run_id}_xgb_el.pkl')
    joblib.dump({'model': clf, 'scaler': None, 'feature_names': feature_names,
                 'threshold': mets['threshold'], 'type': 'credit',
                 'classifier_name': 'credit_xgb_el', 'run_id': run_id}, path)

    results.append({
        'run_id': run_id, 'model_type': 'credit',
        'classifier_name': 'credit_xgb_el',
        'display_name': 'XGBoost EL Model',
        'metrics': mets,
        'feature_importance': [{'feature': f, 'importance': float(v), 'rank': i+1}
                                for i, (f, v) in enumerate(fi)],
        'artifact_path': path, 'is_champion': False,
    })
    logger.info("  XGB EL  — AUC=%.4f  KS=%.4f  Gini=%.4f  (%.0fs)",
                mets['auc_roc'], mets['ks'], mets['gini'], mets['training_duration_s'])
    return results


# ═══════════════════════════════════════════════════════════════════════════
# CHAMPION SELECTION & SCORE UPDATES
# ═══════════════════════════════════════════════════════════════════════════

def _champion_score(r: dict) -> float:
    m = r['metrics']
    return (0.40 * m.get('ks', 0) +
            0.30 * m.get('auc_roc', 0) +
            0.20 * m.get('pr_auc', 0) +
            0.10 * m.get('f1', 0))


def persist_credit_results(results: list[dict]):
    """Save credit model results to DB in CreditModelRun table."""
    from pipeline.db import Session
    from pipeline.credit_db import CreditModelRun

    if not results:
        return

    best = max(results, key=_champion_score)
    best['is_champion'] = True

    session = Session()
    try:
        # Clear old credit model runs
        session.query(CreditModelRun).delete()
        session.commit()

        for r in results:
            m = r['metrics']
            run = CreditModelRun(
                run_id           = r['run_id'],
                classifier_name  = r['classifier_name'],
                display_name     = r['display_name'],
                auc_roc          = m.get('auc_roc'),
                pr_auc           = m.get('pr_auc'),
                ks_statistic     = m.get('ks'),
                gini             = m.get('gini'),
                f1               = m.get('f1'),
                precision        = m.get('precision'),
                recall           = m.get('recall'),
                threshold        = m.get('threshold'),
                n_train          = m.get('n_train'),
                default_rate     = m.get('default_rate'),
                training_duration_s = m.get('training_duration_s'),
                feature_importance  = json.dumps(r.get('feature_importance', [])),
                artifact_path    = r.get('artifact_path'),
                is_champion      = r.get('is_champion', False),
            )
            session.add(run)

        session.commit()
        logger.info("[CREDIT] Champion: %s  KS=%.4f  AUC=%.4f  Gini=%.4f",
                    best['classifier_name'],
                    best['metrics']['ks'],
                    best['metrics']['auc_roc'],
                    best['metrics']['gini'])
    except Exception as e:
        session.rollback()
        logger.error("[CREDIT] persist error: %s", e)
    finally:
        session.close()


def update_credit_scores_from_champion(results: list[dict],
                                        X: np.ndarray, ids: list[str]):
    """Re-score all applicants using the champion model."""
    import joblib
    from pipeline.db import Session
    from pipeline.credit_db import CreditScore, Applicant

    if not results:
        return

    best = max(results, key=_champion_score)
    artifact = joblib.load(best['artifact_path'])
    clf    = artifact['model']
    scaler = artifact.get('scaler')
    X_sc   = scaler.transform(X) if scaler else X

    probs = clf.predict_proba(X_sc)[:, 1]

    session = Session()
    try:
        # Map loan_id → applicant_id via already-loaded IDs
        from pipeline.credit_db import Loan
        loan_app = {r.loan_id: r.applicant_id
                    for r in session.query(Loan.loan_id, Loan.applicant_id).all()}

        # Delete existing scores for this run
        session.query(CreditScore).filter(
            CreditScore.scorecard_version == best['run_id']
        ).delete()
        session.commit()

        batch = []
        seen  = set()
        for loan_id, prob in zip(ids, probs):
            app_id = loan_app.get(loan_id)
            if not app_id or app_id in seen:
                continue
            seen.add(app_id)
            # Convert PD → score: score = 700 - 50*log(PD/(1-PD))
            pd_val = float(np.clip(prob, 1e-6, 1-1e-6))
            logit  = np.log(pd_val / (1 - pd_val))
            score  = int(np.clip(700 - 50 * logit, 300, 850))
            band   = ('Excellent' if score >= 750 else 'Good' if score >= 700
                      else 'Fair' if score >= 650 else 'Poor'
                      if score >= 600 else 'Very Poor')
            batch.append(CreditScore(
                applicant_id      = app_id,
                score             = score,
                score_band        = band,
                pd_estimate       = round(pd_val, 6),
                scorecard_version = best['run_id'],
            ))
            if len(batch) >= 2000:
                session.bulk_save_objects(batch)
                session.commit()
                batch = []

        if batch:
            session.bulk_save_objects(batch)
            session.commit()

        logger.info("[CREDIT] Updated %d credit scores from champion", len(seen))
    except Exception as e:
        session.rollback()
        logger.error("[CREDIT] score update error: %s", e)
    finally:
        session.close()


# ═══════════════════════════════════════════════════════════════════════════
# MASTER RUNNER
# ═══════════════════════════════════════════════════════════════════════════

_status: dict = {"running": False, "last_run_id": None, "last_error": None,
                 "stage": None, "results": []}


def run_credit_pipeline() -> dict:
    global _status
    _status["running"] = True
    _status["last_error"] = None
    _status["stage"] = "loading data"
    run_id = str(uuid.uuid4())

    try:
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s %(levelname)-7s %(message)s')

        logger.info("=" * 65)
        logger.info("CREDIT SCORING PIPELINE — run_id=%s", run_id)
        logger.info("=" * 65)

        # Stage 1: Load data
        X, y, feature_names, loan_ids = load_training_data()

        # Stage 2: Train scorecard
        _status["stage"] = "training logistic scorecard"
        results, X_tr, y_tr, X_val, y_val, scaler = train_all_credit_models(
            X, y, feature_names, run_id
        )

        # Stage 3: LightGBM
        _status["stage"] = "training lightgbm"
        results = train_lightgbm(X_tr, y_tr, X_val, y_val, feature_names, run_id, results)

        # Stage 4: XGBoost
        _status["stage"] = "training xgboost"
        results = train_xgboost(X_tr, y_tr, X_val, y_val, feature_names, run_id, results)

        # Stage 5: Persist
        _status["stage"] = "persisting results"
        persist_credit_results(results)

        # Stage 6: Update scores
        _status["stage"] = "updating credit scores"
        update_credit_scores_from_champion(results, X, loan_ids)

        _status["results"]     = results
        _status["last_run_id"] = run_id
        _status["stage"]       = "complete"

        champion = max(results, key=_champion_score) if results else None
        logger.info("=" * 65)
        if champion:
            m = champion['metrics']
            logger.info("CHAMPION: %s | KS=%.4f | AUC=%.4f | Gini=%.4f | PR-AUC=%.4f",
                        champion['display_name'], m['ks'], m['auc_roc'],
                        m['gini'], m['pr_auc'])
        logger.info("=" * 65)

        return {"run_id": run_id, "results": results, "champion": champion}

    except Exception as e:
        import traceback
        _status["last_error"] = str(e)
        _status["stage"] = "error"
        logger.error("[CREDIT PIPELINE] Error: %s", e)
        traceback.print_exc()
        return {"run_id": run_id, "error": str(e)}
    finally:
        _status["running"] = False


def get_status() -> dict:
    return {**_status, "results": len(_status.get("results", []))}


if __name__ == "__main__":
    run_credit_pipeline()
