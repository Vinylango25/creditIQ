"""
Credit Risk Database Schema Extension
======================================
Additional tables for credit scoring, risk analytics, and A/B testing.
Extends the existing fraud detection schema in db.py.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, String, Text, Date, Index, BigInteger,
)
from sqlalchemy.orm import relationship

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.db import Base, engine, Session


# ── Applicant (Borrower Profile — TransUnion/SEON-like bureau data) ──────────

class Applicant(Base):
    __tablename__ = "applicants"

    id                        = Column(Integer, primary_key=True, autoincrement=True)
    applicant_id              = Column(String, unique=True, nullable=False)  # e.g. APP-000001
    first_name                = Column(String)
    last_name                 = Column(String)
    national_id               = Column(String, unique=True, nullable=True)
    phone_number              = Column(String, nullable=True)
    email                     = Column(String, nullable=True)
    date_of_birth             = Column(Date, nullable=True)
    age                       = Column(Integer, nullable=True)
    gender                    = Column(String, nullable=True)            # M / F / Other
    country                   = Column(String, default="KE")             # KE / NG
    county_province           = Column(String, nullable=True)
    employment_status         = Column(String, nullable=True)            # employed / self_employed / unemployed
    employer_name             = Column(String, nullable=True)
    monthly_income_kes        = Column(Float, nullable=True)
    monthly_expenses_kes      = Column(Float, nullable=True)

    # ── TransUnion-like bureau fields ─────────────────────────────────────────
    tu_score                  = Column(Integer, nullable=True)            # 300–850 bureau score
    tu_grade                  = Column(String, nullable=True)             # A / B / C / D / E
    total_accounts            = Column(Integer, nullable=True)
    open_accounts             = Column(Integer, nullable=True)
    closed_accounts           = Column(Integer, nullable=True)
    delinquent_accounts       = Column(Integer, nullable=True)
    credit_utilization        = Column(Float, nullable=True)              # 0–1
    total_outstanding_debt    = Column(Float, nullable=True)
    total_credit_limit        = Column(Float, nullable=True)
    months_since_last_delinquency = Column(Integer, nullable=True)        # None = never
    months_credit_history     = Column(Integer, nullable=True)            # length of credit history
    num_hard_inquiries_12m    = Column(Integer, nullable=True)
    num_soft_inquiries_12m    = Column(Integer, nullable=True)
    bankruptcy_flag           = Column(Boolean, default=False)
    judgement_flag            = Column(Boolean, default=False)
    active_collections        = Column(Integer, default=0)
    debt_to_income            = Column(Float, nullable=True)              # DTI ratio

    # ── SEON / Digital risk enrichment ────────────────────────────────────────
    seon_fraud_score          = Column(Integer, nullable=True)            # 0–100 (higher = riskier)
    seon_email_deliverable    = Column(Boolean, nullable=True)
    seon_phone_valid          = Column(Boolean, nullable=True)
    seon_social_match_count   = Column(Integer, nullable=True)            # # social profiles found
    seon_ip_risk_level        = Column(String, nullable=True)             # low / medium / high
    seon_device_fingerprint   = Column(String, nullable=True)
    seon_is_vpn               = Column(Boolean, nullable=True)
    seon_is_tor               = Column(Boolean, nullable=True)

    # ── Mobile lending specific (M-Shwari / Tala / Branch-like) ──────────────
    mobile_wallet_age_months  = Column(Integer, nullable=True)
    mpesa_monthly_avg_in      = Column(Float, nullable=True)              # avg monthly M-Pesa inflows
    mpesa_monthly_avg_out     = Column(Float, nullable=True)
    mpesa_loan_history_count  = Column(Integer, nullable=True)
    sim_age_months            = Column(Integer, nullable=True)
    app_install_date          = Column(Date, nullable=True)

    created_at                = Column(DateTime, default=datetime.utcnow)
    updated_at                = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    loans         = relationship("Loan", back_populates="applicant")
    credit_scores = relationship("CreditScore", back_populates="applicant")


# ── Loan (Lending Product) ────────────────────────────────────────────────────

class Loan(Base):
    __tablename__ = "loans"

    id                      = Column(Integer, primary_key=True, autoincrement=True)
    loan_id                 = Column(String, unique=True, nullable=False)   # LN-000001
    applicant_id            = Column(String, ForeignKey("applicants.applicant_id"))
    product_type            = Column(String, nullable=False)    # instant_mobile / salary_advance / bnpl / sme
    loan_amount             = Column(Float, nullable=False)
    currency                = Column(String, default="KES")
    tenure_days             = Column(Integer, nullable=False)   # 7 / 14 / 30 / 60 / 90
    interest_rate           = Column(Float, nullable=False)     # annualised
    disbursement_date       = Column(Date, nullable=False)
    due_date                = Column(Date, nullable=False)
    status                  = Column(String, default="active")  # active / paid / default / written_off
    
    # Repayment tracking
    amount_repaid           = Column(Float, default=0.0)
    repayment_date          = Column(Date, nullable=True)
    days_past_due           = Column(Integer, default=0)
    
    # Risk scores at origination
    pd_score                = Column(Float, nullable=True)      # Probability of Default (0-1)
    lgd_score               = Column(Float, nullable=True)      # Loss Given Default (0-1)
    ead_amount              = Column(Float, nullable=True)      # Exposure at Default
    expected_loss           = Column(Float, nullable=True)      # EL = PD × LGD × EAD
    credit_score_at_orig    = Column(Integer, nullable=True)    # Internal score 300-850
    
    # Vintage / cohort tracking
    origination_year_month  = Column(String, nullable=True)     # "2024-01"
    cohort                  = Column(String, nullable=True)     # "2024-Q1"
    
    # Fraud link
    linked_transaction_id   = Column(Integer, nullable=True)
    fraud_flag              = Column(Boolean, default=False)
    
    # A/B test assignment
    ab_test_id              = Column(String, nullable=True)
    ab_variant              = Column(String, nullable=True)     # control / treatment
    
    created_at              = Column(DateTime, default=datetime.utcnow)

    applicant = relationship("Applicant", back_populates="loans")
    fpd_record = relationship("FPDRecord", back_populates="loan", uselist=False)


# ── Credit Score (Internal Scorecard Output) ──────────────────────────────────

class CreditScore(Base):
    __tablename__ = "credit_scores"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    applicant_id     = Column(String, ForeignKey("applicants.applicant_id"))
    score            = Column(Integer, nullable=False)    # 300–850
    score_band       = Column(String, nullable=False)     # Excellent / Good / Fair / Poor / Very Poor
    pd_estimate      = Column(Float, nullable=False)      # Probability of Default
    lgd_estimate     = Column(Float, nullable=True)
    scorecard_version = Column(String, default="v1.0")
    model_run_id     = Column(Integer, nullable=True)     # FK to model_runs if applicable
    
    # Score contributions (Weight of Evidence — top drivers)
    woe_breakdown    = Column(Text, nullable=True)        # JSON: {feature: woe_contribution}
    
    scored_at        = Column(DateTime, default=datetime.utcnow)

    applicant = relationship("Applicant", back_populates="credit_scores")


# ── FPD Record (First Payment Default — key mobile lending metric) ────────────

class FPDRecord(Base):
    """
    First Payment Default: did the borrower miss their FIRST scheduled payment?
    The most critical early warning indicator in mobile lending.
    """
    __tablename__ = "fpd_records"

    id                    = Column(Integer, primary_key=True, autoincrement=True)
    loan_id               = Column(String, ForeignKey("loans.loan_id"), unique=True)
    applicant_id          = Column(String, ForeignKey("applicants.applicant_id"))
    
    disbursement_date     = Column(Date, nullable=False)
    first_payment_due     = Column(Date, nullable=False)
    first_payment_made    = Column(Date, nullable=True)      # null if not yet paid
    
    dpd_at_day7           = Column(Integer, nullable=True)   # Days Past Due at D+7
    dpd_at_day14          = Column(Integer, nullable=True)
    dpd_at_day30          = Column(Integer, nullable=True)
    
    is_fpd                = Column(Boolean, nullable=True)   # missed first payment
    fpd_bucket            = Column(String, nullable=True)    # 1-7 / 8-14 / 15-30 / 30+
    
    # Risk factors at time of disbursement
    credit_score          = Column(Integer, nullable=True)
    pd_score              = Column(Float, nullable=True)
    seon_fraud_score      = Column(Integer, nullable=True)
    loan_amount           = Column(Float, nullable=True)
    tenure_days           = Column(Integer, nullable=True)
    product_type          = Column(String, nullable=True)
    cohort                = Column(String, nullable=True)

    loan = relationship("Loan", back_populates="fpd_record")


# ── Portfolio Cohort Analysis (Vintage) ───────────────────────────────────────

class CohortSnapshot(Base):
    """
    Monthly snapshot of portfolio cohort performance.
    Used for vintage curves — % default by months-on-book.
    """
    __tablename__ = "cohort_snapshots"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    cohort           = Column(String, nullable=False)        # "2024-Q1"
    mob              = Column(Integer, nullable=False)        # Months On Book (1, 2, 3...)
    snapshot_date    = Column(Date, nullable=False)
    
    total_loans      = Column(Integer, nullable=False)
    active_loans     = Column(Integer, default=0)
    paid_loans       = Column(Integer, default=0)
    default_loans    = Column(Integer, default=0)
    written_off      = Column(Integer, default=0)
    
    cumulative_default_rate = Column(Float, nullable=True)   # % defaulted by this MOB
    cumulative_loss_rate    = Column(Float, nullable=True)
    fpd_rate                = Column(Float, nullable=True)    # FPD % for this cohort
    
    total_disbursed         = Column(Float, nullable=True)
    total_recovered         = Column(Float, nullable=True)
    outstanding_balance     = Column(Float, nullable=True)


# ── A/B Test ──────────────────────────────────────────────────────────────────

class ABTest(Base):
    """
    A/B test definition for champion/challenger model experiments.
    """
    __tablename__ = "ab_tests"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    test_id          = Column(String, unique=True, nullable=False)   # "ABTEST-001"
    name             = Column(String, nullable=False)
    description      = Column(Text, nullable=True)
    hypothesis       = Column(Text, nullable=True)
    
    status           = Column(String, default="active")   # active / completed / paused
    
    # Models being compared
    control_model    = Column(String, nullable=False)      # e.g. "scorecard_v1"
    treatment_model  = Column(String, nullable=False)      # e.g. "lgbm_pd_v2"
    traffic_split    = Column(Float, default=0.5)          # fraction to treatment
    
    # Time bounds
    start_date       = Column(Date, nullable=False)
    end_date         = Column(Date, nullable=True)
    
    # Statistical results (computed)
    control_n        = Column(Integer, nullable=True)
    treatment_n      = Column(Integer, nullable=True)
    control_default_rate  = Column(Float, nullable=True)
    treatment_default_rate = Column(Float, nullable=True)
    p_value          = Column(Float, nullable=True)
    lift             = Column(Float, nullable=True)         # (treatment - control) / control
    is_significant   = Column(Boolean, nullable=True)
    confidence_level = Column(Float, default=0.95)
    
    winner           = Column(String, nullable=True)        # "control" / "treatment" / "none"
    notes            = Column(Text, nullable=True)
    created_at       = Column(DateTime, default=datetime.utcnow)


# ── PSI / Model Drift Report ──────────────────────────────────────────────────

class DriftReport(Base):
    """
    Population Stability Index (PSI) reports for monitoring feature and score drift.
    PSI < 0.1: stable; 0.1–0.25: some drift; > 0.25: significant drift.
    """
    __tablename__ = "drift_reports"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    report_date      = Column(Date, nullable=False)
    feature_name     = Column(String, nullable=False)
    psi_value        = Column(Float, nullable=False)
    drift_level      = Column(String, nullable=False)   # stable / warning / alert
    baseline_period  = Column(String, nullable=True)    # e.g. "2024-Q1"
    current_period   = Column(String, nullable=True)    # e.g. "2024-Q3"
    computed_at      = Column(DateTime, default=datetime.utcnow)


# ── Cost Analysis (Model Value / Business Impact) ────────────────────────────

class CostAnalysisReport(Base):
    """
    Simulated cost-benefit analysis: what does it cost to do nothing vs.
    using the model?  Populated from dummy data and kept up-to-date when
    new loans are seeded.
    """
    __tablename__ = "cost_analysis_reports"

    id                         = Column(Integer, primary_key=True, autoincrement=True)
    report_period              = Column(String, nullable=False)   # "2024-Q1" or "2025-06"
    report_type                = Column(String, default="quarterly")  # monthly / quarterly

    # ── Volume ──────────────────────────────────────────────────────────────
    total_applications         = Column(Integer, nullable=True)
    approved_loans             = Column(Integer, nullable=True)
    approval_rate              = Column(Float, nullable=True)
    total_disbursed_kes        = Column(Float, nullable=True)

    # ── Without-model baseline (naive approve-all) ────────────────────────
    baseline_default_rate      = Column(Float, nullable=True)   # historical naive rate
    baseline_default_count     = Column(Integer, nullable=True)
    baseline_loss_kes          = Column(Float, nullable=True)   # total credit losses

    # Fraud losses (no model)
    baseline_fraud_count       = Column(Integer, nullable=True)
    baseline_fraud_loss_kes    = Column(Float, nullable=True)

    # Ops cost: manual review hours × cost per hour
    baseline_manual_review_hrs = Column(Float, nullable=True)
    baseline_ops_cost_kes      = Column(Float, nullable=True)

    baseline_total_cost_kes    = Column(Float, nullable=True)   # credit + fraud + ops

    # ── With-model performance ───────────────────────────────────────────
    model_default_rate         = Column(Float, nullable=True)
    model_default_count        = Column(Integer, nullable=True)
    model_loss_kes             = Column(Float, nullable=True)

    model_fraud_count          = Column(Integer, nullable=True)
    model_fraud_loss_kes       = Column(Float, nullable=True)

    model_ops_cost_kes         = Column(Float, nullable=True)
    model_total_cost_kes       = Column(Float, nullable=True)

    # ── Savings ──────────────────────────────────────────────────────────
    credit_loss_saved_kes      = Column(Float, nullable=True)
    fraud_loss_saved_kes       = Column(Float, nullable=True)
    ops_cost_saved_kes         = Column(Float, nullable=True)
    total_saved_kes            = Column(Float, nullable=True)

    # ── ROI ───────────────────────────────────────────────────────────────
    model_cost_kes             = Column(Float, nullable=True)   # cost to run model (infra+licensing)
    net_benefit_kes            = Column(Float, nullable=True)   # total_saved - model_cost
    roi_pct                    = Column(Float, nullable=True)   # net_benefit / model_cost × 100

    # ── False positive cost (good borrowers declined) ─────────────────────
    false_positives            = Column(Integer, nullable=True)
    fp_opportunity_cost_kes    = Column(Float, nullable=True)  # revenue foregone

    computed_at                = Column(DateTime, default=datetime.utcnow)



# ── Credit Model Run (scorecard + PD model tracking) ─────────────────────────

class CreditModelRun(Base):
    """One row per trained credit scoring model run."""
    __tablename__ = "credit_model_runs"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    run_id              = Column(String, nullable=False)
    classifier_name     = Column(String, nullable=False)
    display_name        = Column(String, nullable=True)
    # Metrics
    auc_roc             = Column(Float, nullable=True)
    pr_auc              = Column(Float, nullable=True)
    ks_statistic        = Column(Float, nullable=True)
    gini                = Column(Float, nullable=True)
    f1                  = Column(Float, nullable=True)
    precision           = Column(Float, nullable=True)
    recall              = Column(Float, nullable=True)
    threshold           = Column(Float, nullable=True)
    n_train             = Column(Integer, nullable=True)
    default_rate        = Column(Float, nullable=True)
    training_duration_s = Column(Float, nullable=True)
    feature_importance  = Column(Text, nullable=True)    # JSON list
    artifact_path       = Column(String, nullable=True)
    is_champion         = Column(Boolean, default=False)
    trained_at          = Column(DateTime, default=datetime.utcnow)


def init_credit_db():
    """Create all credit risk tables (safe to call multiple times)."""
    Base.metadata.create_all(engine)
    print("[CREDIT DB] Tables initialised")


if __name__ == "__main__":
    init_credit_db()
