# CreditIQ — Setup & Run Guide

Credit Risk Intelligence Platform · Python 3.11+ · Angular 20 · FastAPI · SQLite · MLflow

---

## Project Structure

```
fraud_detection/
├── backend/
│   ├── api/
│   │   ├── main.py                    ← FastAPI (port 8000)
│   │   └── routers/
│   │       ├── auth.py                ← JWT session login
│   │       ├── analytics.py           ← 20+ fraud dashboard endpoints
│   │       ├── credit.py              ← credit scoring, applicants, loans
│   │       ├── risk_analytics.py      ← FPD, vintage, KS/Gini, PSI, EL
│   │       ├── ab_testing.py          ← A/B tests, power analysis
│   │       ├── cost_analysis.py       ← ROI, savings, scenario simulator
│   │       ├── transactions.py        ← transaction explorer
│   │       ├── predictions.py         ← real-time /score
│   │       ├── review.py              ← human-in-the-loop queue
│   │       ├── training.py            ← trigger pipeline + rechampion
│   │       ├── explainability.py      ← SHAP · LIME · feature importance
│   │       └── pipeline.py            ← ingest CSVs → DB
│   ├── config/settings.py             ← all env config
│   ├── pipeline/
│   │   ├── db.py                      ← fraud detection schema
│   │   ├── credit_db.py               ← credit/risk schema
│   │   ├── dummy_data.py              ← seed 5k applicants + 12k loans
│   │   ├── run_pipeline.py            ← master fraud ML runner
│   │   ├── feature_engineering.py     ← 20+ feature groups
│   │   ├── train.py                   ← FLAML models
│   │   ├── imbalance.py               ← ADASYN · class_weight
│   │   ├── explain.py                 ← SHAP + LIME
│   │   └── mlflow_tracking.py         ← MLflow experiment logging
│   ├── data/
│   │   ├── raw/                       ← train.csv · test.csv · identity.csv
│   │   ├── fraud.db                   ← SQLite (auto-created)
│   │   └── predictions.csv            ← submission output
│   └── .env
│
└── frontend/                          ← Angular 20 SPA (port 4300)
    └── src/app/pages/
        ├── dashboard/                 ← fraud detection overview
        ├── credit-scoring/            ← score distribution, bureau signals
        ├── loan-portfolio/            ← portfolio management
        ├── applicants/                ← applicant profiles with bureau + SEON
        ├── risk-analytics/            ← KS/Gini, PSI drift, EL, roll rates
        ├── fpd-analysis/              ← First Payment Default
        ├── vintage-analysis/          ← vintage curves, cohort roll rates
        ├── ab-testing/                ← champion/challenger experiments
        ├── cost-analysis/             ← ROI, savings waterfall, simulator
        ├── transactions/              ← fraud transaction explorer
        ├── model-comparison/          ← all models × metrics
        ├── model-monitoring/          ← calibration, score dist
        ├── explainability/            ← SHAP · LIME · feature importance
        ├── review-queue/              ← human-in-the-loop
        ├── analytics-3d/              ← 3D risk landscape
        └── training/                  ← pipeline trigger + MLflow
```

---

## Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.11+ |
| Node.js | 18+ |
| npm | 9+ |

---

## Backend Setup

```bash
cd fraud_detection/backend
pip install -r requirements.txt
cp .env.example .env       # edit as needed
```

### Start the API

```bash
uvicorn api.main:app --reload --port 8000 --host 127.0.0.1
```

On first startup, the API will automatically:
1. Initialise the fraud + credit SQLite databases
2. Seed 5,000 applicants and 12,000 loans (if empty)
3. Ingest raw fraud CSVs (if empty)

**API docs:** http://localhost:8000/api/docs

---

## Frontend Setup

```bash
cd fraud_detection/frontend
npm install --legacy-peer-deps
npx ng serve --port 4300          # dev server
# or
npx ng build --configuration development   # build (served by FastAPI)
```

**App:** http://localhost:4300

---

## Demo Login Credentials

| Email | Password | Role |
|-------|----------|------|
| `analyst@creditiq.ai` | `analyst2026` | Risk Analyst |
| `admin@creditiq.ai`   | `admin2026`   | Admin |
| `demo@creditiq.ai`    | `demo`        | Viewer |

---

## Seed Credit Data (manual, if needed)

```bash
cd fraud_detection/backend
python pipeline/dummy_data.py          # seed once
python pipeline/dummy_data.py --force  # force re-seed
```

---

## MLflow UI

```bash
cd fraud_detection/backend
mlflow ui --backend-store-uri sqlite:///data/mlflow.db --port 5000
```

Open: http://localhost:5000

---

## Quick Reference

```bash
# Backend
uvicorn api.main:app --reload --port 8000

# Frontend dev
npx ng serve --port 4300

# Seed credit data
python pipeline/dummy_data.py

# Health check
curl http://localhost:8000/api/health

# Credit summary
curl http://localhost:8000/api/credit/summary

# A/B tests
curl http://localhost:8000/api/ab/tests

# Cost summary
curl http://localhost:8000/api/cost/summary
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `No module named 'flaml'` | `pip install flaml` |
| Pipeline error stage 3 | Check `data/raw/` has train.csv, test.csv, identity.csv |
| No champion model | Run pipeline from the ML Pipeline tab |
| 401 on all API calls | Login at /login — cookie-based session |
| Credit data empty | Run `python pipeline/dummy_data.py` |
| Port 4300 in use | Kill existing process or use different port |
| Frontend shows blank | Backend must be running on port 8000 |
