"""
/api/risk — Risk Analytics: FPD, Vintage, Roll Rates, KS/Gini, PSI, Portfolio Risk
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import APIRouter, Query
from sqlalchemy import func, desc

from pipeline.db import Session
from pipeline.credit_db import Loan, FPDRecord, CohortSnapshot, DriftReport, Applicant

router = APIRouter()


# ── 1. FPD Summary ────────────────────────────────────────────────────────────

@router.get("/fpd/summary")
def get_fpd_summary():
    session = Session()
    try:
        total     = session.query(FPDRecord).count()
        fpd_yes   = session.query(FPDRecord).filter(FPDRecord.is_fpd == True).count()
        fpd_rate  = round(fpd_yes / max(total, 1), 4)

        by_bucket = session.query(
            FPDRecord.fpd_bucket,
            func.count(FPDRecord.id).label("cnt"),
        ).filter(FPDRecord.is_fpd == True)\
         .group_by(FPDRecord.fpd_bucket).all()

        by_product = session.query(
            FPDRecord.product_type,
            func.count(FPDRecord.id).label("total"),
        ).group_by(FPDRecord.product_type).all()

        return {
            "total_records": total,
            "fpd_count":     fpd_yes,
            "fpd_rate":      fpd_rate,
            "fpd_pct":       round(fpd_rate * 100, 2),
            "by_bucket":     {r.fpd_bucket: r.cnt for r in by_bucket if r.fpd_bucket},
            "by_product":    [
                {
                    "product": r.product_type,
                    "total":   r.total,
                }
                for r in by_product
            ],
        }
    finally:
        session.close()


# ── 2. FPD Trend (by cohort) ─────────────────────────────────────────────────

@router.get("/fpd/trend")
def get_fpd_trend():
    """FPD rate by cohort (quarterly)."""
    session = Session()
    try:
        rows = session.query(
            FPDRecord.cohort,
            func.count(FPDRecord.id).label("total"),
        ).group_by(FPDRecord.cohort).all()

        fpd_rows = session.query(
            FPDRecord.cohort,
            func.count(FPDRecord.id).label("fpd"),
        ).filter(FPDRecord.is_fpd == True)\
         .group_by(FPDRecord.cohort).all()

        fpd_map = {r.cohort: r.fpd for r in fpd_rows}
        total_map = {r.cohort: r.total for r in rows}

        cohorts = sorted(total_map.keys())
        return {
            "cohorts": cohorts,
            "fpd_rates": [
                round(fpd_map.get(c, 0) / max(total_map.get(c, 1), 1) * 100, 2)
                for c in cohorts
            ],
            "volumes": [total_map.get(c, 0) for c in cohorts],
        }
    finally:
        session.close()


# ── 3. FPD by Score Band ─────────────────────────────────────────────────────

@router.get("/fpd/by-score-band")
def get_fpd_by_score_band():
    session = Session()
    try:
        rows = session.query(FPDRecord).filter(FPDRecord.credit_score.isnot(None)).all()

        bands = {
            "Very Poor (<600)":  {"total": 0, "fpd": 0},
            "Poor (600-649)":    {"total": 0, "fpd": 0},
            "Fair (650-699)":    {"total": 0, "fpd": 0},
            "Good (700-749)":    {"total": 0, "fpd": 0},
            "Excellent (750+)":  {"total": 0, "fpd": 0},
        }
        for r in rows:
            s = r.credit_score
            if s < 600:   k = "Very Poor (<600)"
            elif s < 650: k = "Poor (600-649)"
            elif s < 700: k = "Fair (650-699)"
            elif s < 750: k = "Good (700-749)"
            else:         k = "Excellent (750+)"
            bands[k]["total"] += 1
            if r.is_fpd:
                bands[k]["fpd"] += 1

        return [
            {
                "band":      band,
                "total":     v["total"],
                "fpd_count": v["fpd"],
                "fpd_rate":  round(v["fpd"] / max(v["total"], 1), 4),
            }
            for band, v in bands.items()
        ]
    finally:
        session.close()


# ── 4. Vintage Curves ─────────────────────────────────────────────────────────

@router.get("/vintage/curves")
def get_vintage_curves():
    """Cumulative default rate by MOB (months on book) per cohort."""
    session = Session()
    try:
        rows = session.query(CohortSnapshot)\
                      .order_by(CohortSnapshot.cohort, CohortSnapshot.mob).all()
        if not rows:
            return {"cohorts": [], "series": {}}

        from collections import defaultdict
        by_cohort: dict = defaultdict(dict)
        for r in rows:
            by_cohort[r.cohort][r.mob] = round(r.cumulative_default_rate * 100, 2)

        cohorts = sorted(by_cohort.keys())
        max_mob = max(max(d.keys()) for d in by_cohort.values()) if by_cohort else 12
        mobs    = list(range(1, max_mob + 1))

        series = {}
        for cohort in cohorts:
            series[cohort] = [by_cohort[cohort].get(m) for m in mobs]

        return {"mobs": mobs, "cohorts": cohorts, "series": series}
    finally:
        session.close()


# ── 5. Roll Rate Matrix ───────────────────────────────────────────────────────

@router.get("/roll-rates")
def get_roll_rates():
    """
    DPD (Days Past Due) roll rate matrix — simulated from loan statuses.
    Buckets: Current (0) → 1-7 DPD → 8-30 DPD → 31-60 DPD → 60+ DPD → Written Off
    """
    session = Session()
    try:
        rows = session.query(Loan.status, Loan.days_past_due).all()

        def _bucket(dpd, status):
            if status == "written_off": return "Written Off"
            if status == "paid":        return "Paid"
            if dpd == 0:                return "Current"
            if dpd <= 7:                return "1-7 DPD"
            if dpd <= 30:               return "8-30 DPD"
            if dpd <= 60:               return "31-60 DPD"
            return "60+ DPD"

        buckets = ["Current","1-7 DPD","8-30 DPD","31-60 DPD","60+ DPD","Written Off","Paid"]
        counts  = {b: 0 for b in buckets}
        for r in rows:
            counts[_bucket(r.days_past_due or 0, r.status)] += 1

        total = sum(counts.values())

        # Simulated forward roll rates (% that roll to next bucket in 30 days)
        roll_matrix = {
            "Current":     {"Current": 0.93, "1-7 DPD": 0.05, "8-30 DPD": 0.02, "31-60 DPD": 0.00},
            "1-7 DPD":     {"Current": 0.60, "1-7 DPD": 0.18, "8-30 DPD": 0.18, "31-60 DPD": 0.04},
            "8-30 DPD":    {"Current": 0.25, "1-7 DPD": 0.10, "8-30 DPD": 0.35, "31-60 DPD": 0.25, "60+ DPD": 0.05},
            "31-60 DPD":   {"Current": 0.10, "8-30 DPD": 0.05, "31-60 DPD": 0.40, "60+ DPD": 0.35, "Written Off": 0.10},
            "60+ DPD":     {"60+ DPD": 0.45, "Written Off": 0.55},
        }

        return {
            "buckets": buckets,
            "counts":  counts,
            "pct":     {b: round(counts[b] / max(total, 1) * 100, 2) for b in buckets},
            "roll_matrix": roll_matrix,
        }
    finally:
        session.close()


# ── 6. KS / Gini by score ─────────────────────────────────────────────────────

@router.get("/ks-gini")
def get_ks_gini():
    """
    KS statistic and Gini coefficient for credit score discrimination.
    Measures how well the score separates defaults from non-defaults.
    """
    session = Session()
    try:
        import numpy as np
        rows = session.query(
            Loan.credit_score_at_orig,
            Loan.status,
        ).filter(Loan.credit_score_at_orig.isnot(None)).all()

        if not rows:
            return {"ks": 0, "gini": 0, "curve": []}

        scores   = np.array([r[0] for r in rows], dtype=float)
        labels   = np.array([1 if r[1] in ("default","written_off") else 0 for r in rows])

        # Sort by score descending
        idx      = np.argsort(-scores)
        scores_s = scores[idx]
        labels_s = labels[idx]

        n_total  = len(labels_s)
        n_bad    = labels_s.sum()
        n_good   = n_total - n_bad

        cum_bad  = np.cumsum(labels_s)   / max(n_bad, 1)
        cum_good = np.cumsum(1 - labels_s) / max(n_good, 1)
        ks       = float(np.max(np.abs(cum_bad - cum_good)))
        # np.trapz renamed to np.trapezoid in numpy 2.0
        _trapz = getattr(np, 'trapezoid', None) or getattr(np, 'trapz', None)
        gini     = float(2 * _trapz(cum_bad, cum_good) - 1)

        # Lorenz / CAP curve — downsample
        step  = max(1, n_total // 50)
        curve = [
            {
                "pct_population": round(float(i / n_total * 100), 1),
                "cum_bad_rate":   round(float(cum_bad[i-1]), 4),
                "cum_good_rate":  round(float(cum_good[i-1]), 4),
            }
            for i in range(step, n_total, step)
        ]

        # Score band discriminatory power
        bands = ["<600","600-649","650-699","700-749","750+"]
        thresholds = [0, 600, 650, 700, 750, 851]
        band_stats = []
        for i in range(len(bands)):
            mask = (scores >= thresholds[i]) & (scores < thresholds[i+1])
            if mask.sum() == 0:
                continue
            dr = round(float(labels[mask].mean()), 4)
            band_stats.append({"band": bands[i], "count": int(mask.sum()), "default_rate": dr})

        return {
            "ks_statistic": round(ks, 4),
            "gini":         round(abs(gini), 4),
            "auc_roc":      round((abs(gini) + 1) / 2, 4),
            "curve":        curve,
            "band_stats":   band_stats,
        }
    finally:
        session.close()


# ── 7. PSI / Drift Monitoring ─────────────────────────────────────────────────

@router.get("/psi-drift")
def get_psi_drift():
    session = Session()
    try:
        rows = session.query(DriftReport).order_by(DriftReport.psi_value.desc()).all()
        return [
            {
                "feature":         r.feature_name,
                "psi":             round(r.psi_value, 4),
                "drift_level":     r.drift_level,
                "baseline_period": r.baseline_period,
                "current_period":  r.current_period,
            }
            for r in rows
        ]
    finally:
        session.close()


# ── 8. Expected Loss by Cohort ────────────────────────────────────────────────

@router.get("/expected-loss")
def get_expected_loss():
    session = Session()
    try:
        rows = session.query(
            Loan.cohort,
            func.count(Loan.id).label("loans"),
            func.sum(Loan.loan_amount).label("disbursed"),
            func.sum(Loan.expected_loss).label("total_el"),
            func.avg(Loan.pd_score).label("avg_pd"),
            func.avg(Loan.lgd_score).label("avg_lgd"),
        ).filter(Loan.cohort.isnot(None))\
         .group_by(Loan.cohort)\
         .order_by(Loan.cohort).all()

        return [
            {
                "cohort":          r.cohort,
                "loans":           r.loans,
                "disbursed_kes":   round(r.disbursed or 0, 2),
                "total_el_kes":    round(r.total_el or 0, 2),
                "el_rate":         round((r.total_el or 0) / max(r.disbursed or 1, 1), 4),
                "avg_pd":          round(r.avg_pd or 0, 4),
                "avg_lgd":         round(r.avg_lgd or 0, 4),
            }
            for r in rows
        ]
    finally:
        session.close()


# ── 9. Risk by Employment / Income ────────────────────────────────────────────

@router.get("/risk-by-segment")
def get_risk_by_segment():
    """Default rate and avg PD broken down by employment status and income tier."""
    session = Session()
    try:
        rows = session.query(
            Applicant.employment_status,
            func.count(Loan.id).label("loans"),
            func.avg(Loan.pd_score).label("avg_pd"),
            func.avg(Applicant.tu_score).label("avg_score"),
        ).join(Loan, Loan.applicant_id == Applicant.applicant_id)\
         .filter(Applicant.employment_status.isnot(None))\
         .group_by(Applicant.employment_status).all()

        defaults_by_emp = session.query(
            Applicant.employment_status,
            func.count(Loan.id).label("defaults"),
        ).join(Loan, Loan.applicant_id == Applicant.applicant_id)\
         .filter(Loan.status.in_(["default","written_off"]))\
         .group_by(Applicant.employment_status).all()
        def_emp_map = {r.employment_status: r.defaults for r in defaults_by_emp}

        total_by_emp = {r.employment_status: r.loans for r in rows}

        return {
            "by_employment": [
                {
                    "segment":      r.employment_status,
                    "loans":        r.loans,
                    "avg_pd":       round(r.avg_pd or 0, 4),
                    "avg_score":    round(r.avg_score or 0, 1),
                    "default_count":def_emp_map.get(r.employment_status, 0),
                    "default_rate": round(
                        def_emp_map.get(r.employment_status, 0) / max(r.loans, 1), 4
                    ),
                }
                for r in rows
            ]
        }
    finally:
        session.close()


# ── 10. Portfolio Summary KPIs Over Time ─────────────────────────────────────

@router.get("/portfolio-trend")
def get_portfolio_trend():
    """Monthly portfolio KPIs — disbursement, default rate, avg score."""
    session = Session()
    try:
        rows = session.query(
            Loan.origination_year_month,
            func.count(Loan.id).label("loans"),
            func.sum(Loan.loan_amount).label("disbursed"),
            func.avg(Loan.pd_score).label("avg_pd"),
            func.avg(Loan.credit_score_at_orig).label("avg_score"),
        ).filter(Loan.origination_year_month.isnot(None))\
         .group_by(Loan.origination_year_month)\
         .order_by(Loan.origination_year_month).all()

        def_by_month = session.query(
            Loan.origination_year_month,
            func.count(Loan.id).label("defaults"),
        ).filter(
            Loan.status.in_(["default","written_off"]),
            Loan.origination_year_month.isnot(None),
        ).group_by(Loan.origination_year_month).all()
        def_map = {r.origination_year_month: r.defaults for r in def_by_month}
        total_map = {r.origination_year_month: r.loans for r in rows}

        months = [r.origination_year_month for r in rows]
        return {
            "months":         months,
            "loan_volumes":   [r.loans for r in rows],
            "disbursed_kes":  [round(r.disbursed or 0, 0) for r in rows],
            "default_rates":  [
                round(def_map.get(m, 0) / max(total_map.get(m, 1), 1) * 100, 2)
                for m in months
            ],
            "avg_pd":         [round(r.avg_pd or 0, 4) for r in rows],
            "avg_scores":     [round(r.avg_score or 0, 1) for r in rows],
        }
    finally:
        session.close()
