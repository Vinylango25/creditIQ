"""
/api/cost — Cost Analysis & Model ROI
Simulates financial impact: credit losses, fraud losses, ops cost,
model savings, ROI, and false positive opportunity cost.
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import APIRouter, Query
from sqlalchemy import func, desc

from pipeline.db import Session
from pipeline.credit_db import CostAnalysisReport, Loan, Applicant

router = APIRouter()


# ── 1. Aggregate Executive Summary ───────────────────────────────────────────

@router.get("/summary")
def get_cost_summary():
    session = Session()
    try:
        rows = session.query(CostAnalysisReport).order_by(CostAnalysisReport.report_period).all()
        if not rows:
            return {"error": "No cost analysis data — run the seed script first"}

        total_baseline_loss   = sum(r.baseline_total_cost_kes or 0 for r in rows)
        total_model_cost      = sum(r.model_total_cost_kes   or 0 for r in rows)
        total_saved           = sum(r.total_saved_kes         or 0 for r in rows)
        total_credit_saved    = sum(r.credit_loss_saved_kes   or 0 for r in rows)
        total_fraud_saved     = sum(r.fraud_loss_saved_kes    or 0 for r in rows)
        total_ops_saved       = sum(r.ops_cost_saved_kes      or 0 for r in rows)
        total_model_infra     = sum(r.model_cost_kes          or 0 for r in rows)
        total_net_benefit     = sum(r.net_benefit_kes         or 0 for r in rows)
        total_fp_cost         = sum(r.fp_opportunity_cost_kes or 0 for r in rows)
        total_disbursed       = sum(r.total_disbursed_kes     or 0 for r in rows)

        avg_roi = round(total_net_benefit / max(total_model_infra, 1) * 100, 2)
        latest  = rows[-1]

        return {
            # Lifetime totals (KES)
            "total_disbursed_kes":        round(total_disbursed, 0),
            "total_baseline_cost_kes":    round(total_baseline_loss, 0),
            "total_model_cost_kes":       round(total_model_cost, 0),
            "total_saved_kes":            round(total_saved, 0),
            "total_credit_saved_kes":     round(total_credit_saved, 0),
            "total_fraud_saved_kes":      round(total_fraud_saved, 0),
            "total_ops_saved_kes":        round(total_ops_saved, 0),
            "total_model_infra_kes":      round(total_model_infra, 0),
            "total_net_benefit_kes":      round(total_net_benefit, 0),
            "total_fp_cost_kes":          round(total_fp_cost, 0),
            "lifetime_roi_pct":           avg_roi,
            # Latest period snapshot
            "latest_period":              latest.report_period,
            "latest_default_rate_model":  latest.model_default_rate,
            "latest_default_rate_base":   latest.baseline_default_rate,
            "latest_savings_kes":         round(latest.total_saved_kes or 0, 0),
            "latest_roi_pct":             round(latest.roi_pct or 0, 2),
            "periods_analysed":           len(rows),
        }
    finally:
        session.close()


# ── 2. Period-by-Period Table ─────────────────────────────────────────────────

@router.get("/by-period")
def get_cost_by_period():
    session = Session()
    try:
        rows = session.query(CostAnalysisReport).order_by(CostAnalysisReport.report_period).all()
        return [
            {
                "period":                    r.report_period,
                "total_applications":        r.total_applications,
                "approved_loans":            r.approved_loans,
                "approval_rate":             round(r.approval_rate or 0, 4),
                "total_disbursed_kes":       round(r.total_disbursed_kes or 0, 0),
                # Baseline
                "baseline_default_rate":     round(r.baseline_default_rate or 0, 4),
                "baseline_defaults":         r.baseline_default_count,
                "baseline_loss_kes":         round(r.baseline_loss_kes or 0, 0),
                "baseline_fraud_loss_kes":   round(r.baseline_fraud_loss_kes or 0, 0),
                "baseline_ops_kes":          round(r.baseline_ops_cost_kes or 0, 0),
                "baseline_total_kes":        round(r.baseline_total_cost_kes or 0, 0),
                # Model
                "model_default_rate":        round(r.model_default_rate or 0, 4),
                "model_defaults":            r.model_default_count,
                "model_loss_kes":            round(r.model_loss_kes or 0, 0),
                "model_fraud_loss_kes":      round(r.model_fraud_loss_kes or 0, 0),
                "model_ops_kes":             round(r.model_ops_cost_kes or 0, 0),
                "model_total_kes":           round(r.model_total_cost_kes or 0, 0),
                # Savings
                "credit_saved_kes":          round(r.credit_loss_saved_kes or 0, 0),
                "fraud_saved_kes":           round(r.fraud_loss_saved_kes or 0, 0),
                "ops_saved_kes":             round(r.ops_cost_saved_kes or 0, 0),
                "total_saved_kes":           round(r.total_saved_kes or 0, 0),
                # ROI
                "model_infra_kes":           round(r.model_cost_kes or 0, 0),
                "net_benefit_kes":           round(r.net_benefit_kes or 0, 0),
                "roi_pct":                   round(r.roi_pct or 0, 2),
                # FP cost
                "false_positives":           r.false_positives,
                "fp_opp_cost_kes":           round(r.fp_opportunity_cost_kes or 0, 0),
            }
            for r in rows
        ]
    finally:
        session.close()


# ── 3. Savings Waterfall ─────────────────────────────────────────────────────

@router.get("/savings-waterfall")
def get_savings_waterfall():
    """Waterfall chart data: baseline cost → savings categories → net model cost → net benefit."""
    session = Session()
    try:
        rows = session.query(CostAnalysisReport).order_by(CostAnalysisReport.report_period).all()
        if not rows:
            return {"items": []}

        baseline  = round(sum(r.baseline_total_cost_kes or 0 for r in rows), 0)
        c_saved   = round(sum(r.credit_loss_saved_kes   or 0 for r in rows), 0)
        f_saved   = round(sum(r.fraud_loss_saved_kes    or 0 for r in rows), 0)
        o_saved   = round(sum(r.ops_cost_saved_kes      or 0 for r in rows), 0)
        infra     = round(sum(r.model_cost_kes           or 0 for r in rows), 0)
        net       = round(sum(r.net_benefit_kes          or 0 for r in rows), 0)
        fp_cost   = round(sum(r.fp_opportunity_cost_kes  or 0 for r in rows), 0)

        return {
            "items": [
                {"label": "Baseline Total Cost",       "value":  baseline, "type": "total"},
                {"label": "Credit Loss Reduction",     "value": -c_saved,  "type": "saving"},
                {"label": "Fraud Loss Reduction",      "value": -f_saved,  "type": "saving"},
                {"label": "Ops Cost Reduction",        "value": -o_saved,  "type": "saving"},
                {"label": "Model Infrastructure Cost", "value":  infra,    "type": "cost"},
                {"label": "FP Opportunity Cost",       "value":  fp_cost,  "type": "cost"},
                {"label": "Net Benefit",               "value":  net,      "type": "net"},
            ],
            "baseline_kes": baseline,
            "total_saved_kes": c_saved + f_saved + o_saved,
            "net_benefit_kes": net,
        }
    finally:
        session.close()


# ── 4. ROI Over Time ─────────────────────────────────────────────────────────

@router.get("/roi-trend")
def get_roi_trend():
    session = Session()
    try:
        rows = session.query(CostAnalysisReport).order_by(CostAnalysisReport.report_period).all()
        return {
            "periods":          [r.report_period for r in rows],
            "roi_pct":          [round(r.roi_pct or 0, 2) for r in rows],
            "net_benefit_kes":  [round(r.net_benefit_kes or 0, 0) for r in rows],
            "total_saved_kes":  [round(r.total_saved_kes or 0, 0) for r in rows],
            "model_cost_kes":   [round(r.model_cost_kes or 0, 0) for r in rows],
            "default_rate_baseline": [round(r.baseline_default_rate or 0, 4) for r in rows],
            "default_rate_model":    [round(r.model_default_rate or 0, 4) for r in rows],
        }
    finally:
        session.close()


# ── 5. Cost Breakdown Donut ────────────────────────────────────────────────────

@router.get("/cost-breakdown")
def get_cost_breakdown():
    """Pie breakdown: what % of total baseline loss is credit vs fraud vs ops."""
    session = Session()
    try:
        rows = session.query(CostAnalysisReport).all()
        if not rows:
            return {"baseline": [], "model": []}

        b_credit = sum(r.baseline_loss_kes or 0 for r in rows)
        b_fraud  = sum(r.baseline_fraud_loss_kes or 0 for r in rows)
        b_ops    = sum(r.baseline_ops_cost_kes or 0 for r in rows)

        m_credit = sum(r.model_loss_kes or 0 for r in rows)
        m_fraud  = sum(r.model_fraud_loss_kes or 0 for r in rows)
        m_ops    = sum(r.model_ops_cost_kes or 0 for r in rows)
        m_infra  = sum(r.model_cost_kes or 0 for r in rows)

        return {
            "baseline": [
                {"name": "Credit Losses",  "value": round(b_credit, 0)},
                {"name": "Fraud Losses",   "value": round(b_fraud, 0)},
                {"name": "Ops Cost",       "value": round(b_ops, 0)},
            ],
            "model": [
                {"name": "Credit Losses",        "value": round(m_credit, 0)},
                {"name": "Fraud Losses",         "value": round(m_fraud, 0)},
                {"name": "Ops Cost",             "value": round(m_ops, 0)},
                {"name": "Model Infra",          "value": round(m_infra, 0)},
            ],
        }
    finally:
        session.close()


# ── 6. Scenario Simulator ─────────────────────────────────────────────────────

@router.get("/scenario")
def simulate_scenario(
    monthly_loans:       int   = Query(1000, description="Loans per month"),
    avg_loan_kes:        float = Query(8500, description="Average loan amount KES"),
    baseline_dr:         float = Query(0.18, description="Baseline default rate"),
    model_dr:            float = Query(0.095, description="Model default rate"),
    lgd:                 float = Query(0.55, description="Loss Given Default"),
    fraud_pct_of_default:float = Query(0.22, description="Fraud as % of defaults"),
    model_cost_per_loan: float = Query(2.50, description="Model cost per loan (KES)"),
    manual_review_pct:   float = Query(0.15, description="% of loans needing manual review"),
    review_cost_kes:     float = Query(262.5, description="Cost per manual review (KES)"),
):
    """
    What-if scenario simulator — adjust assumptions to see projected savings.
    All figures are per-month.
    """
    disbursed = monthly_loans * avg_loan_kes

    # Baseline
    b_defaults     = int(monthly_loans * baseline_dr)
    b_credit_loss  = round(b_defaults * avg_loan_kes * lgd, 2)
    b_fraud_count  = int(b_defaults * fraud_pct_of_default)
    b_fraud_loss   = round(b_fraud_count * avg_loan_kes * 0.85, 2)
    b_review_hrs   = round(monthly_loans * 0.75, 1)
    b_ops          = round(b_review_hrs * 350, 2)
    b_total        = round(b_credit_loss + b_fraud_loss + b_ops, 2)

    # Model
    m_defaults     = int(monthly_loans * model_dr)
    m_credit_loss  = round(m_defaults * avg_loan_kes * lgd, 2)
    m_fraud_count  = int(m_defaults * 0.08)
    m_fraud_loss   = round(m_fraud_count * avg_loan_kes * 0.85, 2)
    m_review_hrs   = round(monthly_loans * manual_review_pct * 0.75, 1)
    m_ops          = round(m_review_hrs * 350, 2)
    model_infra    = round(180_000 / 3 + monthly_loans * model_cost_per_loan, 2)
    m_total        = round(m_credit_loss + m_fraud_loss + m_ops + model_infra, 2)

    saved          = round(b_total - m_total, 2)
    net_benefit    = round(saved - model_infra, 2)
    roi            = round(net_benefit / max(model_infra, 1) * 100, 2)

    # Annualised
    annual_saved   = round(saved * 12, 2)
    annual_roi     = roi

    return {
        "inputs": {
            "monthly_loans": monthly_loans,
            "avg_loan_kes":  avg_loan_kes,
            "baseline_dr":   baseline_dr,
            "model_dr":      model_dr,
            "lgd":           lgd,
        },
        "baseline": {
            "defaults":     b_defaults,
            "credit_loss":  b_credit_loss,
            "fraud_count":  b_fraud_count,
            "fraud_loss":   b_fraud_loss,
            "ops_cost":     b_ops,
            "total_cost":   b_total,
        },
        "model": {
            "defaults":     m_defaults,
            "credit_loss":  m_credit_loss,
            "fraud_count":  m_fraud_count,
            "fraud_loss":   m_fraud_loss,
            "ops_cost":     m_ops,
            "infra_cost":   model_infra,
            "total_cost":   m_total,
        },
        "savings": {
            "monthly_saved_kes": saved,
            "annual_saved_kes":  annual_saved,
            "model_cost_kes":    model_infra,
            "net_benefit_kes":   net_benefit,
            "roi_pct":           roi,
            "default_rate_reduction_pct": round((baseline_dr - model_dr) / baseline_dr * 100, 1),
        },
    }
