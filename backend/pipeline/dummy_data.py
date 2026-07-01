"""
Dummy Data Generator — Credit Risk Intelligence Platform
=========================================================
Generates realistic simulated data resembling:
  - TransUnion bureau data (credit history, scores, delinquencies)
  - SEON digital risk enrichment (email/phone/IP/device signals)
  - Mobile lending portfolio (M-Shwari / Tala / Branch style)
  - Loan performance with FPD, vintage cohorts, roll rates
  - A/B test assignments
  - Cost analysis benchmarks (fraud losses, model savings)

Run: python pipeline/dummy_data.py
"""
from __future__ import annotations

import random
import sys, os
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.credit_db import (
    Applicant, Loan, CreditScore, FPDRecord,
    CohortSnapshot, ABTest, DriftReport, CostAnalysisReport, init_credit_db,
)
from pipeline.db import Session, init_db

RANDOM_SEED = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

N_APPLICANTS = 5_000
N_LOANS      = 12_000

# ── Reference data ────────────────────────────────────────────────────────────
KE_COUNTIES = ["Nairobi","Mombasa","Kisumu","Nakuru","Eldoret","Thika","Nyeri",
                "Machakos","Meru","Garissa","Kitale","Malindi"]
NG_STATES   = ["Lagos","Abuja","Kano","Ibadan","Port Harcourt","Benin City",
                "Kaduna","Enugu","Owerri","Uyo"]
EMPLOYERS   = ["Kenya Commercial Bank","Safaricom","Equity Bank","Standard Chartered",
                "Unilever Kenya","East Africa Breweries","Nation Media","Kenya Airways",
                "Total Kenya","Naivas Supermarket","Civil Service","Teaching Service",
                "MTN Nigeria","Dangote Group","Access Bank","GTBank","Zenith Bank",
                "NNPC","First Bank","Self Employed","Freelancer","SME Owner"]
PRODUCT_TYPES = ["instant_mobile","salary_advance","bnpl","sme_loan","emergency_loan"]
IP_RISK       = ["low","low","low","medium","medium","high"]
DEVICE_FP     = [f"fp_{uuid.uuid4().hex[:8]}" for _ in range(500)]


def _rand_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def _tu_grade(score: int) -> str:
    if score >= 750: return "A"
    if score >= 700: return "B"
    if score >= 650: return "C"
    if score >= 600: return "D"
    return "E"


def _score_band(score: int) -> str:
    if score >= 750: return "Excellent"
    if score >= 700: return "Good"
    if score >= 650: return "Fair"
    if score >= 600: return "Poor"
    return "Very Poor"


def _pd_from_score(score: int) -> float:
    """Logistic mapping from credit score (300-850) to PD (0→1)."""
    x = (score - 575) / 100.0
    return float(1 / (1 + np.exp(2.5 * x)))


def _seon_score(is_fraud_prone: bool) -> int:
    if is_fraud_prone:
        return random.randint(45, 95)
    return random.randint(2, 40)


# ── Generate Applicants ───────────────────────────────────────────────────────

def generate_applicants(n: int = N_APPLICANTS) -> list[Applicant]:
    applicants = []
    start_date = date(2022, 1, 1)
    end_date   = date(2025, 6, 1)

    for i in range(n):
        country   = random.choice(["KE"] * 6 + ["NG"] * 4)
        age       = random.randint(18, 65)
        income    = round(np.random.lognormal(np.log(35_000 if country == "KE" else 85_000), 0.7), 2)
        is_risky  = random.random() < 0.18   # 18% high-risk applicants

        # TransUnion-like bureau score (correlated with income and age)
        base_score = min(850, max(300, int(
            400
            + (age - 18) * 2.5
            + min(income / 2000, 150)
            + random.gauss(0, 60)
            - (80 if is_risky else 0)
        )))

        util   = round(random.betavariate(2, 3) if not is_risky else random.betavariate(4, 2), 3)
        delinq = random.randint(0, 3) if is_risky else random.choices([0,1], weights=[0.92,0.08])[0]
        mob    = random.randint(3, 240)  # months in bureau
        n_hard = random.randint(0, 8) if is_risky else random.randint(0, 3)
        total_debt  = round(income * random.uniform(0.5, 4.0 if is_risky else 2.0), 2)
        credit_lim  = round(income * random.uniform(1.0, 5.0), 2)
        dti         = round(min(total_debt / (income * 12 + 1), 2.5), 3)

        mpesa_in   = round(income * random.uniform(0.8, 1.5), 2)
        mpesa_out  = round(mpesa_in * random.uniform(0.6, 0.95), 2)

        county = (random.choice(KE_COUNTIES) if country == "KE"
                  else random.choice(NG_STATES))

        a = Applicant(
            applicant_id              = f"APP-{i+1:06d}",
            first_name                = random.choice(["James","Mary","John","Grace","Peter","Faith",
                                                        "David","Ruth","Samuel","Joyce","Emeka","Ngozi",
                                                        "Chidi","Amaka","Tunde","Bola","Kevin","Aisha"]),
            last_name                 = random.choice(["Kamau","Wanjiku","Odhiambo","Mwangi","Kariuki",
                                                       "Adesanya","Okafor","Ibrahim","Nwosu","Adeleke",
                                                       "Mutua","Njoroge","Otieno","Okonkwo","Balogun"]),
            national_id               = f"{'KE' if country=='KE' else 'NG'}{random.randint(10000000,99999999)}",
            phone_number              = f"+{'254' if country=='KE' else '234'}{random.randint(700000000,799999999)}",
            email                     = f"user{i+1}@{random.choice(['gmail.com','yahoo.com','outlook.com','hotmail.com'])}",
            date_of_birth             = date.today() - timedelta(days=age*365),
            age                       = age,
            gender                    = random.choice(["M","M","F","F","M"]),
            country                   = country,
            county_province           = county,
            employment_status         = random.choice(["employed","employed","self_employed","unemployed"]),
            employer_name             = random.choice(EMPLOYERS),
            monthly_income_kes        = income,
            monthly_expenses_kes      = round(income * random.uniform(0.4, 0.8), 2),
            # Bureau
            tu_score                  = base_score,
            tu_grade                  = _tu_grade(base_score),
            total_accounts            = random.randint(1, 10),
            open_accounts             = random.randint(1, 6),
            closed_accounts           = random.randint(0, 4),
            delinquent_accounts       = delinq,
            credit_utilization        = util,
            total_outstanding_debt    = total_debt,
            total_credit_limit        = credit_lim,
            months_since_last_delinquency = random.randint(3, 36) if delinq > 0 else None,
            months_credit_history     = mob,
            num_hard_inquiries_12m    = n_hard,
            num_soft_inquiries_12m    = random.randint(0, 5),
            bankruptcy_flag           = random.random() < 0.01,
            judgement_flag            = random.random() < 0.02,
            active_collections        = random.randint(0, 2) if is_risky else 0,
            debt_to_income            = dti,
            # SEON
            seon_fraud_score          = _seon_score(is_risky),
            seon_email_deliverable    = random.random() > 0.05,
            seon_phone_valid          = random.random() > 0.03,
            seon_social_match_count   = random.randint(0, 8),
            seon_ip_risk_level        = random.choice(IP_RISK),
            seon_device_fingerprint   = random.choice(DEVICE_FP),
            seon_is_vpn               = random.random() < 0.04,
            seon_is_tor               = random.random() < 0.005,
            # Mobile
            mobile_wallet_age_months  = random.randint(1, 60),
            mpesa_monthly_avg_in      = mpesa_in,
            mpesa_monthly_avg_out     = mpesa_out,
            mpesa_loan_history_count  = random.randint(0, 12),
            sim_age_months            = random.randint(6, 120),
            app_install_date          = _rand_date(date(2021, 1, 1), date(2025, 1, 1)),
            created_at                = datetime.combine(
                _rand_date(start_date, end_date), datetime.min.time()
            ),
        )
        applicants.append(a)
    return applicants


# ── Generate Loans ─────────────────────────────────────────────────────────────

def generate_loans(applicants: list[Applicant], n: int = N_LOANS) -> list[Loan]:
    loans       = []
    ab_test_ids = ["ABTEST-001", "ABTEST-002", None, None, None]

    for i in range(n):
        app       = random.choice(applicants)
        score     = app.tu_score or 600
        pd        = _pd_from_score(score)
        is_default_likely = random.random() < pd

        product   = random.choice(PRODUCT_TYPES)
        currency  = "KES" if app.country == "KE" else "NGN"
        tenure    = random.choice([7, 14, 30, 30, 60, 90])
        income    = app.monthly_income_kes or 30_000
        max_amt   = income * (0.5 if product == "instant_mobile" else
                              2.0 if product == "salary_advance" else
                              3.0 if product == "sme_loan" else 1.0)
        amount    = round(max(500, np.random.lognormal(np.log(min(max_amt, 50_000)), 0.5)), 2)
        rate      = random.uniform(0.12, 0.36)  # 12–36% p.a.

        # Disbursement date spread across 3 years
        disb_date = _rand_date(date(2022, 1, 1), date(2025, 3, 31))
        due_date  = disb_date + timedelta(days=tenure)
        ym        = disb_date.strftime("%Y-%m")
        quarter   = f"{disb_date.year}-Q{(disb_date.month-1)//3+1}"

        # Repayment outcome
        if due_date <= date.today():
            if is_default_likely:
                status      = random.choice(["default","written_off","default"])
                dpd         = random.randint(7, 90)
                repaid      = round(amount * random.uniform(0, 0.6), 2)
                repay_date  = None
            else:
                status      = "paid"
                dpd         = 0
                repaid      = round(amount * (1 + rate * tenure / 365), 2)
                repay_date  = due_date + timedelta(days=random.randint(-2, 5))
        else:
            status     = "active"
            dpd        = max(0, (date.today() - due_date).days) if date.today() > due_date else 0
            repaid     = 0.0
            repay_date = None

        lgd    = random.uniform(0.3, 0.8)
        ead    = amount
        el     = round(pd * lgd * ead, 2)

        ab_test = random.choice(ab_test_ids)
        ab_var  = random.choice(["control", "treatment"]) if ab_test else None

        loan = Loan(
            loan_id                = f"LN-{i+1:07d}",
            applicant_id           = app.applicant_id,
            product_type           = product,
            loan_amount            = amount,
            currency               = currency,
            tenure_days            = tenure,
            interest_rate          = round(rate, 4),
            disbursement_date      = disb_date,
            due_date               = due_date,
            status                 = status,
            amount_repaid          = repaid,
            repayment_date         = repay_date,
            days_past_due          = dpd,
            pd_score               = round(pd, 4),
            lgd_score              = round(lgd, 4),
            ead_amount             = ead,
            expected_loss          = el,
            credit_score_at_orig   = score,
            origination_year_month = ym,
            cohort                 = quarter,
            fraud_flag             = app.seon_fraud_score > 70 and random.random() < 0.3,
            ab_test_id             = ab_test,
            ab_variant             = ab_var,
            created_at             = datetime.combine(disb_date, datetime.min.time()),
        )
        loans.append(loan)
    return loans


# ── Generate Credit Scores ────────────────────────────────────────────────────

def generate_credit_scores(applicants: list[Applicant]) -> list[CreditScore]:
    scores = []
    for app in applicants:
        raw = app.tu_score or 600
        # Add some scoring model noise vs raw bureau score
        modelled = int(np.clip(raw + random.gauss(0, 25), 300, 850))
        pd_est   = _pd_from_score(modelled)
        lgd_est  = round(random.uniform(0.3, 0.7), 3)

        woe = {
            "credit_utilization":    round(-(app.credit_utilization or 0.3) * 40, 2),
            "months_credit_history": round(min((app.months_credit_history or 0) / 6, 20), 2),
            "delinquent_accounts":   round(-(app.delinquent_accounts or 0) * 15, 2),
            "num_hard_inquiries":    round(-(app.num_hard_inquiries_12m or 0) * 5, 2),
            "debt_to_income":        round(-(app.debt_to_income or 0.3) * 30, 2),
            "mpesa_inflow":          round(min((app.mpesa_monthly_avg_in or 0) / 5000, 15), 2),
            "seon_risk":             round(-(app.seon_fraud_score or 20) / 10, 2),
        }
        import json
        scores.append(CreditScore(
            applicant_id      = app.applicant_id,
            score             = modelled,
            score_band        = _score_band(modelled),
            pd_estimate       = round(pd_est, 4),
            lgd_estimate      = lgd_est,
            scorecard_version = "v1.0",
            woe_breakdown     = json.dumps(woe),
            scored_at         = app.created_at or datetime.utcnow(),
        ))
    return scores


# ── Generate FPD Records ──────────────────────────────────────────────────────

def generate_fpd_records(loans: list[Loan]) -> list[FPDRecord]:
    records = []
    for loan in loans:
        if loan.due_date > date.today():
            continue  # still active, no FPD data yet
        first_due = loan.disbursement_date + timedelta(days=min(loan.tenure_days, 30))
        is_fpd    = loan.status in ("default", "written_off") and random.random() < 0.7
        if not is_fpd and loan.status == "paid":
            is_fpd = random.random() < 0.04   # small FPD-but-recovered rate

        dpd7  = random.randint(5, 30) if is_fpd else random.randint(0, 3)
        dpd14 = dpd7 + (random.randint(0, 15) if is_fpd else 0)
        dpd30 = dpd14 + (random.randint(0, 20) if is_fpd else 0)

        if is_fpd:
            if dpd7 <= 7:    bucket = "1-7"
            elif dpd7 <= 14: bucket = "8-14"
            elif dpd7 <= 30: bucket = "15-30"
            else:            bucket = "30+"
        else:
            bucket = None

        records.append(FPDRecord(
            loan_id            = loan.loan_id,
            applicant_id       = loan.applicant_id,
            disbursement_date  = loan.disbursement_date,
            first_payment_due  = first_due,
            first_payment_made = (first_due + timedelta(days=random.randint(-3, dpd7)))
                                 if not is_fpd else None,
            dpd_at_day7        = dpd7,
            dpd_at_day14       = dpd14,
            dpd_at_day30       = dpd30,
            is_fpd             = is_fpd,
            fpd_bucket         = bucket,
            credit_score       = loan.credit_score_at_orig,
            pd_score           = loan.pd_score,
            loan_amount        = loan.loan_amount,
            tenure_days        = loan.tenure_days,
            product_type       = loan.product_type,
            cohort             = loan.cohort,
        ))
    return records


# ── Generate Cohort Snapshots ─────────────────────────────────────────────────

def generate_cohort_snapshots(loans: list[Loan]) -> list[CohortSnapshot]:
    from collections import defaultdict
    cohort_loans: dict = defaultdict(list)
    for ln in loans:
        cohort_loans[ln.cohort].append(ln)

    snapshots = []
    for cohort, cohort_list in sorted(cohort_loans.items()):
        total       = len(cohort_list)
        fpd_count   = sum(1 for l in cohort_list if l.status in ("default","written_off"))
        disbursed   = sum(l.loan_amount for l in cohort_list)

        # Generate MOB 1..12
        for mob in range(1, 13):
            cum_default_rate = min(fpd_count / max(total, 1) * (mob / 12), 1.0)
            cum_default_rate += random.gauss(0, 0.005)
            cum_default_rate = round(max(0, min(cum_default_rate, 0.5)), 4)

            defaults    = int(total * cum_default_rate)
            paid        = max(0, total - defaults - int(total * 0.15))
            active      = total - defaults - paid
            recovered   = round(disbursed * cum_default_rate * random.uniform(0.3, 0.6), 2)
            outstanding = round(disbursed * (active / max(total, 1)) * 0.8, 2)

            snapshots.append(CohortSnapshot(
                cohort                  = cohort,
                mob                     = mob,
                snapshot_date           = date(2025, 1, 1) + timedelta(days=mob * 30),
                total_loans             = total,
                active_loans            = max(0, active),
                paid_loans              = max(0, paid),
                default_loans           = defaults,
                written_off             = int(defaults * 0.3),
                cumulative_default_rate = cum_default_rate,
                cumulative_loss_rate    = round(cum_default_rate * random.uniform(0.4, 0.7), 4),
                fpd_rate                = round(fpd_count / max(total, 1), 4),
                total_disbursed         = disbursed,
                total_recovered         = recovered,
                outstanding_balance     = outstanding,
            ))
    return snapshots


# ── Generate A/B Tests ────────────────────────────────────────────────────────

def generate_ab_tests() -> list[ABTest]:
    tests = [
        ABTest(
            test_id          = "ABTEST-001",
            name             = "Scorecard v1 vs LightGBM PD Model",
            description      = "Comparing logistic scorecard against LightGBM on mobile instant loans",
            hypothesis       = "LightGBM will reduce default rate by 15% with <5% volume loss",
            status           = "completed",
            control_model    = "scorecard_v1",
            treatment_model  = "lightgbm_pd_v2",
            traffic_split    = 0.50,
            start_date       = date(2024, 1, 1),
            end_date         = date(2024, 3, 31),
            control_n        = 2340,
            treatment_n      = 2287,
            control_default_rate  = 0.112,
            treatment_default_rate= 0.089,
            p_value          = 0.0031,
            lift             = -0.205,
            is_significant   = True,
            confidence_level = 0.95,
            winner           = "treatment",
            notes            = "LightGBM reduced defaults by 20.5%. Promoted to champion.",
        ),
        ABTest(
            test_id          = "ABTEST-002",
            name             = "Strict Cutoff vs Flexible Threshold on BNPL",
            description      = "Score cutoff 650 vs dynamic threshold per product",
            hypothesis       = "Dynamic threshold increases approval rate 8% with same risk",
            status           = "active",
            control_model    = "cutoff_650",
            treatment_model  = "dynamic_threshold",
            traffic_split    = 0.50,
            start_date       = date(2025, 1, 1),
            end_date         = date(2025, 6, 30),
            control_n        = 1180,
            treatment_n      = 1204,
            control_default_rate  = 0.098,
            treatment_default_rate= 0.103,
            p_value          = 0.21,
            lift             = 0.051,
            is_significant   = False,
            confidence_level = 0.95,
            winner           = None,
            notes            = "Test ongoing. Not yet statistically significant.",
        ),
        ABTest(
            test_id          = "ABTEST-003",
            name             = "SEON Fraud Signal vs No SEON on Salary Advance",
            description      = "Does adding SEON risk score at origination reduce fraud losses?",
            hypothesis       = "SEON reduces fraud-driven defaults by 30%",
            status           = "completed",
            control_model    = "no_seon_signal",
            treatment_model  = "with_seon_signal",
            traffic_split    = 0.50,
            start_date       = date(2023, 7, 1),
            end_date         = date(2023, 12, 31),
            control_n        = 3100,
            treatment_n      = 3045,
            control_default_rate  = 0.078,
            treatment_default_rate= 0.051,
            p_value          = 0.00008,
            lift             = -0.346,
            is_significant   = True,
            confidence_level = 0.99,
            winner           = "treatment",
            notes            = "SEON integration reduces fraud defaults by 34.6%. Significant at 99%.",
        ),
    ]
    return tests


# ── Generate Drift Reports ────────────────────────────────────────────────────

def generate_drift_reports() -> list[DriftReport]:
    features = ["credit_score","debt_to_income","loan_amount","credit_utilization",
                "num_hard_inquiries","seon_fraud_score","mpesa_monthly_avg_in",
                "mobile_wallet_age_months","age","monthly_income"]
    reports  = []
    for feat in features:
        psi = round(abs(random.gauss(0.08, 0.07)), 4)
        reports.append(DriftReport(
            report_date    = date(2025, 6, 1),
            feature_name   = feat,
            psi_value      = psi,
            drift_level    = "stable" if psi < 0.1 else ("warning" if psi < 0.25 else "alert"),
            baseline_period= "2024-Q1",
            current_period = "2025-Q2",
        ))
    return reports


# ── Generate Cost Analysis Reports ───────────────────────────────────────────

def generate_cost_analysis(loans: list[Loan]) -> list[CostAnalysisReport]:
    """
    Simulates quarterly cost-benefit analysis for 2022-Q1 through 2025-Q2.
    Uses realistic KES figures for a mid-size mobile lender (~100k loans/year).

    Key assumptions (documented for transparency):
      - Average loan size: KES 8,500
      - Baseline (no-model) default rate: 18%
      - Model-driven default rate: ~9.5% (47% reduction)
      - Fraud accounts for 22% of defaults
      - Manual review cost: KES 350/case
      - Model infrastructure cost: KES 180,000/quarter
      - False positive rate: 8% of approved population (good borrowers declined)
      - Average interest revenue per loan: KES 1,200 (opportunity cost proxy)
    """
    from collections import defaultdict

    cohort_loans: dict = defaultdict(list)
    for ln in loans:
        if ln.cohort:
            cohort_loans[ln.cohort].append(ln)

    reports = []
    # Quarters in scope
    quarters = sorted(set(ln.cohort for ln in loans if ln.cohort))

    # Simulate improving model performance over time (model gets better)
    base_improvement = 0.47   # ~47% default reduction from model v1
    for q_idx, cohort in enumerate(quarters):
        q_loans   = cohort_loans[cohort]
        n_loans   = len(q_loans)
        if n_loans == 0:
            continue

        # Disbursed volume
        total_disbursed = sum(l.loan_amount for l in q_loans)
        avg_loan        = total_disbursed / n_loans

        # Simulate improving model — gains 2% each quarter
        model_improvement = min(base_improvement + q_idx * 0.02, 0.65)

        # ── Baseline (naive approve-all) ───────────────────────────────────
        baseline_default_rate  = round(random.uniform(0.16, 0.22), 4)
        baseline_defaults      = int(n_loans * baseline_default_rate)
        baseline_lgd           = 0.55
        baseline_loss          = round(baseline_defaults * avg_loan * baseline_lgd, 2)

        # Fraud: 22% of baseline defaults are fraud-driven
        baseline_fraud_count   = int(baseline_defaults * 0.22)
        baseline_fraud_loss    = round(baseline_fraud_count * avg_loan * 0.85, 2)

        # Manual ops: all loans need manual review at 45 min/case, KES 350/hr
        baseline_review_hrs    = round(n_loans * 0.75, 1)   # 45 min each
        baseline_ops           = round(baseline_review_hrs * 350, 2)

        baseline_total         = round(baseline_loss + baseline_fraud_loss + baseline_ops, 2)

        # ── With-model ────────────────────────────────────────────────────
        model_default_rate     = round(baseline_default_rate * (1 - model_improvement), 4)
        model_defaults         = int(n_loans * model_default_rate)
        model_loss             = round(model_defaults * avg_loan * baseline_lgd, 2)

        model_fraud_count      = int(model_defaults * 0.08)   # fraud detection catches most
        model_fraud_loss       = round(model_fraud_count * avg_loan * 0.85, 2)

        # Automated scoring: only 15% of loans need manual review
        model_review_hrs       = round(n_loans * 0.15 * 0.75, 1)
        model_ops              = round(model_review_hrs * 350, 2)
        model_total            = round(model_loss + model_fraud_loss + model_ops, 2)

        # ── Savings ───────────────────────────────────────────────────────
        credit_saved           = round(baseline_loss - model_loss, 2)
        fraud_saved            = round(baseline_fraud_loss - model_fraud_loss, 2)
        ops_saved              = round(baseline_ops - model_ops, 2)
        total_saved            = round(credit_saved + fraud_saved + ops_saved, 2)

        # ── ROI ───────────────────────────────────────────────────────────
        model_cost             = round(180_000 + n_loans * 2.5, 2)   # infra + per-call cost
        net_benefit            = round(total_saved - model_cost, 2)
        roi_pct                = round(net_benefit / model_cost * 100, 2) if model_cost > 0 else 0

        # ── False positive cost ────────────────────────────────────────────
        fp_rate                = random.uniform(0.06, 0.11)
        fp_count               = int(n_loans * fp_rate)
        fp_opp_cost            = round(fp_count * 1_200, 2)   # avg revenue per loan

        reports.append(CostAnalysisReport(
            report_period              = cohort,
            report_type                = "quarterly",
            total_applications         = int(n_loans * 1.35),   # some are rejected
            approved_loans             = n_loans,
            approval_rate              = round(n_loans / (n_loans * 1.35), 4),
            total_disbursed_kes        = round(total_disbursed, 2),
            # Baseline
            baseline_default_rate      = baseline_default_rate,
            baseline_default_count     = baseline_defaults,
            baseline_loss_kes          = baseline_loss,
            baseline_fraud_count       = baseline_fraud_count,
            baseline_fraud_loss_kes    = baseline_fraud_loss,
            baseline_manual_review_hrs = baseline_review_hrs,
            baseline_ops_cost_kes      = baseline_ops,
            baseline_total_cost_kes    = baseline_total,
            # Model
            model_default_rate         = model_default_rate,
            model_default_count        = model_defaults,
            model_loss_kes             = model_loss,
            model_fraud_count          = model_fraud_count,
            model_fraud_loss_kes       = model_fraud_loss,
            model_ops_cost_kes         = model_ops,
            model_total_cost_kes       = model_total,
            # Savings
            credit_loss_saved_kes      = credit_saved,
            fraud_loss_saved_kes       = fraud_saved,
            ops_cost_saved_kes         = ops_saved,
            total_saved_kes            = total_saved,
            # ROI
            model_cost_kes             = model_cost,
            net_benefit_kes            = net_benefit,
            roi_pct                    = roi_pct,
            # FP cost
            false_positives            = fp_count,
            fp_opportunity_cost_kes    = fp_opp_cost,
        ))
    return reports

def run_seed(force: bool = False):
    init_db()
    init_credit_db()
    session = Session()

    try:
        existing = session.query(Applicant).count()
        if existing > 0 and not force:
            print(f"[SEED] DB already has {existing} applicants — skipping (use force=True to re-seed)")
            return

        if force and existing > 0:
            print("[SEED] Force re-seed: clearing existing credit tables …")
            for tbl in [DriftReport, CohortSnapshot, FPDRecord, CreditScore, Loan, Applicant, ABTest, CostAnalysisReport]:
                session.query(tbl).delete()
            session.commit()

        print(f"[SEED] Generating {N_APPLICANTS} applicants …")
        applicants = generate_applicants(N_APPLICANTS)
        session.bulk_save_objects(applicants)
        session.commit()

        print(f"[SEED] Generating {N_LOANS} loans …")
        app_list = session.query(Applicant).all()
        loans    = generate_loans(app_list, N_LOANS)
        session.bulk_save_objects(loans)
        session.commit()

        print("[SEED] Generating credit scores …")
        scores = generate_credit_scores(app_list)
        session.bulk_save_objects(scores)
        session.commit()

        print("[SEED] Generating FPD records …")
        loan_list = session.query(Loan).all()
        fpd_recs  = generate_fpd_records(loan_list)
        session.bulk_save_objects(fpd_recs)
        session.commit()

        print("[SEED] Generating cohort snapshots …")
        snapshots = generate_cohort_snapshots(loan_list)
        session.bulk_save_objects(snapshots)
        session.commit()

        print("[SEED] Generating A/B tests …")
        ab_tests = generate_ab_tests()
        session.bulk_save_objects(ab_tests)
        session.commit()

        print("[SEED] Generating drift reports …")
        drifts = generate_drift_reports()
        session.bulk_save_objects(drifts)
        session.commit()

        print("[SEED] Generating cost analysis reports …")
        loan_list2 = session.query(Loan).all()
        cost_reports = generate_cost_analysis(loan_list2)
        session.bulk_save_objects(cost_reports)
        session.commit()

        print(f"[SEED] ✅ Done — {N_APPLICANTS} applicants, {N_LOANS} loans seeded")

    except Exception as e:
        session.rollback()
        print(f"[SEED] ERROR: {e}")
        import traceback; traceback.print_exc()
    finally:
        session.close()


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="Re-seed even if data exists")
    args = ap.parse_args()
    run_seed(force=args.force)
