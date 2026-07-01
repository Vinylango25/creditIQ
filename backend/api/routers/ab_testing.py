"""
/api/ab — A/B Testing: Champion/Challenger experiments, statistical significance
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import desc

from pipeline.db import Session
from pipeline.credit_db import ABTest, Loan

router = APIRouter()


# ── 1. All A/B Tests ─────────────────────────────────────────────────────────

@router.get("/tests")
def get_all_tests():
    session = Session()
    try:
        tests = session.query(ABTest).order_by(desc(ABTest.created_at)).all()
        return [_test_to_dict(t) for t in tests]
    finally:
        session.close()


# ── 2. Single Test Detail ────────────────────────────────────────────────────

@router.get("/tests/{test_id}")
def get_test(test_id: str):
    session = Session()
    try:
        t = session.query(ABTest).filter_by(test_id=test_id).first()
        if not t:
            raise HTTPException(status_code=404, detail="Test not found")

        # Pull actual loan data for this test
        control_loans   = session.query(Loan).filter_by(ab_test_id=test_id, ab_variant="control").count()
        treatment_loans = session.query(Loan).filter_by(ab_test_id=test_id, ab_variant="treatment").count()

        from sqlalchemy import func
        c_defs = session.query(func.count(Loan.id)).filter(
            Loan.ab_test_id == test_id,
            Loan.ab_variant == "control",
            Loan.status.in_(["default","written_off"]),
        ).scalar() or 0

        t_defs = session.query(func.count(Loan.id)).filter(
            Loan.ab_test_id == test_id,
            Loan.ab_variant == "treatment",
            Loan.status.in_(["default","written_off"]),
        ).scalar() or 0

        actual_c_rate = round(c_defs / max(control_loans, 1), 4)
        actual_t_rate = round(t_defs / max(treatment_loans, 1), 4)

        d = _test_to_dict(t)
        d["actual_data"] = {
            "control_loans":       control_loans,
            "treatment_loans":     treatment_loans,
            "control_defaults":    c_defs,
            "treatment_defaults":  t_defs,
            "actual_control_default_rate":   actual_c_rate,
            "actual_treatment_default_rate": actual_t_rate,
            "actual_lift": round((actual_t_rate - actual_c_rate) / max(actual_c_rate, 0.001), 4)
                           if actual_c_rate > 0 else 0,
        }
        return d
    finally:
        session.close()


# ── 3. Summary Stats ─────────────────────────────────────────────────────────

@router.get("/summary")
def get_ab_summary():
    session = Session()
    try:
        all_tests  = session.query(ABTest).all()
        total      = len(all_tests)
        active     = sum(1 for t in all_tests if t.status == "active")
        completed  = sum(1 for t in all_tests if t.status == "completed")
        significant= sum(1 for t in all_tests if t.is_significant)
        winners_treatment = sum(1 for t in all_tests if t.winner == "treatment")
        winners_control   = sum(1 for t in all_tests if t.winner == "control")

        total_savings_pct = 0.0
        completed_with_winner = [t for t in all_tests if t.status == "completed" and t.winner == "treatment"]
        if completed_with_winner:
            avg_lift = sum(abs(t.lift or 0) for t in completed_with_winner) / len(completed_with_winner)
            total_savings_pct = round(avg_lift * 100, 2)

        return {
            "total_tests":         total,
            "active_tests":        active,
            "completed_tests":     completed,
            "significant_results": significant,
            "treatment_wins":      winners_treatment,
            "control_wins":        winners_control,
            "avg_lift_pct":        total_savings_pct,
        }
    finally:
        session.close()


# ── 4. Power Analysis (sample size calculator) ───────────────────────────────

@router.get("/power-analysis")
def get_power_analysis(
    baseline_rate:  float = Query(0.10, description="Baseline default rate"),
    min_detectable: float = Query(0.02, description="Minimum detectable effect (absolute)"),
    alpha:          float = Query(0.05, description="Significance level"),
    power:          float = Query(0.80, description="Statistical power"),
):
    """
    Calculate required sample size per arm for a two-proportion z-test.
    """
    import numpy as np
    from scipy import stats

    p1 = baseline_rate
    p2 = baseline_rate - min_detectable   # expected treatment rate
    p2 = max(p2, 0.001)

    p_bar = (p1 + p2) / 2
    z_alpha = stats.norm.ppf(1 - alpha / 2)
    z_power = stats.norm.ppf(power)

    # Two-proportion z-test sample size formula
    n = ((z_alpha * (2 * p_bar * (1 - p_bar)) ** 0.5 +
          z_power * (p1*(1-p1) + p2*(1-p2)) ** 0.5) /
         abs(p1 - p2)) ** 2

    n_per_arm = int(np.ceil(n))

    return {
        "baseline_rate":     p1,
        "treatment_rate":    round(p2, 4),
        "min_effect_abs":    min_detectable,
        "alpha":             alpha,
        "power":             power,
        "n_per_arm":         n_per_arm,
        "total_n":           n_per_arm * 2,
        "note": "Sample size required per test arm for statistically valid results",
    }


# ── 5. Cumulative lift over time ──────────────────────────────────────────────

@router.get("/cumulative-lift/{test_id}")
def get_cumulative_lift(test_id: str):
    """Simulated cumulative lift curve — shows how lift converges over time."""
    import numpy as np
    session = Session()
    try:
        t = session.query(ABTest).filter_by(test_id=test_id).first()
        if not t:
            raise HTTPException(status_code=404, detail="Test not found")

        n = t.control_n or 1000
        true_lift = t.lift or -0.1

        # Simulate weekly cumulative observations
        weeks = list(range(1, 13))
        cumulative_lift = []
        cumulative_pvalue = []
        np.random.seed(42)

        for w in weeks:
            frac = w / 12.0
            observed_n  = int(n * frac)
            noise        = np.random.normal(0, 0.05 / (w ** 0.5))
            obs_lift     = round(true_lift + noise, 4)
            # p-value decreases as sample grows
            p_val        = max(0.001, round(1.0 / (1 + abs(true_lift) * observed_n / 100), 4))
            cumulative_lift.append(obs_lift * 100)
            cumulative_pvalue.append(p_val)

        return {
            "test_id":          test_id,
            "weeks":            weeks,
            "cumulative_lift":  [round(v, 2) for v in cumulative_lift],
            "p_values":         cumulative_pvalue,
            "significance_line":5.0,   # 5% alpha line
            "final_lift_pct":   round(true_lift * 100, 2),
            "is_significant":   t.is_significant,
        }
    finally:
        session.close()


# ── Helper ────────────────────────────────────────────────────────────────────

def _test_to_dict(t: ABTest) -> dict:
    return {
        "test_id":                t.test_id,
        "name":                   t.name,
        "description":            t.description,
        "hypothesis":             t.hypothesis,
        "status":                 t.status,
        "control_model":          t.control_model,
        "treatment_model":        t.treatment_model,
        "traffic_split":          t.traffic_split,
        "start_date":             str(t.start_date) if t.start_date else None,
        "end_date":               str(t.end_date) if t.end_date else None,
        "control_n":              t.control_n,
        "treatment_n":            t.treatment_n,
        "control_default_rate":   t.control_default_rate,
        "treatment_default_rate": t.treatment_default_rate,
        "p_value":                t.p_value,
        "lift":                   t.lift,
        "lift_pct":               round((t.lift or 0) * 100, 2),
        "is_significant":         t.is_significant,
        "confidence_level":       t.confidence_level,
        "winner":                 t.winner,
        "notes":                  t.notes,
    }
