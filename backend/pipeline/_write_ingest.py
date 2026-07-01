"""Helper: writes ingest_home_credit.py cleanly."""
import os

TARGET = os.path.join(os.path.dirname(__file__), "ingest_home_credit.py")

CODE = r'''from __future__ import annotations
import argparse, logging, os, sys, warnings
from datetime import date, datetime, timedelta
from pathlib import Path
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

SEED = 42; np.random.seed(SEED)
DATA_DIR = Path(__file__).parent.parent / "data" / "raw" / "home-credit"

INCOME_MAP = {"Working":"employed","Commercial associate":"self_employed","Pensioner":"retired",
              "State servant":"employed","Student":"student","Unemployed":"unemployed",
              "Businessman":"self_employed","Maternity leave":"employed"}
KE_COUNTIES = ["Nairobi","Mombasa","Kisumu","Nakuru","Eldoret","Thika","Nyeri","Machakos","Meru","Garissa","Malindi","Kisii"]
NG_STATES   = ["Lagos","Abuja","Kano","Ibadan","Port Harcourt","Benin City","Kaduna","Enugu","Owerri","Uyo","Warri","Jos"]
EMPLOYERS   = ["KCB Bank","Safaricom","Equity Bank","Standard Chartered","Kenya Airways","Civil Service",
               "MTN Nigeria","Dangote Group","Access Bank","GTBank","Self Employed","Freelancer","SME Owner"]
PRODUCTS    = ["instant_mobile","salary_advance","bnpl","sme_loan","emergency_loan"]
PROD_W      = [0.35, 0.25, 0.15, 0.15, 0.10]
AB_TESTS    = ["ABTEST-001","ABTEST-002",None,None,None,None]
DEVICE_FP   = [f"fp_{i:06x}" for i in range(800)]
CZK_TO_KES  = 4.2

def tu_grade(s): return "A" if s>=750 else "B" if s>=700 else "C" if s>=650 else "D" if s>=600 else "E"
def pd_from_score(s): return float(1/(1+np.exp(2.5*(s-575)/100)))

def load_bureau():
    logger.info("[1] bureau.csv...")
    b = pd.read_csv(DATA_DIR/"bureau.csv")
    a = b.groupby("SK_ID_CURR").agg(
        bureau_total_accounts=("SK_ID_BUREAU","count"),
        bureau_active_accounts=("CREDIT_ACTIVE", lambda x:(x=="Active").sum()),
        bureau_closed_accounts=("CREDIT_ACTIVE", lambda x:(x=="Closed").sum()),
        bureau_days_overdue_max=("CREDIT_DAY_OVERDUE","max"),
        bureau_total_debt=("AMT_CREDIT_SUM_DEBT","sum"),
        bureau_total_credit=("AMT_CREDIT_SUM","sum"),
        bureau_months_history=("DAYS_CREDIT", lambda x:int(abs(x.min())/30)),
    ).reset_index()
    a["bureau_debt_ratio"] = (a["bureau_total_debt"]/(a["bureau_total_credit"].clip(lower=1))).clip(0,3)
    a["bureau_delinquent_accounts"] = (a["bureau_days_overdue_max"]>0).astype(int)
    logger.info("    %d rows -> %d applicants", len(b), len(a))
    return a

def load_prev():
    logger.info("[2] previous_application.csv...")
    p = pd.read_csv(DATA_DIR/"previous_application.csv",
                    usecols=["SK_ID_CURR","NAME_CONTRACT_STATUS","AMT_CREDIT","DAYS_DECISION"])
    a = p.groupby("SK_ID_CURR").agg(
        prev_total_apps=("SK_ID_CURR","count"),
        prev_approved=("NAME_CONTRACT_STATUS", lambda x:(x=="Approved").sum()),
        prev_refused=("NAME_CONTRACT_STATUS", lambda x:(x=="Refused").sum()),
    ).reset_index()
    logger.info("    %d rows -> %d applicants", len(p), len(a))
    return a

def load_inst():
    logger.info("[3] installments_payments.csv...")
    i = pd.read_csv(DATA_DIR/"installments_payments.csv",
                    usecols=["SK_ID_CURR","DAYS_INSTALMENT","DAYS_ENTRY_PAYMENT","AMT_INSTALMENT","AMT_PAYMENT"])
    i["dpd"] = (i["DAYS_ENTRY_PAYMENT"]-i["DAYS_INSTALMENT"]).clip(lower=0)
    a = i.groupby("SK_ID_CURR").agg(
        inst_max_dpd=("dpd","max"),
        inst_late_count=("dpd", lambda x:(x>0).sum()),
    ).reset_index()
    logger.info("    %d rows -> %d applicants", len(i), len(a))
    return a

def build_applicants(app, bur, prev, inst, n_sample):
    logger.info("[4] Merging...")
    df = app.merge(bur,on="SK_ID_CURR",how="left").merge(prev,on="SK_ID_CURR",how="left").merge(inst,on="SK_ID_CURR",how="left")
    if n_sample and n_sample < len(df):
        df = df.groupby("TARGET",group_keys=False).apply(
            lambda x: x.sample(min(len(x),max(1,int(n_sample*len(x)/len(df)))),random_state=SEED)
        ).reset_index(drop=True)
        logger.info("    Sampled %d rows", len(df))
    n = len(df); rng = np.random.default_rng(SEED)
    logger.info("[4] Vectorized for %d rows...", n)
    s = np.full(n, 575.0)
    for col in ["EXT_SOURCE_1","EXT_SOURCE_2","EXT_SOURCE_3"]:
        if col in df.columns: s += (df[col].fillna(0.5).values-0.5)*120
    income_v = df["AMT_INCOME_TOTAL"].fillna(30000).clip(lower=1).values
    s += np.minimum(np.log1p(income_v/50000)*20, 40)
    age_v = (df["DAYS_BIRTH"].abs().fillna(10000)/365).clip(18,70).values
    s += np.minimum((age_v-25)*1.2, 30)
    s -= np.minimum(df["bureau_days_overdue_max"].fillna(0).values*0.5, 80)
    s -= df["bureau_debt_ratio"].fillna(0.3).values*40
    scores = np.clip(s+rng.normal(0,15,n), 300, 850).astype(int)
    incomes = (income_v*CZK_TO_KES).clip(5000, 2_000_000)
    util_v = df["bureau_debt_ratio"].fillna(0.3).clip(0,1).values
    delinq_v = df["bureau_delinquent_accounts"].fillna(0).astype(int).values
    debt_v = (df["bureau_total_debt"].fillna(0)*CZK_TO_KES).values
    lim_v = (df["bureau_total_credit"].fillna(1)*CZK_TO_KES).clip(1).values
    hist_v = df["bureau_months_history"].fillna(12).clip(0,480).astype(int).values
    inq_v = df["prev_refused"].fillna(0).clip(0,15).astype(int).values
    dti_v = (debt_v/(incomes*12+1)).clip(0,3)
    overdue_v = df["bureau_days_overdue_max"].fillna(0).values
    ctry_v = rng.choice(["KE","NG"],n,p=[0.6,0.4])
    county_v = np.where(ctry_v=="KE", rng.choice(KE_COUNTIES,n), rng.choice(NG_STATES,n))
    emp_v = df["NAME_INCOME_TYPE"].map(INCOME_MAP).fillna("employed").values
    gender_v = df["CODE_GENDER"].map({"M":"M","F":"F"}).fillna("M").values
    pd_v = 1/(1+np.exp(2.5*(scores-575)/100))
    seon_v = np.clip(pd_v*80+rng.normal(0,8,n), 2, 98).astype(int)
    prev_cnt = df["prev_total_apps"].fillna(0).clip(0,50).astype(int).values
    inst_dpd_v = df["inst_max_dpd"].fillna(0).values
    names_f = ["James","Mary","John","Grace","Peter","Faith","David","Ruth","Samuel","Joyce","Emeka","Ngozi","Chidi","Amaka"]
    names_l = ["Kamau","Wanjiku","Mwangi","Kariuki","Adesanya","Okafor","Ibrahim","Nwosu","Adeleke","Mutua","Njoroge","Otieno"]
    fn_v=rng.integers(0,len(names_f),n); ln_v=rng.integers(0,len(names_l),n); em_v=rng.integers(0,len(EMPLOYERS),n)
    b_install=date(2018,1,1); b_create=date(2019,1,1)
    inst_off=rng.integers(0,(date(2024,1,1)-b_install).days,n)
    crea_off=rng.integers(0,(date(2025,1,1)-b_create).days,n)
    sk_ids = df["SK_ID_CURR"].values
    logger.info("[4] Building output dataframe...")
    out = pd.DataFrame({
        "applicant_id":[f"APP-{int(x):07d}" for x in sk_ids],
        "first_name":[names_f[i] for i in fn_v],"last_name":[names_l[i] for i in ln_v],
        "national_id":[f"{'KE' if c=='KE' else 'NG'}{rng.integers(10000000,99999999)}" for c in ctry_v],
        "phone_number":[f"+{'254' if c=='KE' else '234'}{rng.integers(700000000,799999999)}" for c in ctry_v],
        "email":[f"user{int(x)}@gmail.com" for x in sk_ids],
        "age":age_v.astype(int),"gender":gender_v,"country":ctry_v,"county_province":county_v,
        "employment_status":emp_v,"employer_name":[EMPLOYERS[i] for i in em_v],
        "monthly_income_kes":np.round(incomes,2),"monthly_expenses_kes":np.round(incomes*rng.uniform(0.4,0.8,n),2),
        "tu_score":scores,"tu_grade":[tu_grade(int(s)) for s in scores],
        "total_accounts":df["bureau_total_accounts"].fillna(2).astype(int).values,
        "open_accounts":df["bureau_active_accounts"].fillna(1).astype(int).values,
        "closed_accounts":df["bureau_closed_accounts"].fillna(0).astype(int).values,
        "delinquent_accounts":delinq_v,"credit_utilization":np.round(util_v,4),
        "total_outstanding_debt":np.round(debt_v,2),"total_credit_limit":np.round(lim_v,2),
        "months_since_last_delinquency":np.where(overdue_v>0,(overdue_v/30).astype(int),None),
        "months_credit_history":hist_v,"num_hard_inquiries_12m":inq_v,
        "num_soft_inquiries_12m":rng.integers(0,6,n),"bankruptcy_flag":(rng.random(n)<0.008),
        "judgement_flag":(rng.random(n)<0.015),"active_collections":np.maximum(0,delinq_v-1),
        "debt_to_income":np.round(dti_v,4),"seon_fraud_score":seon_v,
        "seon_email_deliverable":(rng.random(n)>0.04),"seon_phone_valid":(rng.random(n)>0.03),
        "seon_social_match_count":rng.integers(0,9,n),
        "seon_ip_risk_level":rng.choice(["low","low","low","medium","medium","high"],n),
        "seon_device_fingerprint":rng.choice(DEVICE_FP,n),
        "seon_is_vpn":(rng.random(n)<0.04),"seon_is_tor":(rng.random(n)<0.005),
        "mobile_wallet_age_months":rng.integers(1,72,n),"sim_age_months":rng.integers(6,144,n),
        "mpesa_monthly_avg_in":np.round(incomes*rng.uniform(0.7,1.4,n),2),
        "mpesa_monthly_avg_out":np.round(incomes*rng.uniform(0.4,0.9,n),2),
        "mpesa_loan_history_count":prev_cnt,
        "app_install_date":[b_install+timedelta(days=int(d)) for d in inst_off],
        "created_at":[datetime.combine(b_create+timedelta(days=int(d)),datetime.min.time()) for d in crea_off],
        "_target":df["TARGET"].values.astype(int),
        "_amt_credit":df["AMT_CREDIT"].fillna(10000).values,
        "_inst_max_dpd":inst_dpd_v,
    })
    logger.info("[4] Done: %d applicants", len(out))
    return out

def build_loans(app_df):
    logger.info("[5] Building loans (vectorized)...")
    rng=np.random.default_rng(SEED+1); n=len(app_df)
    scores=app_df["tu_score"].values; targets=app_df["_target"].values
    incomes=app_df["monthly_income_kes"].values
    amt_cr=app_df["_amt_credit"].values*CZK_TO_KES
    inst_dpd=app_df["_inst_max_dpd"].values
    ctry=app_df["country"].values; seon=app_df["seon_fraud_score"].values
    pd_v=1/(1+np.exp(2.5*(scores-575)/100)); lgd_v=rng.uniform(0.30,0.75,n)
    max_amt=np.clip(np.minimum(amt_cr,incomes*3),500,500_000)
    amounts=np.round(np.clip(np.random.lognormal(np.log(np.maximum(500,max_amt*0.6)),0.4,n),500,500_000),2)
    products=rng.choice(PRODUCTS,n,p=PROD_W); currencies=np.where(ctry=="KE","KES","NGN")
    tenures=rng.choice([7,14,30,30,30,60,90],n)
    rates=np.round(np.clip(rng.normal(0.22,0.05,n),0.10,0.40),4)
    base_d=date(2019,1,1); end_d=date(2025,3,31); today=date.today()
    offsets=rng.integers(0,(end_d-base_d).days,n)
    disb_dates=[base_d+timedelta(days=int(o)) for o in offsets]
    due_dates=[d+timedelta(days=int(t)) for d,t in zip(disb_dates,tenures)]
    statuses=[]; dpds=[]; repaid_v=[]; repay_dates=[]
    for i in range(n):
        if due_dates[i]<=today:
            if targets[i]==1:
                st="default" if rng.random()<0.65 else "written_off"
                dp=int(np.clip(rng.integers(7,120),7,180))
                rp=round(float(amounts[i]*rng.uniform(0,0.5)),2); rd=None
            else:
                st="default" if (inst_dpd[i]>30 and rng.random()<0.3) else "paid"
                dp=0; rp=round(float(amounts[i]*(1+rates[i]*tenures[i]/365)),2)
                rd=due_dates[i]+timedelta(days=int(rng.integers(0,8)))
        else:
            st="active"; dp=max(0,(today-due_dates[i]).days) if today>due_dates[i] else 0
            rp=0.0; rd=None
        statuses.append(st); dpds.append(dp); repaid_v.append(rp); repay_dates.append(rd)
    el_v=np.round(pd_v*lgd_v*amounts,2)
    yms=[d.strftime("%Y-%m") for d in disb_dates]
    qs=[f"{d.year}-Q{(d.month-1)//3+1}" for d in disb_dates]
    ab_t=rng.choice(AB_TESTS,n); ab_v=[rng.choice(["control","treatment"]) if t else None for t in ab_t]
    fraud=(seon>70)&(rng.random(n)<0.35)
    out=pd.DataFrame({
        "loan_id":[f"LN-{i+1:08d}" for i in range(n)],
        "applicant_id":app_df["applicant_id"].values,"product_type":products,
        "loan_amount":amounts,"currency":currencies,"tenure_days":tenures,
        "interest_rate":rates,"disbursement_date":disb_dates,"due_date":due_dates,
        "status":statuses,"amount_repaid":repaid_v,"repayment_date":repay_dates,
        "days_past_due":dpds,"pd_score":np.round(pd_v,4),"lgd_score":np.round(lgd_v,4),
        "ead_amount":amounts,"expected_loss":el_v,"credit_score_at_orig":scores,
        "origination_year_month":yms,"cohort":qs,"fraud_flag":fraud,
        "ab_test_id":ab_t,"ab_variant":ab_v,
        "created_at":[datetime.combine(d,datetime.min.time()) for d in disb_dates],
    })
    logger.info("[5] Done: %d loans", len(out)); return out

def persist(app_df, loan_df):
    from pipeline.db import Session, init_db
    from pipeline.credit_db import (Applicant,Loan,CreditScore,FPDRecord,
        CohortSnapshot,ABTest,DriftReport,CostAnalysisReport,init_credit_db)
    from pipeline.dummy_data import (generate_credit_scores,generate_fpd_records,
        generate_cohort_snapshots,generate_ab_tests,generate_drift_reports,generate_cost_analysis)
    init_db(); init_credit_db(); session=Session(); BATCH=3000
    try:
        logger.info("[6] Clearing old data...")
        for tbl in [CostAnalysisReport,DriftReport,CohortSnapshot,FPDRecord,CreditScore,Loan,Applicant,ABTest]:
            session.query(tbl).delete()
        session.commit()
        logger.info("[6] Inserting %d applicants...", len(app_df))
        batch=[]
        for _,r in app_df.iterrows():
            msld = r.months_since_last_delinquency
            msld_val = (int(float(msld)) if msld is not None and msld==msld else None)
            batch.append(Applicant(
                applicant_id=r.applicant_id,first_name=r.first_name,last_name=r.last_name,
                national_id=r.national_id,phone_number=r.phone_number,email=r.email,
                age=int(r.age),gender=r.gender,country=r.country,county_province=r.county_province,
                employment_status=r.employment_status,employer_name=r.employer_name,
                monthly_income_kes=float(r.monthly_income_kes),monthly_expenses_kes=float(r.monthly_expenses_kes),
                tu_score=int(r.tu_score),tu_grade=r.tu_grade,
                total_accounts=int(r.total_accounts),open_accounts=int(r.open_accounts),
                closed_accounts=int(r.closed_accounts),delinquent_accounts=int(r.delinquent_accounts),
                credit_utilization=float(r.credit_utilization),total_outstanding_debt=float(r.total_outstanding_debt),
                total_credit_limit=float(r.total_credit_limit),months_since_last_delinquency=msld_val,
                months_credit_history=int(r.months_credit_history),num_hard_inquiries_12m=int(r.num_hard_inquiries_12m),
                num_soft_inquiries_12m=int(r.num_soft_inquiries_12m),bankruptcy_flag=bool(r.bankruptcy_flag),
                judgement_flag=bool(r.judgement_flag),active_collections=int(r.active_collections),
                debt_to_income=float(r.debt_to_income),seon_fraud_score=int(r.seon_fraud_score),
                seon_email_deliverable=bool(r.seon_email_deliverable),seon_phone_valid=bool(r.seon_phone_valid),
                seon_social_match_count=int(r.seon_social_match_count),seon_ip_risk_level=r.seon_ip_risk_level,
                seon_device_fingerprint=r.seon_device_fingerprint,seon_is_vpn=bool(r.seon_is_vpn),
                seon_is_tor=bool(r.seon_is_tor),mobile_wallet_age_months=int(r.mobile_wallet_age_months),
                sim_age_months=int(r.sim_age_months),mpesa_monthly_avg_in=float(r.mpesa_monthly_avg_in),
                mpesa_monthly_avg_out=float(r.mpesa_monthly_avg_out),mpesa_loan_history_count=int(r.mpesa_loan_history_count),
                app_install_date=r.app_install_date,created_at=r.created_at,
            ))
            if len(batch)>=BATCH:
                session.bulk_save_objects(batch); session.commit()
                logger.info("    saved batch of %d", BATCH); batch=[]
        if batch: session.bulk_save_objects(batch); session.commit()
        logger.info("[6] Inserting %d loans...", len(loan_df))
        batch=[]
        for _,r in loan_df.iterrows():
            batch.append(Loan(
                loan_id=r.loan_id,applicant_id=r.applicant_id,product_type=r.product_type,
                loan_amount=float(r.loan_amount),currency=r.currency,tenure_days=int(r.tenure_days),
                interest_rate=float(r.interest_rate),disbursement_date=r.disbursement_date,
                due_date=r.due_date,status=r.status,amount_repaid=float(r.amount_repaid),
                repayment_date=r.repayment_date,days_past_due=int(r.days_past_due),
                pd_score=float(r.pd_score),lgd_score=float(r.lgd_score),ead_amount=float(r.ead_amount),
                expected_loss=float(r.expected_loss),credit_score_at_orig=int(r.credit_score_at_orig),
                origination_year_month=r.origination_year_month,cohort=r.cohort,
                fraud_flag=bool(r.fraud_flag),ab_test_id=r.ab_test_id,ab_variant=r.ab_variant,
                created_at=r.created_at,
            ))
            if len(batch)>=BATCH:
                session.bulk_save_objects(batch); session.commit()
                logger.info("    saved batch of %d", BATCH); batch=[]
        if batch: session.bulk_save_objects(batch); session.commit()
        logger.info("[6] Generating derived tables...")
        all_a=session.query(Applicant).all()
        session.bulk_save_objects(generate_credit_scores(all_a)); session.commit()
        all_l=session.query(Loan).all()
        session.bulk_save_objects(generate_fpd_records(all_l)); session.commit()
        session.bulk_save_objects(generate_cohort_snapshots(all_l)); session.commit()
        session.bulk_save_objects(generate_ab_tests()); session.commit()
        session.bulk_save_objects(generate_drift_reports()); session.commit()
        session.bulk_save_objects(generate_cost_analysis(all_l)); session.commit()
        logger.info("[6] DONE: %d applicants, %d loans", len(app_df), len(loan_df))
    except Exception as e:
        session.rollback(); import traceback; traceback.print_exc(); raise
    finally: session.close()

def run(n_sample=None, force=False):
    from pipeline.db import Session
    from pipeline.credit_db import Applicant
    s=Session()
    try: existing=s.query(Applicant).count()
    finally: s.close()
    if existing>0 and not force:
        logger.info("DB has %d applicants. Use --force to re-ingest.", existing); return
    logger.info("="*60)
    logger.info("HOME CREDIT INGESTION  sample=%s", n_sample or "ALL")
    logger.info("="*60)
    app=pd.read_csv(DATA_DIR/"application_train.csv")
    logger.info("[0] Loaded %d rows, %d cols", len(app), len(app.columns))
    bur=load_bureau(); prev=load_prev(); inst=load_inst()
    app_df=build_applicants(app,bur,prev,inst,n_sample)
    loan_df=build_loans(app_df)
    app_df=app_df.drop(columns=["_target","_amt_credit","_inst_max_dpd"],errors="ignore")
    persist(app_df,loan_df)

if __name__=="__main__":
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--sample",type=int,default=None)
    ap.add_argument("--force",action="store_true")
    args=ap.parse_args()
    run(n_sample=args.sample, force=args.force)
'''

with open(TARGET, "w", encoding="utf-8") as f:
    f.write(CODE)

print(f"Written {len(CODE)} chars to {TARGET}")
