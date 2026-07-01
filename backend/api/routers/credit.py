"""
/api/credit — Credit Scoring, Applicant Profiles, Loan Portfolio
"""
from __future__ import annotations

import json
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, desc, asc

from pipeline.db import Session
from pipeline.credit_db import Applicant, Loan, CreditScore, FPDRecord

router = APIRouter()


# ── 1. Portfolio KPI Summary ─────────────────────────────────────────────────

@router.get("/summary")
def get_credit_summary():
    session = Session()
    try:
        total_applicants = session.query(Applicant).count()
        total_loans      = session.query(Loan).count()

        # Active loans
        active_loans = session.query(Loan).filter(Loan.status == "active").count()

        # Loan status breakdown
        statuses = session.query(
            Loan.status, func.count(Loan.id).label("cnt")
        ).group_by(Loan.status).all()
        status_map = {s.status: s.cnt for s in statuses}

        # Default rate
        defaulted = status_map.get("default", 0) + status_map.get("written_off", 0)
        default_rate = round(defaulted / max(total_loans, 1), 4)

        # Portfolio balance (KES)
        total_disbursed = session.query(func.sum(Loan.loan_amount)).scalar() or 0
        total_repaid    = session.query(func.sum(Loan.amount_repaid)).scalar() or 0
        outstanding     = total_disbursed - total_repaid

        # Expected loss
        avg_el = session.query(func.avg(Loan.expected_loss)).scalar() or 0
        total_el = session.query(func.sum(Loan.expected_loss)).scalar() or 0

        # Average credit score
        avg_score = session.query(func.avg(Applicant.tu_score)).scalar() or 0

        # FPD rate
        fpd_total = session.query(FPDRecord).count()
        fpd_count = session.query(FPDRecord).filter(FPDRecord.is_fpd == True).count()
        fpd_rate  = round(fpd_count / max(fpd_total, 1), 4)

        # Avg PD
        avg_pd = session.query(func.avg(Loan.pd_score)).scalar() or 0

        return {
            "total_applicants":    total_applicants,
            "total_loans":         total_loans,
            "active_loans":        active_loans,
            "paid_loans":          status_map.get("paid", 0),
            "defaulted_loans":     defaulted,
            "written_off_loans":   status_map.get("written_off", 0),
            "default_rate":        default_rate,
            "default_pct":         round(default_rate * 100, 2),
            "total_disbursed_kes": round(total_disbursed, 2),
            "total_repaid_kes":    round(total_repaid, 2),
            "outstanding_kes":     round(outstanding, 2),
            "avg_expected_loss":   round(avg_el, 2),
            "total_expected_loss": round(total_el, 2),
            "avg_credit_score":    round(avg_score, 1),
            "fpd_rate":            fpd_rate,
            "fpd_pct":             round(fpd_rate * 100, 2),
            "avg_pd":              round(avg_pd, 4),
        }
    finally:
        session.close()


# ── 2. Score Distribution ─────────────────────────────────────────────────────

@router.get("/score-distribution")
def get_score_distribution():
    session = Session()
    try:
        rows = session.query(Applicant.tu_score).filter(Applicant.tu_score.isnot(None)).all()
        if not rows:
            return {"bands": [], "counts": []}

        bands = {
            "Very Poor (300-599)": 0,
            "Poor (600-649)": 0,
            "Fair (650-699)": 0,
            "Good (700-749)": 0,
            "Excellent (750-850)": 0,
        }
        for (score,) in rows:
            if score < 600:   bands["Very Poor (300-599)"] += 1
            elif score < 650: bands["Poor (600-649)"] += 1
            elif score < 700: bands["Fair (650-699)"] += 1
            elif score < 750: bands["Good (700-749)"] += 1
            else:             bands["Excellent (750-850)"] += 1

        return {
            "bands":  list(bands.keys()),
            "counts": list(bands.values()),
            "total":  len(rows),
        }
    finally:
        session.close()


# ── 3. PD Distribution ────────────────────────────────────────────────────────

@router.get("/pd-distribution")
def get_pd_distribution(bins: int = Query(20, ge=5, le=40)):
    session = Session()
    try:
        import numpy as np
        rows = session.query(Loan.pd_score).filter(Loan.pd_score.isnot(None)).all()
        if not rows:
            return {"bins": [], "counts": []}
        pds = [r[0] for r in rows]
        counts, edges = np.histogram(pds, bins=bins, range=(0, 1))
        labels = [f"{edges[i]:.2f}–{edges[i+1]:.2f}" for i in range(len(edges) - 1)]
        return {"bins": labels, "counts": counts.tolist()}
    finally:
        session.close()


# ── 4. Loan Portfolio by Product ─────────────────────────────────────────────

@router.get("/portfolio-by-product")
def get_portfolio_by_product():
    session = Session()
    try:
        rows = session.query(
            Loan.product_type,
            func.count(Loan.id).label("total"),
            func.sum(Loan.loan_amount).label("disbursed"),
            func.avg(Loan.pd_score).label("avg_pd"),
            func.avg(Loan.credit_score_at_orig).label("avg_score"),
        ).group_by(Loan.product_type).all()

        defaults_by_product = session.query(
            Loan.product_type,
            func.count(Loan.id).label("defaults"),
        ).filter(Loan.status.in_(["default", "written_off"]))\
         .group_by(Loan.product_type).all()
        def_map = {r.product_type: r.defaults for r in defaults_by_product}

        return [
            {
                "product":      r.product_type,
                "total_loans":  r.total,
                "disbursed_kes":round(r.disbursed or 0, 2),
                "avg_pd":       round(r.avg_pd or 0, 4),
                "avg_score":    round(r.avg_score or 0, 1),
                "defaults":     def_map.get(r.product_type, 0),
                "default_rate": round(def_map.get(r.product_type, 0) / max(r.total, 1), 4),
            }
            for r in rows
        ]
    finally:
        session.close()


# ── 5. Loan Portfolio by Country ─────────────────────────────────────────────

@router.get("/portfolio-by-country")
def get_portfolio_by_country():
    session = Session()
    try:
        rows = session.query(
            Applicant.country,
            func.count(Loan.id).label("total"),
            func.sum(Loan.loan_amount).label("disbursed"),
            func.avg(Loan.pd_score).label("avg_pd"),
        ).join(Loan, Loan.applicant_id == Applicant.applicant_id)\
         .group_by(Applicant.country).all()

        return [
            {
                "country":      r.country,
                "total_loans":  r.total,
                "disbursed_kes":round(r.disbursed or 0, 2),
                "avg_pd":       round(r.avg_pd or 0, 4),
            }
            for r in rows
        ]
    finally:
        session.close()


# ── 6. Applicants list (paginated) ───────────────────────────────────────────

@router.get("/applicants")
def list_applicants(
    page:       int   = Query(1, ge=1),
    page_size:  int   = Query(20, ge=1, le=100),
    country:    str   = Query(None),
    tu_grade:   str   = Query(None),
    min_score:  int   = Query(None),
    max_score:  int   = Query(None),
    employment: str   = Query(None),
):
    session = Session()
    try:
        q = session.query(Applicant)
        if country:      q = q.filter(Applicant.country == country)
        if tu_grade:     q = q.filter(Applicant.tu_grade == tu_grade)
        if min_score:    q = q.filter(Applicant.tu_score >= min_score)
        if max_score:    q = q.filter(Applicant.tu_score <= max_score)
        if employment:   q = q.filter(Applicant.employment_status == employment)

        total = q.count()
        rows  = q.order_by(desc(Applicant.created_at)).offset((page-1)*page_size).limit(page_size).all()

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "applicants": [
                {
                    "applicant_id":     a.applicant_id,
                    "name":             f"{a.first_name} {a.last_name}",
                    "age":              a.age,
                    "gender":           a.gender,
                    "country":          a.country,
                    "county":           a.county_province,
                    "employment":       a.employment_status,
                    "monthly_income":   a.monthly_income_kes,
                    "tu_score":         a.tu_score,
                    "tu_grade":         a.tu_grade,
                    "credit_utilization": a.credit_utilization,
                    "dti":              a.debt_to_income,
                    "seon_score":       a.seon_fraud_score,
                    "delinquent":       a.delinquent_accounts,
                    "bankruptcy":       a.bankruptcy_flag,
                    "mpesa_avg_in":     a.mpesa_monthly_avg_in,
                }
                for a in rows
            ]
        }
    finally:
        session.close()


# ── 7. Single Applicant Detail ────────────────────────────────────────────────

@router.get("/applicants/{applicant_id}")
def get_applicant(applicant_id: str):
    session = Session()
    try:
        a = session.query(Applicant).filter_by(applicant_id=applicant_id).first()
        if not a:
            raise HTTPException(status_code=404, detail="Applicant not found")

        loans = session.query(Loan).filter_by(applicant_id=applicant_id)\
                       .order_by(desc(Loan.created_at)).all()
        scores = session.query(CreditScore).filter_by(applicant_id=applicant_id)\
                        .order_by(desc(CreditScore.scored_at)).all()

        return {
            "applicant_id":            a.applicant_id,
            "name":                    f"{a.first_name} {a.last_name}",
            "national_id":             a.national_id,
            "phone":                   a.phone_number,
            "email":                   a.email,
            "age":                     a.age,
            "gender":                  a.gender,
            "country":                 a.country,
            "county":                  a.county_province,
            "employment_status":       a.employment_status,
            "employer":                a.employer_name,
            "monthly_income_kes":      a.monthly_income_kes,
            "monthly_expenses_kes":    a.monthly_expenses_kes,
            # Bureau
            "tu_score":                a.tu_score,
            "tu_grade":                a.tu_grade,
            "total_accounts":          a.total_accounts,
            "open_accounts":           a.open_accounts,
            "delinquent_accounts":     a.delinquent_accounts,
            "credit_utilization":      a.credit_utilization,
            "total_outstanding_debt":  a.total_outstanding_debt,
            "total_credit_limit":      a.total_credit_limit,
            "months_credit_history":   a.months_credit_history,
            "months_since_last_delinquency": a.months_since_last_delinquency,
            "num_hard_inquiries_12m":  a.num_hard_inquiries_12m,
            "bankruptcy_flag":         a.bankruptcy_flag,
            "judgement_flag":          a.judgement_flag,
            "active_collections":      a.active_collections,
            "debt_to_income":          a.debt_to_income,
            # SEON
            "seon_fraud_score":        a.seon_fraud_score,
            "seon_email_deliverable":  a.seon_email_deliverable,
            "seon_phone_valid":        a.seon_phone_valid,
            "seon_social_match_count": a.seon_social_match_count,
            "seon_ip_risk_level":      a.seon_ip_risk_level,
            "seon_is_vpn":             a.seon_is_vpn,
            "seon_is_tor":             a.seon_is_tor,
            # Mobile
            "mobile_wallet_age_months":a.mobile_wallet_age_months,
            "mpesa_monthly_avg_in":    a.mpesa_monthly_avg_in,
            "mpesa_monthly_avg_out":   a.mpesa_monthly_avg_out,
            "mpesa_loan_history_count":a.mpesa_loan_history_count,
            "sim_age_months":          a.sim_age_months,
            # Loans
            "loans": [
                {
                    "loan_id":          l.loan_id,
                    "product":          l.product_type,
                    "amount":           l.loan_amount,
                    "currency":         l.currency,
                    "status":           l.status,
                    "disbursement_date":str(l.disbursement_date),
                    "due_date":         str(l.due_date),
                    "pd_score":         l.pd_score,
                    "days_past_due":    l.days_past_due,
                }
                for l in loans
            ],
            # Latest score
            "latest_score": {
                "score":     scores[0].score if scores else None,
                "band":      scores[0].score_band if scores else None,
                "pd":        scores[0].pd_estimate if scores else None,
                "woe":       json.loads(scores[0].woe_breakdown or "{}") if scores else {},
            } if scores else None,
        }
    finally:
        session.close()


# ── 8. Credit Score Heatmap (age × score band) ───────────────────────────────

@router.get("/score-heatmap")
def get_score_heatmap():
    """Score distribution by age group × employment status."""
    session = Session()
    try:
        rows = session.query(
            Applicant.age,
            Applicant.employment_status,
            Applicant.tu_score,
        ).filter(
            Applicant.age.isnot(None),
            Applicant.tu_score.isnot(None),
        ).all()

        if not rows:
            return {"age_groups": [], "employment": [], "matrix": []}

        from collections import defaultdict
        import numpy as np

        age_bins = ["18-25","26-30","31-35","36-40","41-50","51-65"]
        emp_types = ["employed","self_employed","unemployed"]

        def age_grp(a):
            if a <= 25:  return "18-25"
            if a <= 30:  return "26-30"
            if a <= 35:  return "31-35"
            if a <= 40:  return "36-40"
            if a <= 50:  return "41-50"
            return "51-65"

        matrix_scores: dict = defaultdict(list)
        for age, emp, score in rows:
            ag  = age_grp(age)
            emp = emp or "employed"
            if emp not in emp_types:
                emp = "employed"
            matrix_scores[(ag, emp)].append(score)

        matrix = []
        for ai, ag in enumerate(age_bins):
            for ei, emp in enumerate(emp_types):
                vals = matrix_scores.get((ag, emp), [])
                avg  = round(float(np.mean(vals)), 1) if vals else 0.0
                matrix.append({
                    "age_group": ag, "age_idx": ai,
                    "employment": emp, "emp_idx": ei,
                    "avg_score": avg, "count": len(vals),
                })

        return {"age_groups": age_bins, "employment": emp_types, "matrix": matrix}
    finally:
        session.close()


# ── 9. Bureau Signal Breakdown ────────────────────────────────────────────────

@router.get("/bureau-signals")
def get_bureau_signals():
    """Aggregated bureau data: utilization, DTI, inquiry distributions."""
    session = Session()
    try:
        rows = session.query(
            Applicant.credit_utilization,
            Applicant.debt_to_income,
            Applicant.num_hard_inquiries_12m,
            Applicant.months_credit_history,
            Applicant.delinquent_accounts,
        ).filter(Applicant.tu_score.isnot(None)).limit(5000).all()

        if not rows:
            return {}

        import numpy as np
        utils   = [r[0] for r in rows if r[0] is not None]
        dtis    = [r[1] for r in rows if r[1] is not None]
        inqs    = [r[2] for r in rows if r[2] is not None]
        mob_his = [r[3] for r in rows if r[3] is not None]
        delinqs = [r[4] for r in rows if r[4] is not None]

        def _hist(data, bins, range_):
            counts, edges = np.histogram(data, bins=bins, range=range_)
            labels = [f"{edges[i]:.2f}–{edges[i+1]:.2f}" for i in range(len(edges)-1)]
            return {"labels": labels, "counts": counts.tolist()}

        return {
            "utilization":       _hist(utils,   10, (0, 1)),
            "dti":               _hist(dtis,    10, (0, 2)),
            "hard_inquiries":    _hist(inqs,    9,  (0, 9)),
            "credit_history_months": _hist(mob_his, 12, (0, 240)),
            "delinquent_accounts": {
                "labels": ["0","1","2","3+"],
                "counts": [
                    sum(1 for d in delinqs if d == 0),
                    sum(1 for d in delinqs if d == 1),
                    sum(1 for d in delinqs if d == 2),
                    sum(1 for d in delinqs if d >= 3),
                ]
            },
        }
    finally:
        session.close()


# ── 10. Loans list (paginated) ────────────────────────────────────────────────

@router.get("/loans")
def list_loans(
    page:         int   = Query(1, ge=1),
    page_size:    int   = Query(20, ge=1, le=100),
    status:       str   = Query(None),
    product_type: str   = Query(None),
    cohort:       str   = Query(None),
):
    session = Session()
    try:
        q = session.query(Loan)
        if status:        q = q.filter(Loan.status == status)
        if product_type:  q = q.filter(Loan.product_type == product_type)
        if cohort:        q = q.filter(Loan.cohort == cohort)

        total = q.count()
        rows  = q.order_by(desc(Loan.created_at)).offset((page-1)*page_size).limit(page_size).all()

        return {
            "total": total, "page": page, "page_size": page_size,
            "loans": [
                {
                    "loan_id":       l.loan_id,
                    "applicant_id":  l.applicant_id,
                    "product":       l.product_type,
                    "amount":        l.loan_amount,
                    "currency":      l.currency,
                    "status":        l.status,
                    "disbursement":  str(l.disbursement_date),
                    "due_date":      str(l.due_date),
                    "dpd":           l.days_past_due,
                    "pd":            l.pd_score,
                    "lgd":           l.lgd_score,
                    "el":            l.expected_loss,
                    "score":         l.credit_score_at_orig,
                    "cohort":        l.cohort,
                    "fraud_flag":    l.fraud_flag,
                }
                for l in rows
            ]
        }
    finally:
        session.close()
