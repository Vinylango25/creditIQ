"""
Unified Credit Risk Dataset Generator
======================================
Creates 500,000 realistic loan applications with distributions calibrated
to match real-world datasets:
  - Home Credit Default Risk (Kaggle) — bureau + application features
  - Lending Club Loan Data            — loan terms, grades, outcomes
  - IEEE-CIS / Vesta Fraud Detection  — transaction fraud signals
  - Give Me Some Credit               — bureau ratios
  - TransUnion / SEON enrichment      — simulated bureau + digital risk

Output: 500K rows covering:
  ✅ Applicant demographics + employment
  ✅ Bureau data (score, utilization, DTI, inquiries, delinquencies)
  ✅ SEON digital risk signals
  ✅ Mobile wallet / M-Pesa signals (KE+NG context)
  ✅ Loan terms and outcomes (paid/default/active)
  ✅ FPD flags
  ✅ Fraud labels (aligned with IEEE-CIS distributions)
  ✅ Vintage / cohort tracking
  ✅ A/B test assignments

Usage:
    python pipeline/generate_unified_data.py
    python pipeline/generate_unified_data.py --n 500000 --force
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import os
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SEED = 42
random.seed(SEED)
np.random.seed(SEED)

N_DEFAULT         = 500_000
FRAUD_RATE        = 0.038        # 3.8% — calibrated to IEEE-CIS
DEFAULT_RATE      = 0.128        # 12.8% — calibrated to Home Credit
FPD_RATE          = 0.072        # 7.2% — mobile lending benchmark
REVIEW_RATE       = 0.15         # 15% uncertain zone


# ─────────────────────────────────────────────────────────────────────────────
# Reference tables (calibrated to real datasets)
# ─────────────────────────────────────────────────────────────────────────────

COUNTRIES       = ["KE"] * 60 + ["NG"] * 40
KE_COUNTIES     = ["Nairobi","Mombasa","Kisumu","Nakuru","Eldoret","Thika",
                    "Nyeri","Machakos","Meru","Garissa","Malindi","Kisii",
                    "Kakamega","Embu","Migori","Uasin Gishu","Trans Nzoia"]
NG_STATES       = ["Lagos","Abuja","Kano","Ibadan","Port Harcourt","Benin City",
                    "Kaduna","Enugu","Owerri","Uyo","Warri","Jos","Ilorin","Aba"]
EMPLOYMENT_DIST = (["employed"]*48 + ["self_employed"]*32 +
                   ["unemployed"]*10 + ["student"]*5 + ["retired"]*5)
LOAN_PRODUCTS   = (["instant_mobile"]*35 + ["salary_advance"]*25 +
                   ["bnpl"]*15 + ["sme_loan"]*15 + ["emergency_loan"]*10)
TENURES         = [7,7,14,14,30,30,30,60,90]
CARD_TYPES      = ["debit","debit","credit","prepaid"]
CHANNELS        = ["mobile_money","mobile_money","p2p","bank_transfer",
                   "card","airtime","bill_pay"]
IP_RISKS        = ["low"]*65 + ["medium"]*25 + ["high"]*10
SOCIAL_COUNTS   = [0,1,1,2,2,3,4,5,6,7,8]
AB_TESTS        = ["ABTEST-001","ABTEST-002",None,None,None,None,None,None]
