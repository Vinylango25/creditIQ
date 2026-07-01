# CreditIQ — Risk Intelligence Platform

A full-stack ML platform simulating a real mobile lending / fintech institution.  
Covers **credit scoring**, **risk analytics**, **fraud detection**, **A/B testing**, and **cost/ROI analysis**.

---

## Platform Overview

| Module | What it does |
|---|---|
| **Fraud Detection** | Real-time transaction scoring · SHAP/LIME explainability · Human-in-the-loop review |
| **Credit Scoring** | Bureau-enriched applicant profiles (TransUnion + SEON) · PD/LGD/EAD modelling |
| **Risk Analytics** | FPD · Vintage curves · Roll rates · KS/Gini · PSI drift · Expected Loss |
| **A/B Testing** | Champion/challenger experiments · Statistical significance · Power analysis |
| **Cost Analysis** | ROI waterfall · Savings simulation · Model value vs. baseline |
| **ML Pipeline** | AutoML (FLAML) · 10 classifiers · MLflow tracking · Active learning |

---

## Quick Start

```bash
# 1. Backend
cd fraud_detection/backend
pip install -r requirements.txt
cp .env.example .env
uvicorn api.main:app --reload --port 8000

# 2. Frontend (separate terminal)
cd fraud_detection/frontend
npm install --legacy-peer-deps
npx ng serve --port 4300
```

App → http://localhost:4300  
API docs → http://localhost:8000/api/docs

On first startup the API auto-seeds 5,000 applicants and 12,000 loans.

---

## Login Credentials

| Email | Password | Role |
|---|---|---|
| `analyst@creditiq.ai` | `analyst2026` | Risk Analyst |
| `admin@creditiq.ai`   | `admin2026`   | Admin |
| `demo@creditiq.ai`    | `demo`        | Viewer |

---

## Navigation

```
Overview        → Dashboard · Transactions
Fraud           → Advanced Analytics (3D) · Model Comparison · Model Health
Credit          → Credit Scoring · Loan Portfolio · Applicant Profiles
Risk            → Risk Overview · FPD Analysis · Vintage & Cohorts
A/B & Cost      → A/B Testing · Cost & ROI Analysis
Explainability  → SHAP · LIME · Feature Importance
ML Pipeline     → Pipeline & Training · Human-in-the-Loop Review
```

---

## Stack

**Backend:** Python 3.11 · FastAPI · SQLAlchemy · SQLite/PostgreSQL · FLAML AutoML · LightGBM · XGBoost · CatBoost · SHAP · MLflow · scikit-learn · scipy

**Frontend:** Angular 20 · ngx-echarts · RxJS · Angular Signals

---

## Data

- **Fraud dataset:** ~590k training transactions (Kenya + Nigeria mobile payments)
- **Credit dataset:** 5,000 simulated applicants with bureau-grade fields (TransUnion-style) + SEON digital risk enrichment + 12,000 loans with full lifecycle tracking
- **Simulated figures** are used for cost analysis — documented assumptions in each endpoint

---

## Key Metrics & Formulas

```
Champion composite  = 0.50 × Recall + 0.20 × PR-AUC + 0.20 × AUC-ROC + 0.10 × F1
Expected Loss (EL)  = PD × LGD × EAD
Credit score range  = 300–850  (A ≥ 750, B ≥ 700, C ≥ 650, D ≥ 600, E < 600)
PSI thresholds      = < 0.10 stable · 0.10–0.25 warning · > 0.25 alert
FPD target          = < 5% (mobile lending industry benchmark)
```
