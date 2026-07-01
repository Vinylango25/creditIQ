"""
/api/insights — AI-generated contextual commentary on platform metrics.
Reads live data from DB and generates natural-language insights, alerts,
and recommendations without requiring an external LLM API.
All logic is rule-based + statistical — fast and offline.
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import APIRouter
from sqlalchemy import func, desc

from pipeline.db import Session, Transaction, ModelRun, Prediction, ReviewQueueItem
from pipeline.credit_db import (Applicant, Loan, FPDRecord, CohortSnapshot,
                                  DriftReport, CostAnalysisReport)

router = APIRouter()


def _trend(values: list[float]) -> str:
    """Return trend direction from a list of values."""
    if len(values) < 2: return "stable"
    recent = values[-3:] if len(values) >= 3 else values
    diff = recent[-1] - recent[0]
    pct  = diff / max(abs(recent[0]), 0.001)
    if pct >  0.05: return "rising"
    if pct < -0.05: return "falling"
    return "stable"


def _status(value: float, thresholds: dict) -> str:
    """Return good/warning/alert status."""
    if value <= thresholds.get("good", 0):    return "good"
    if value <= thresholds.get("warning", 0): return "warning"
    return "alert"


@router.get("/dashboard")
def get_dashboard_insights():
    """
    Generates a full set of AI insights for the main dashboard.
    Returns structured insights with status, trend, description, and recommendation.
    """
    session = Session()
    try:
        insights = []

        # ── FRAUD INSIGHTS ────────────────────────────────────────────────
        champion = session.query(ModelRun).filter_by(is_champion=True)\
                          .order_by(desc(ModelRun.trained_at)).first()
        total_txns = session.query(Transaction).count()
        fraud_txns = session.query(Transaction).filter(Transaction.is_fraud==1,
                                                        Transaction.split=="train").count()
        fraud_rate = fraud_txns / max(total_txns, 1)
        pending_q  = session.query(ReviewQueueItem).filter_by(status="pending").count()

        if champion:
            recall = champion.recall_fraud or 0
            pr_auc = champion.pr_auc or 0
            auc    = champion.auc_roc or 0
            ks     = champion.ks_statistic or 0

            insights.append({
                "id": "fraud_recall",
                "category": "Fraud Detection",
                "title": "Model Recall (Fraud Catch Rate)",
                "value": f"{recall*100:.1f}%",
                "status": "good" if recall > 0.8 else "warning" if recall > 0.6 else "alert",
                "trend": "stable",
                "icon": "🎯",
                "description": f"The champion model ({champion.classifier_name}) correctly identifies "
                               f"{recall*100:.1f}% of all real fraud cases. "
                               f"{'Excellent detection rate.' if recall > 0.8 else 'Room to improve — consider retraining.' if recall > 0.6 else 'Low recall — many frauds are being missed.'}",
                "recommendation": (
                    "Consider lowering the decision threshold to catch more fraud."
                    if recall < 0.75
                    else "Model is performing well. Monitor for concept drift."
                ),
                "benchmark": "Industry target: >80% recall",
            })

            insights.append({
                "id": "model_pr_auc",
                "category": "Fraud Detection",
                "title": "PR-AUC (Precision-Recall Area)",
                "value": f"{pr_auc:.4f}",
                "status": "good" if pr_auc > 0.5 else "warning" if pr_auc > 0.3 else "alert",
                "trend": "stable",
                "icon": "📐",
                "description": f"PR-AUC of {pr_auc:.4f} measures model quality under class imbalance. "
                               f"A random classifier scores ~{fraud_rate:.3f} (the fraud base rate). "
                               f"Your model achieves {pr_auc/max(fraud_rate,0.001):.1f}× improvement over random.",
                "recommendation": (
                    "Strong model — focus on threshold tuning for operational deployment."
                    if pr_auc > 0.45
                    else "Consider feature engineering or ensemble methods to improve PR-AUC."
                ),
                "benchmark": f"Random baseline: {fraud_rate:.4f}",
            })

            insights.append({
                "id": "ks_statistic",
                "category": "Fraud Detection",
                "title": "KS Statistic",
                "value": f"{ks:.4f}",
                "status": "good" if ks > 0.4 else "warning" if ks > 0.25 else "alert",
                "trend": "stable",
                "icon": "📊",
                "description": f"KS = {ks:.4f} measures the maximum separation between fraud and legitimate score distributions. "
                               f"{'Strong discriminating power.' if ks > 0.4 else 'Moderate discrimination.' if ks > 0.25 else 'Weak separation — scores overlap significantly.'}",
                "recommendation": "KS > 0.4 indicates strong model health." if ks > 0.4
                                  else "Consider adding velocity features or interaction terms to improve KS.",
                "benchmark": "Good: >0.40 | Acceptable: 0.25–0.40 | Poor: <0.25",
            })

        insights.append({
            "id": "fraud_rate",
            "category": "Fraud Detection",
            "title": "Transaction Fraud Rate",
            "value": f"{fraud_rate*100:.2f}%",
            "status": "warning" if fraud_rate > 0.05 else "good",
            "trend": "stable",
            "icon": "🚨",
            "description": f"{fraud_txns:,} of {total_txns:,} transactions confirmed as fraud. "
                           f"{'Above typical mobile payment fraud rates (2–4%).' if fraud_rate > 0.04 else 'Within normal range for mobile payments.'}",
            "recommendation": "Review channel-level fraud rates to identify hot spots."
                              if fraud_rate > 0.04 else "Fraud rate is healthy. Maintain current controls.",
            "benchmark": "Mobile payments: 1–4% | Alert: >5%",
        })

        if pending_q > 0:
            insights.append({
                "id": "review_queue",
                "category": "Operations",
                "title": "Review Queue Backlog",
                "value": str(pending_q),
                "status": "alert" if pending_q > 500 else "warning" if pending_q > 100 else "good",
                "trend": "stable",
                "icon": "⚡",
                "description": f"{pending_q} transactions are in the uncertain zone (score 0.3–0.7) awaiting analyst review. "
                               f"{'Critical backlog — analyst capacity needed.' if pending_q > 500 else 'Manageable queue.' if pending_q <= 100 else 'Growing queue — consider threshold adjustment.'}",
                "recommendation": "Consider batch-reviewing low-priority items or adjusting thresholds to reduce queue size."
                                  if pending_q > 200 else "Queue is under control.",
                "benchmark": "Target: <100 pending | Alert: >500",
            })

        # ── CREDIT INSIGHTS ───────────────────────────────────────────────
        total_loans   = session.query(Loan).count()
        default_loans = session.query(Loan).filter(Loan.status.in_(["default","written_off"])).count()
        active_loans  = session.query(Loan).filter_by(status="active").count()
        total_disb    = session.query(func.sum(Loan.loan_amount)).scalar() or 0
        total_el      = session.query(func.sum(Loan.expected_loss)).scalar() or 0
        avg_score     = session.query(func.avg(Applicant.tu_score)).scalar() or 0
        default_rate  = default_loans / max(total_loans, 1)

        fpd_total = session.query(FPDRecord).count()
        fpd_yes   = session.query(FPDRecord).filter_by(is_fpd=True).count()
        fpd_rate  = fpd_yes / max(fpd_total, 1)

        el_rate = total_el / max(total_disb, 1)

        insights.append({
            "id": "default_rate",
            "category": "Credit Risk",
            "title": "Portfolio Default Rate",
            "value": f"{default_rate*100:.2f}%",
            "status": "good" if default_rate < 0.08 else "warning" if default_rate < 0.15 else "alert",
            "trend": "stable",
            "icon": "📉",
            "description": f"{default_loans:,} of {total_loans:,} loans have defaulted or been written off. "
                           f"{'Well within acceptable range for mobile lending.' if default_rate < 0.08 else 'Elevated — review underwriting criteria.' if default_rate < 0.15 else 'Critical — significant portfolio deterioration.'}",
            "recommendation": (
                "Review scoring cutoffs and consider tightening for high-risk segments."
                if default_rate > 0.10
                else "Default rate is healthy. Focus on growth."
            ),
            "benchmark": "Mobile lending: <10% target | Alert: >15%",
        })

        insights.append({
            "id": "fpd_rate",
            "category": "Credit Risk",
            "title": "First Payment Default (FPD)",
            "value": f"{fpd_rate*100:.2f}%",
            "status": "good" if fpd_rate < 0.05 else "warning" if fpd_rate < 0.10 else "alert",
            "trend": "stable",
            "icon": "⚡",
            "description": f"{fpd_yes:,} borrowers missed their very first payment ({fpd_rate*100:.1f}%). "
                           f"FPD is the strongest early indicator of intentional fraud or severe mis-selling. "
                           f"{'Target achieved.' if fpd_rate < 0.05 else 'Above target — review approval criteria.' if fpd_rate < 0.10 else 'Critical — possible systemic fraud or product mis-selling.'}",
            "recommendation": (
                "Investigate FPD borrowers for fraud patterns — check SEON score correlation."
                if fpd_rate > 0.07
                else "FPD is within target. Monitor cohort trends."
            ),
            "benchmark": "Industry target: <5% | Alert: >10%",
        })

        insights.append({
            "id": "credit_score",
            "category": "Credit Risk",
            "title": "Portfolio Average Credit Score",
            "value": f"{avg_score:.0f}",
            "status": "good" if avg_score > 680 else "warning" if avg_score > 620 else "alert",
            "trend": "stable",
            "icon": "🏅",
            "description": f"Average bureau score of {avg_score:.0f} (range 300–850). "
                           f"{'High-quality portfolio — mostly prime borrowers.' if avg_score > 700 else 'Near-prime portfolio — moderate risk.' if avg_score > 640 else 'Sub-prime heavy — elevated risk profile.'}",
            "recommendation": (
                "Consider product-level score floors to maintain portfolio quality."
                if avg_score < 650
                else "Portfolio quality is good. Consider expanding to slightly lower scores with tighter terms."
            ),
            "benchmark": "Prime: 700+ | Near-prime: 640–699 | Sub-prime: <640",
        })

        insights.append({
            "id": "expected_loss",
            "category": "Credit Risk",
            "title": "Expected Loss Rate",
            "value": f"{el_rate*100:.2f}%",
            "status": "good" if el_rate < 0.04 else "warning" if el_rate < 0.08 else "alert",
            "trend": "stable",
            "icon": "💸",
            "description": f"Expected Loss = PD × LGD × EAD = {el_rate*100:.2f}% of disbursed portfolio. "
                           f"Total EL: KES {total_el:,.0f} against KES {total_disb:,.0f} disbursed. "
                           f"This is the regulatory capital proxy — {'well provisioned.' if el_rate < 0.04 else 'provision buffer recommended.' if el_rate < 0.08 else 'significant provisioning required.'}",
            "recommendation": (
                f"Provision at least KES {total_el*1.2:,.0f} (120% of EL) as loan loss reserve."
                if el_rate > 0.04
                else "Current EL is low. Maintain adequate IFRS 9 provisioning."
            ),
            "benchmark": "Well-provisioned: <4% EL | Alert: >8%",
        })

        # ── PSI DRIFT INSIGHTS ────────────────────────────────────────────
        drift_alerts = session.query(DriftReport)\
                               .filter(DriftReport.psi_value >= 0.25)\
                               .order_by(desc(DriftReport.psi_value)).limit(3).all()
        drift_warnings = session.query(DriftReport)\
                                 .filter(DriftReport.psi_value >= 0.10,
                                         DriftReport.psi_value < 0.25).count()

        if drift_alerts:
            feature_names = ", ".join(r.feature_name for r in drift_alerts[:2])
            insights.append({
                "id": "psi_drift",
                "category": "Model Monitoring",
                "title": "Feature Distribution Drift (PSI)",
                "value": f"{len(drift_alerts)} alert(s)",
                "status": "alert",
                "trend": "rising",
                "icon": "📡",
                "description": f"{len(drift_alerts)} feature(s) show significant population shift: {feature_names}. "
                               f"PSI > 0.25 indicates the model was trained on a different population than it's currently scoring. "
                               f"Predictions may be unreliable for these features.",
                "recommendation": "Schedule model retraining with recent data. "
                                  "Temporarily widen confidence intervals on affected features.",
                "benchmark": "PSI <0.10: stable | 0.10–0.25: warning | >0.25: retrain needed",
            })
        elif drift_warnings > 0:
            insights.append({
                "id": "psi_drift",
                "category": "Model Monitoring",
                "title": "Feature Distribution Drift (PSI)",
                "value": f"{drift_warnings} warning(s)",
                "status": "warning",
                "trend": "rising",
                "icon": "📡",
                "description": f"{drift_warnings} feature(s) show early drift signs (PSI 0.10–0.25). "
                               f"Monitor closely — schedule retraining if trend continues.",
                "recommendation": "Increase monitoring frequency. Consider online learning or model refresh.",
                "benchmark": "PSI <0.10: stable | 0.10–0.25: warning | >0.25: retrain needed",
            })

        # ── COST / ROI INSIGHTS ───────────────────────────────────────────
        cost_reports = session.query(CostAnalysisReport)\
                               .order_by(CostAnalysisReport.report_period).all()
        if cost_reports:
            latest     = cost_reports[-1]
            total_saved = sum(r.total_saved_kes or 0 for r in cost_reports)
            avg_roi     = sum(r.roi_pct or 0 for r in cost_reports) / len(cost_reports)

            insights.append({
                "id": "model_roi",
                "category": "Business Value",
                "title": "Model Return on Investment",
                "value": f"{avg_roi:.0f}%",
                "status": "good" if avg_roi > 200 else "warning" if avg_roi > 50 else "alert",
                "trend": "rising",
                "icon": "📈",
                "description": f"The credit+fraud model generates {avg_roi:.0f}% ROI against infrastructure costs. "
                               f"Total lifetime savings: KES {total_saved:,.0f} vs baseline (approve-all). "
                               f"{'Exceptional value delivery.' if avg_roi > 300 else 'Strong positive ROI.' if avg_roi > 100 else 'Positive but could be optimised.'}",
                "recommendation": (
                    "Document ROI to justify model infrastructure investment to stakeholders."
                    if avg_roi > 200
                    else "Review model cost allocation — high infra cost is limiting ROI."
                ),
                "benchmark": "Excellent: >300% | Good: 100–300% | Marginal: <100%",
            })

            if latest.model_default_rate and latest.baseline_default_rate:
                reduction = (1 - latest.model_default_rate / latest.baseline_default_rate) * 100
                insights.append({
                    "id": "default_reduction",
                    "category": "Business Value",
                    "title": "Default Rate Reduction (Latest Period)",
                    "value": f"{reduction:.1f}%",
                    "status": "good" if reduction > 30 else "warning" if reduction > 10 else "alert",
                    "trend": "falling",
                    "icon": "🛡️",
                    "description": f"Model reduced defaults from {latest.baseline_default_rate*100:.1f}% to "
                                   f"{latest.model_default_rate*100:.1f}% — a {reduction:.1f}% reduction. "
                                   f"{'Strong credit quality improvement.' if reduction > 30 else 'Moderate improvement.' if reduction > 10 else 'Minimal impact — review model effectiveness.'}",
                    "recommendation": "A/B test stricter cutoffs on high-risk segments to drive further reduction.",
                    "benchmark": "Target: >30% reduction | Acceptable: >15%",
                })

        return {
            "insights":      insights,
            "total":         len(insights),
            "alerts":        sum(1 for i in insights if i["status"] == "alert"),
            "warnings":      sum(1 for i in insights if i["status"] == "warning"),
            "good":          sum(1 for i in insights if i["status"] == "good"),
            "generated_at":  __import__("datetime").datetime.utcnow().isoformat(),
        }

    finally:
        session.close()


@router.get("/kpi/{kpi_id}")
def get_kpi_insight(kpi_id: str):
    """Get detailed insight for a specific KPI."""
    # Re-use dashboard insights and filter
    all_insights = get_dashboard_insights()
    match = next((i for i in all_insights["insights"] if i["id"] == kpi_id), None)
    if not match:
        return {"error": f"No insight for kpi_id={kpi_id}"}
    return match


@router.get("/alerts")
def get_active_alerts():
    """Return only alert-level insights."""
    result = get_dashboard_insights()
    return {
        "alerts":  [i for i in result["insights"] if i["status"] == "alert"],
        "warnings":[i for i in result["insights"] if i["status"] == "warning"],
    }
