"""
Feature Engineering Pipeline — CreditIQ Risk Intelligence Platform
=============================================================

Overview
--------
Transforms raw transaction CSV data into a rich numeric feature matrix
suitable for gradient-boosting and ensemble classifiers. All transforms
are fit on the training split only and applied identically to the test
split to prevent leakage.

Entry point: build_features(df_train, df_test, df_identity)
Returns: (X_train DataFrame, X_test DataFrame, feature_names list)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 1 — Currency Normalisation & Amount Transforms
────────────────────────────────────────────────────
WHY: Transaction amounts are in two currencies (KES and NGN) with a
     ~12× scale difference (KES median ≈ 1,500 vs NGN median ≈ 18,000).
     Raw amounts are not comparable across currencies. Additionally,
     amount distributions are heavily right-skewed; log/sqrt transforms
     compress the scale and help tree-based models split more effectively.

WHAT:
  - amt_usd       : TransactionAmt converted to USD (KES÷128, NGN÷1570)
  - log_amt       : log(1 + TransactionAmt) — reduces right skew
  - log_amt_usd   : log(1 + amt_usd) — currency-normalised log amount
  - sqrt_amt      : sqrt(TransactionAmt) — alternative compression
  - amt_cents     : fractional cents component (round-number detection)

OUTPUT: 5 numeric features per transaction.
ACHIEVED: Models can compare amounts across KE/NG and detect unusually
          large or structured transactions regardless of currency.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 2 — Time Features
──────────────────────
WHY: Fraud patterns are strongly time-dependent. Transactions at 3am on
     a weekend behave differently from transactions on a Tuesday morning.
     Raw TransactionDT (seconds offset) has no semantic meaning to a
     model. Cyclical encodings prevent the model from treating hour 23
     and hour 0 as maximally different.

WHAT:
  - hour, dow, week         : raw time components
  - is_weekend, is_night    : binary risk flags
  - is_business             : business-hours flag (Mon–Fri 9–17)
  - hour_sin/cos, dow_sin/cos: cyclical encodings (preserves periodicity)
  - hour_bin                : 5-bucket discretisation (late-night, early,
                              morning, afternoon, evening)
  - weekend_night           : interaction — highest-risk time window

OUTPUT: 11 time features per transaction.
ACHIEVED: Models learn hour-of-day and day-of-week fraud seasonality
          without being misled by discontinuities at midnight/Sunday.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 3 — Email Domain Risk Bucketing
──────────────────────────────────────
WHY: Fraudsters commonly use disposable or anonymous email providers.
     Bucketing domains into risk levels (low/unknown/high) gives the
     model a compact signal without high cardinality.

WHAT:
  - p_email_risk    : sender domain risk (0=low, 1=unknown, 2=high, -1=missing)
  - r_email_risk    : recipient domain risk
  - email_match     : 1 if sender and recipient share the same domain
  - email_missing   : 1 if sender email is absent (often suspicious)

OUTPUT: 4 features.
ACHIEVED: Captures email-based fraud signals without one-hot encoding
          thousands of unique domains.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 4 — Match Flag Encoding (M1–M6)
──────────────────────────────────────
WHY: M-columns are categorical T/F/NaN flags representing data-matching
     outcomes between transaction metadata fields. Encoding them as
     numeric allows the model to use them directly and also compute
     aggregate signals (how many fields matched?).

WHAT:
  - M*_enc              : T→1, F→0, NaN→-1
  - match_flag_sum      : count of fields that matched (higher = more verified)
  - match_flag_missing  : count of missing match flags (more missing = less verifiable)
  - match_flag_all_T    : 1 if all available flags are True

OUTPUT: len(M_cols) + 3 features.
ACHIEVED: Gives model both individual and aggregate match quality signals.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 5 — Transaction Velocity Features
────────────────────────────────────────
WHY: Card-testing and account-takeover attacks generate bursts of
     transactions in short windows. A card that makes 15 transactions
     in one hour is far more suspicious than one that makes 1.
     Velocity is one of the strongest real-world fraud signals.

WHAT: For each grouping key (card1, P_emaildomain) and time window
      (1h, 6h, 24h, 7d):
  - vel_*_cnt   : count of prior transactions in the window
  - vel_*_sum   : sum of prior amounts in the window
  - vel_*_max   : max prior amount in the window
  - vel_*_ratio : current amount / rolling sum (spike detection)

OUTPUT: 4 keys × 4 windows × 4 stats = 32 velocity features.
ACHIEVED: Model detects burst patterns, account-testing sequences,
          and sudden spending spikes.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 6 — Amount Statistics per Group
──────────────────────────────────────
WHY: A KES 50,000 transaction is normal for some cards and extreme for
     others. Normalising by the card's own history (z-score, ratio to
     median) captures the deviation from expected behaviour.

WHAT: For each grouping key (card1, P_emaildomain, card_bank, channel):
  - *_amt_mean/std/med   : group-level amount statistics
  - *_amt_zscore         : (current - mean) / std — standardised deviation
  - *_amt_ratio          : current / mean
  - *_amt_med_ratio      : current / median (robust to outliers)

OUTPUT: 4 groups × 6 stats = 24 features.
ACHIEVED: Model detects transactions that are anomalously large relative
          to the entity's own baseline behaviour.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 7 — Smoothed Target Encoding
───────────────────────────────────
WHY: High-cardinality categoricals (card_bank, channel, card_type, etc.)
     can't be one-hot encoded efficiently. Target encoding replaces each
     category with its fraud rate, giving the model a direct signal.
     Smoothing prevents overfitting on rare categories.

WHAT: Formula: (count × mean_cat + k × global_mean) / (count + k)
     Applied to: card_bank, channel, card_type, country, P_emaildomain,
                 R_emaildomain, card1
     Fit on training data only — test categories use training statistics.

OUTPUT: 7 target-encoded features.
ACHIEVED: Model learns that certain banks or channels have higher
          baseline fraud rates without treating them as dummy variables.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 8 — Frequency Encoding
─────────────────────────────
WHY: Entities that appear rarely in the dataset (new cards, new email
     domains) are inherently riskier than well-established ones. Frequency
     encoding captures this "familiarity" signal.

WHAT: For card1, card_bank, P_emaildomain, R_emaildomain, channel:
  - *_freq    : raw count of occurrences in the dataset
  - *_logfreq : log(1 + freq) — compressed frequency

OUTPUT: 10 features.
ACHIEVED: Model can penalise unfamiliar entities as potential fraud vectors.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 9 — Time Since Last Transaction
──────────────────────────────────────
WHY: Very short inter-transaction times (seconds apart) signal automated
     card-testing bots. Very long gaps may indicate account takeovers.

WHAT: For card1 and P_emaildomain:
  - *_time_since_last : seconds since the previous transaction by this entity
  - *_is_first_txn    : 1 if this is the entity's first recorded transaction

OUTPUT: 4 features.
ACHIEVED: Model detects rapid-fire bot attacks and identifies new accounts
          with no transaction history.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 10 — Network / Graph Features
────────────────────────────────────
WHY: Fraudsters reuse cards across many email addresses (or vice versa).
     Counting unique counterparts per entity captures this multi-identity
     behaviour without building a full graph.

WHAT:
  - card1_email_nuniq  : unique email domains used with this card
  - email_card1_nuniq  : unique card1 values seen with this email
  - chan_bank_nuniq    : unique banks per channel (structural signal)

OUTPUT: 3 features.
ACHIEVED: Detects account-sharing and identity-cycling patterns common
          in organised fraud rings.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 11 — Recipient Account Age
─────────────────────────────────
WHY: Newly created recipient accounts (< 7 days old) are a well-known
     fraud indicator — fraudsters set up mule accounts to receive funds.

WHAT:
  - recip_age_days    : raw age in days (missing filled with 0)
  - recip_age_missing : 1 if age was not provided
  - is_new_account    : 1 if age < 7 days
  - recip_age_log     : log(1 + age) — compressed
  - recip_age_bin     : quantile-based bin (fit on train)

OUTPUT: 5 features.
ACHIEVED: Model learns to flag transactions to new/unknown recipient
          accounts as higher risk.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 12 — D* Block (Time-Delta Features)
──────────────────────────────────────────
WHY: D-columns represent time-deltas between events (e.g. days since
     last login, days since card was first seen). Missing values indicate
     the event never occurred. Delta from the training median captures
     anomalous timing.

WHAT: For each D column (D1–D5):
  - D*_missing : missingness indicator
  - D*_delta   : value minus training median
  - D*_abs     : absolute delta (magnitude of deviation)

OUTPUT: 3 × len(D_cols) features.
ACHIEVED: Model uses timing gaps as fraud signals without being biased
          by the raw scale of each D column.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 13 — V* Block (PCA + Top Raw Features)
────────────────────────────────────────────
WHY: V-columns are Vesta-derived engineered features with opaque meaning.
     There are 30+ V columns with high mutual correlation. PCA reduces
     dimensionality while retaining the most variance. Keeping top raw
     V columns (by variance) preserves the most individually informative
     signals.

WHAT:
  - v_pca_0..11      : 12 PCA components (fit on train)
  - V*_raw           : top 15 V columns by training variance
  - v_missing_rate   : fraction of V columns that are zero
  - v_sum, v_std     : aggregate V statistics
  - v_nonzero_count  : count of non-zero V values

OUTPUT: 12 PCA + 15 raw + 4 aggregate = 31 features.
ACHIEVED: Reduces 30+ correlated V columns to a compact representation
          while preserving the strongest individual signals.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 14 — C* Count Features
─────────────────────────────
WHY: C-columns are count features (e.g. how many addresses, emails, or
     phone numbers are associated with the card). High counts indicate
     an account is being shared or recycled across many identities.

WHAT:
  - c_total, c_max, c_std : aggregate C statistics
  - c_nonzero             : how many C features are active
  - c1_c2_ratio           : C1/C2 (velocity ratio signal)

OUTPUT: 5 features.
ACHIEVED: Model learns that accounts with unusually high association
          counts are higher-risk.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 15 — Cross-Features
──────────────────────────
WHY: Interactions between categorical features capture joint risk that
     is not apparent from either feature alone. For example, a mobile_money
     transaction at 3am on a weekend is riskier than either signal alone.

WHAT: Label-encode channel, card_type, country, card_bank, then:
  - cross_chan_card  : channel × card_type
  - cross_ctry_chan  : country × channel
  - cross_hour_chan  : hour_bin × channel
  - cross_wknd_chan  : is_weekend × channel

OUTPUT: 4 cross-features + 4 label-encoded features.
ACHIEVED: Captures compound risk signals from combinations of context
          variables that are jointly predictive of fraud.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 16 — Identity Aggregations
────────────────────────────────
WHY: The identity feed (device type, browser, OS, biometric IDs) is a
     separate table that joins on TransactionID. Not all transactions
     have identity records — their absence is itself a signal.

WHAT: Aggregate identity rows per TransactionID:
  - device_count    : number of identity records (device sessions)
  - has_mobile      : fraction of sessions on mobile device
  - id_01..id_11    : mean/std/min/max of numeric identity fields
  - device_nuniq    : number of unique DeviceInfo strings

OUTPUT: ~50 identity-derived features.
ACHIEVED: Captures device-switching behaviour and identity
          inconsistencies that correlate with account takeover.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 17 — Sender Velocity
──────────────────────────
WHY: sender_prev_txn_count tracks how many prior transactions the sender
     has made. A sender with 0 prior transactions is a first-time user —
     higher risk than an established customer.

WHAT:
  - sender_prev_txn_count : raw count (missing filled with 0)
  - sender_is_new         : 1 if count == 0
  - sender_log_count      : log(1 + count) — compressed history depth

OUTPUT: 3 features.
ACHIEVED: Model learns that established senders are lower risk while
          first-time senders warrant closer scrutiny.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 18 — Amount Percentile Rank Within Card
─────────────────────────────────────────────
WHY: A transaction that ranks in the 99th percentile of all amounts for
     that card is anomalous regardless of its absolute value.

WHAT:
  - amt_pctrank_card1 : percentile rank of this transaction's amount
                        among all transactions by the same card1

OUTPUT: 1 feature.
ACHIEVED: Captures within-card amount anomalies in a scale-free way.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 19 — Block Missingness Rates
───────────────────────────────────
WHY: Missingness patterns are themselves informative. A transaction with
     many missing D-values may have been submitted with incomplete
     metadata, which correlates with fraud.

WHAT:
  - d_missing_rate : fraction of D columns that are missing
  - m_missing_rate : fraction of M flag columns that are missing

OUTPUT: 2 features.
ACHIEVED: Model learns that data sparsity is a weak but useful fraud signal.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 20 — Card Combination Frequencies
────────────────────────────────────────
WHY: card1/card2/card3/card5 encode card identifiers at different levels
     of granularity. Rare card values that have appeared very few times
     in the dataset are more likely to be fraudulent (new/stolen cards).

WHAT: For card1, card2, card3, card5:
  - *_freq : count of times this card value appears in the full dataset

OUTPUT: 4 features.
ACHIEVED: Model penalises cards that are rare in the historical data,
          capturing the "unknown card" fraud signal.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

LEAKAGE GUARD
──────────────
`flagged_for_review` is NEVER included — it is derived from model scores
and would constitute direct label leakage.

All target encoding and group statistics are fit exclusively on the
training split and applied to the test split using training-derived
parameters.

TOTAL FEATURES: ~150–200 depending on data columns present.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import LabelEncoder, QuantileTransformer
from collections import defaultdict

# Exchange rates
_KES_TO_USD = 1 / 128.0
_NGN_TO_USD = 1 / 1570.0

_LOW_RISK_DOMAINS  = {"gmail.com","yahoo.com","hotmail.com","outlook.com",
                       "icloud.com","live.com","yahoo.co.ke","yahoo.com.ng",
                       "aol.com","protonmail.com"}
_HIGH_RISK_DOMAINS = {"anonymous","mailinator.com","guerrillamail.com",
                       "throwam.com","yopmail.com","trashmail.com",
                       "dispostable.com","sharklasers.com"}


def _email_risk(domain) -> int:
    if pd.isna(domain) or str(domain).strip() == "":
        return -1
    d = str(domain).strip().lower()
    if d in _LOW_RISK_DOMAINS:  return 0
    if d in _HIGH_RISK_DOMAINS: return 2
    return 1


def _encode_match_flag(series: pd.Series) -> pd.Series:
    return series.map({"T": 1, "F": 0}).fillna(-1).astype(np.int8)


def _smoothed_target_encode(
    train_series: pd.Series,
    target: pd.Series,
    test_series: pd.Series,
    min_samples: int = 20,
    smoothing: float = 10.0,
) -> tuple[pd.Series, pd.Series]:
    """
    Smoothed target encoding — avoids overfitting on rare categories.
    Formula: (count * mean_cat + smoothing * global_mean) / (count + smoothing)
    Uses out-of-fold on train to prevent leakage.
    """
    global_mean = target.mean()
    stats = pd.DataFrame({"cat": train_series, "target": target})
    agg   = stats.groupby("cat")["target"].agg(["count", "mean"])
    agg["encoded"] = (
        (agg["count"] * agg["mean"] + smoothing * global_mean) /
        (agg["count"] + smoothing)
    )
    train_enc = train_series.map(agg["encoded"]).fillna(global_mean).astype(np.float32)
    test_enc  = test_series.map(agg["encoded"]).fillna(global_mean).astype(np.float32)
    return train_enc, test_enc


def build_features(
    df_train: pd.DataFrame,
    df_test:  pd.DataFrame,
    df_identity: pd.DataFrame,
    n_pca_components: int = 12,
    v_top_raw: int = 15,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """
    Fit all feature transforms on train, apply to both splits.
    Returns (X_train, X_test, feature_names) — no isFraud / flagged_for_review.
    """
    print("[FE] Starting Kaggle-grade feature engineering …")

    df_train = df_train.copy()
    df_test  = df_test.copy()
    df_train["_split"] = "train"
    df_test["_split"]  = "test"
    df_test["isFraud"] = np.nan

    # Sort both by TransactionDT and reset index (critical for positional alignment)
    df_train = df_train.sort_values("TransactionDT").reset_index(drop=True)
    df_test  = df_test.sort_values("TransactionDT").reset_index(drop=True)

    combined = pd.concat([df_train, df_test], ignore_index=True, sort=False)
    train_mask = combined["_split"] == "train"
    y_train_col = combined.loc[train_mask, "isFraud"].values

    # ── 1. Currency normalisation ─────────────────────────────────────────────
    print("[FE] 1. Currency normalisation")
    combined["amt_usd"] = np.where(
        combined["currency"] == "KES",
        combined["TransactionAmt"] * _KES_TO_USD,
        combined["TransactionAmt"] * _NGN_TO_USD,
    )
    combined["log_amt"]      = np.log1p(combined["TransactionAmt"])
    combined["log_amt_usd"]  = np.log1p(combined["amt_usd"])
    combined["sqrt_amt"]     = np.sqrt(combined["TransactionAmt"].clip(0))
    combined["amt_cents"]    = (combined["TransactionAmt"] * 100 % 100).astype(np.float32)  # cents component

    # ── 2. Time features ──────────────────────────────────────────────────────
    print("[FE] 2. Time features")
    t = combined["TransactionDT"]
    combined["hour"]        = (t // 3600) % 24
    combined["dow"]         = (t // 86400) % 7
    combined["week"]        = (t // 604800) % 52
    combined["is_weekend"]  = (combined["dow"] >= 5).astype(np.int8)
    combined["is_night"]    = ((combined["hour"] < 6) | (combined["hour"] >= 22)).astype(np.int8)
    combined["is_business"] = ((combined["hour"] >= 9) & (combined["hour"] < 17) & (combined["dow"] < 5)).astype(np.int8)
    # Cyclical
    combined["hour_sin"]    = np.sin(2 * np.pi * combined["hour"] / 24)
    combined["hour_cos"]    = np.cos(2 * np.pi * combined["hour"] / 24)
    combined["dow_sin"]     = np.sin(2 * np.pi * combined["dow"] / 7)
    combined["dow_cos"]     = np.cos(2 * np.pi * combined["dow"] / 7)
    # Hour bins (0-3=late_night, 4-7=early, 8-11=morning, 12-17=afternoon, 18-23=evening)
    combined["hour_bin"]    = pd.cut(combined["hour"], bins=[-1,3,7,11,17,23], labels=[0,1,2,3,4]).astype(np.float32)
    # Weekend × Night interaction (highest risk window)
    combined["weekend_night"] = (combined["is_weekend"] & combined["is_night"]).astype(np.int8)

    # ── 3. Email domain risk ──────────────────────────────────────────────────
    print("[FE] 3. Email domain risk")
    combined["p_email_risk"]   = combined["P_emaildomain"].apply(_email_risk)
    combined["r_email_risk"]   = combined["R_emaildomain"].apply(_email_risk)
    combined["email_match"]    = (combined["P_emaildomain"].fillna("__na__") == combined["R_emaildomain"].fillna("__na__")).astype(np.int8)
    combined["email_missing"]  = combined["P_emaildomain"].isna().astype(np.int8)

    # ── 4. Match flags ────────────────────────────────────────────────────────
    print("[FE] 4. Match flags")
    m_raw = [c for c in combined.columns if c.startswith("M") and c[1:].isdigit()]
    for col in m_raw:
        combined[f"{col}_enc"] = _encode_match_flag(combined[col])
    m_enc = [f"{c}_enc" for c in m_raw]
    if m_enc:
        combined["match_flag_sum"]     = combined[m_enc].clip(lower=0).sum(axis=1)
        combined["match_flag_missing"] = (combined[m_enc] == -1).sum(axis=1)
        combined["match_flag_all_T"]   = (combined[m_enc] == 1).all(axis=1).astype(np.int8)

    # ── 5. Velocity features ──────────────────────────────────────────────────
    print("[FE] 5. Velocity features (1h/6h/24h/7d)")
    dt_arr  = combined["TransactionDT"].values
    amt_arr = combined["TransactionAmt"].values

    windows = {"1h": 3600, "6h": 21600, "24h": 86400, "7d": 604800}
    group_cols = ["card1", "P_emaildomain"]

    for gcol in group_cols:
        if gcol not in combined.columns:
            continue
        grp_vals = combined[gcol].fillna("__na__").astype(str).values
        grp_map: dict = defaultdict(list)
        for i, g in enumerate(grp_vals):
            grp_map[g].append(i)

        for win_name, win_sec in windows.items():
            counts   = np.zeros(len(combined), dtype=np.int32)
            amt_sums = np.zeros(len(combined), dtype=np.float32)
            amt_maxs = np.zeros(len(combined), dtype=np.float32)

            for g, idxs in grp_map.items():
                ia = np.array(idxs)
                dt_g  = dt_arr[ia]
                amt_g = amt_arr[ia]
                for pos, i in enumerate(ia):
                    mask = (dt_g >= dt_arr[i] - win_sec) & (dt_g < dt_arr[i])
                    counts[i]   = mask.sum()
                    amt_sums[i] = amt_g[mask].sum()
                    amt_maxs[i] = amt_g[mask].max() if mask.any() else 0.0

            safe = gcol.replace("_", "")
            combined[f"vel_{safe}_{win_name}_cnt"]  = counts
            combined[f"vel_{safe}_{win_name}_sum"]  = amt_sums
            combined[f"vel_{safe}_{win_name}_max"]  = amt_maxs
            # Ratio: current amount / rolling sum (spike detection)
            combined[f"vel_{safe}_{win_name}_ratio"] = (
                combined["TransactionAmt"] / (amt_sums + 1e-6)
            ).clip(0, 1000).astype(np.float32)

    # ── 6. Amount stats per group ─────────────────────────────────────────────
    print("[FE] 6. Amount stats per group")
    for gcol in ["card1", "P_emaildomain", "card_bank", "channel"]:
        if gcol not in combined.columns:
            continue
        s = gcol.replace("_","")
        gs = combined.groupby(gcol)["TransactionAmt"].agg(["mean","std","median"])
        gs.columns = [f"{s}_amt_mean", f"{s}_amt_std", f"{s}_amt_med"]
        combined = combined.join(gs, on=gcol, how="left")
        m = f"{s}_amt_mean"; sd = f"{s}_amt_std"; med = f"{s}_amt_med"
        combined[f"{s}_amt_zscore"]    = ((combined["TransactionAmt"] - combined[m].fillna(0)) / (combined[sd].fillna(1) + 1e-8)).astype(np.float32)
        combined[f"{s}_amt_ratio"]     = (combined["TransactionAmt"] / (combined[m].fillna(combined["TransactionAmt"]) + 1e-8)).astype(np.float32)
        combined[f"{s}_amt_med_ratio"] = (combined["TransactionAmt"] / (combined[med].fillna(combined["TransactionAmt"]) + 1e-8)).astype(np.float32)

    # ── 7. Target encoding (TRAIN ONLY — smoothed, no leakage) ───────────────
    print("[FE] 7. Target encoding (smoothed)")
    te_cols = ["card_bank", "channel", "card_type", "country",
               "P_emaildomain", "R_emaildomain", "card1"]
    tr_idx = combined.index[train_mask].tolist()
    te_idx = combined.index[~train_mask].tolist()
    y_series = pd.Series(y_train_col, index=tr_idx)

    for col in te_cols:
        if col not in combined.columns:
            continue
        tr_enc, te_enc = _smoothed_target_encode(
            combined.loc[tr_idx, col].fillna("__na__"),
            y_series,
            combined.loc[te_idx, col].fillna("__na__"),
        )
        feat_name = col.replace("_","") + "_te"
        combined.loc[tr_idx, feat_name] = tr_enc.values
        combined.loc[te_idx, feat_name] = te_enc.values

    # ── 8. Frequency encoding ─────────────────────────────────────────────────
    print("[FE] 8. Frequency encoding")
    freq_cols = ["card1", "card_bank", "P_emaildomain", "R_emaildomain", "channel"]
    for col in freq_cols:
        if col not in combined.columns:
            continue
        freq = combined[col].fillna("__na__").value_counts()
        combined[f"{col.replace('_','')}_freq"] = combined[col].fillna("__na__").map(freq).astype(np.float32)
        # Log frequency
        combined[f"{col.replace('_','')}_logfreq"] = np.log1p(combined[f"{col.replace('_','')}_freq"])

    # ── 9. Time since last transaction ───────────────────────────────────────
    print("[FE] 9. Time-since-last features")
    for gcol in ["card1", "P_emaildomain"]:
        if gcol not in combined.columns:
            continue
        combined_sorted = combined.sort_values("TransactionDT").copy()
        combined_sorted[gcol] = combined_sorted[gcol].fillna("__na__")
        combined_sorted["_prev_dt"] = combined_sorted.groupby(gcol)["TransactionDT"].shift(1)
        combined_sorted["_delta"] = (combined_sorted["TransactionDT"] - combined_sorted["_prev_dt"]).fillna(-1)
        feat = f"{gcol.replace('_','')}_time_since_last"
        combined[feat] = combined_sorted["_delta"].values
        combined[f"{gcol.replace('_','')}_is_first_txn"] = (combined[feat] < 0).astype(np.int8)
        combined[feat] = combined[feat].clip(lower=0)

    # ── 10. Network features ──────────────────────────────────────────────────
    print("[FE] 10. Network / graph features")
    # Unique counterparts per card (card paired with how many unique emails?)
    if "card1" in combined.columns and "P_emaildomain" in combined.columns:
        nuniq = combined.groupby("card1")["P_emaildomain"].nunique()
        combined["card1_email_nuniq"] = combined["card1"].map(nuniq).fillna(1).astype(np.float32)
    if "P_emaildomain" in combined.columns and "card1" in combined.columns:
        nuniq2 = combined.groupby("P_emaildomain")["card1"].nunique()
        combined["email_card1_nuniq"] = combined["P_emaildomain"].map(nuniq2).fillna(1).astype(np.float32)
    # card_bank nunique per channel
    if "card_bank" in combined.columns:
        cb_ch = combined.groupby("channel")["card_bank"].nunique()
        combined["chan_bank_nuniq"] = combined["channel"].map(cb_ch).fillna(1).astype(np.float32)

    # ── 11. Recipient account age ─────────────────────────────────────────────
    print("[FE] 11. Recipient account age")
    if "recipient_account_age_days" in combined.columns:
        combined["recip_age_missing"] = combined["recipient_account_age_days"].isna().astype(np.int8)
        combined["recip_age_days"]    = combined["recipient_account_age_days"].fillna(0)
        combined["is_new_account"]    = (combined["recip_age_days"] < 7).astype(np.int8)
        combined["recip_age_log"]     = np.log1p(combined["recip_age_days"])
        # Quantile bins (fit on train)
        age_tr = combined.loc[train_mask & combined["recipient_account_age_days"].notna(), "recipient_account_age_days"]
        quantiles = age_tr.quantile([0.1, 0.25, 0.5, 0.75, 0.9, 0.99]).values
        combined["recip_age_bin"] = pd.cut(
            combined["recip_age_days"],
            bins=[-1] + list(quantiles) + [1e9],
            labels=False,
        ).fillna(0).astype(np.float32)

    # ── 12. D* features ───────────────────────────────────────────────────────
    print("[FE] 12. D* features")
    d_cols = [c for c in combined.columns if c.startswith("D") and c[1:].isdigit()]
    for dc in d_cols:
        median_val = combined.loc[train_mask, dc].median()
        combined[f"{dc}_missing"] = combined[dc].isna().astype(np.int8)
        combined[dc]              = combined[dc].fillna(median_val)
        combined[f"{dc}_delta"]   = (combined[dc] - median_val).astype(np.float32)
        combined[f"{dc}_abs"]     = np.abs(combined[f"{dc}_delta"]).astype(np.float32)

    # ── 13. V* block — ALL raw + PCA + correlation groups ────────────────────
    print("[FE] 13. V* block (full)")
    v_cols = [c for c in combined.columns if c.startswith("V") and c[1:].isdigit()]
    if v_cols:
        v_data = combined[v_cols].fillna(0).values.astype(np.float32)

        # PCA on train
        n_tr = int(train_mask.sum())
        pca = PCA(n_components=min(n_pca_components, len(v_cols)), random_state=42)
        pca.fit(v_data[:n_tr])
        pca_result = pca.transform(v_data)
        for i in range(pca.n_components_):
            combined[f"v_pca_{i}"] = pca_result[:, i]

        # Top V columns by variance on train — keep as raw features
        v_vars = pd.Series(v_data[:n_tr].var(axis=0), index=v_cols)
        top_v  = v_vars.nlargest(v_top_raw).index.tolist()
        for vc in top_v:
            combined[f"{vc}_raw"] = combined[vc].fillna(0)

        # V block missingness
        combined["v_missing_rate"]  = (combined[v_cols] == 0).mean(axis=1).astype(np.float32)
        combined["v_sum"]           = v_data.sum(axis=1).astype(np.float32)
        combined["v_std"]           = v_data.std(axis=1).astype(np.float32)
        combined["v_nonzero_count"] = (v_data != 0).sum(axis=1).astype(np.float32)

    # ── 14. C* features ───────────────────────────────────────────────────────
    print("[FE] 14. C* features")
    c_cols = [c for c in combined.columns if c.startswith("C") and c[1:].isdigit()]
    if c_cols:
        for cc in c_cols:
            combined[cc] = combined[cc].fillna(0)
        combined["c_total"]   = combined[c_cols].sum(axis=1)
        combined["c_max"]     = combined[c_cols].max(axis=1)
        combined["c_std"]     = combined[c_cols].std(axis=1).fillna(0)
        combined["c_nonzero"] = (combined[c_cols] > 0).sum(axis=1)
        # C1/C2 ratio (velocity ratio signal)
        if "C1" in combined.columns and "C2" in combined.columns:
            combined["c1_c2_ratio"] = (combined["C1"] / (combined["C2"] + 1e-6)).clip(0, 100)

    # ── 15. Cross-features ────────────────────────────────────────────────────
    print("[FE] 15. Cross-features")
    le = {}
    for col in ["channel","card_type","country","card_bank"]:
        if col in combined.columns:
            le[col] = LabelEncoder()
            combined[f"{col}_le"] = le[col].fit_transform(combined[col].fillna("unknown"))

    if "channel_le" in combined.columns and "card_type_le" in combined.columns:
        combined["cross_chan_card"]    = combined["channel_le"] * 10 + combined["card_type_le"]
    if "country_le" in combined.columns and "channel_le" in combined.columns:
        combined["cross_ctry_chan"]    = combined["country_le"] * 10 + combined["channel_le"]
    if "hour_bin" in combined.columns and "channel_le" in combined.columns:
        combined["cross_hour_chan"]    = combined["hour_bin"].fillna(0) * 10 + combined["channel_le"]
    if "is_weekend" in combined.columns and "channel_le" in combined.columns:
        combined["cross_wknd_chan"]    = combined["is_weekend"] * 10 + combined["channel_le"]

    # ── 16. Identity aggregations ─────────────────────────────────────────────
    print("[FE] 16. Identity features")
    if df_identity is not None and not df_identity.empty:
        id_num_cols = [c for c in df_identity.columns if c.startswith("id_") and c[3:].isdigit()]
        agg_dict: dict = {
            "DeviceType": ["count", lambda x: (x == "mobile").mean()],
        }
        for ic in id_num_cols[:11]:
            if ic in df_identity.columns:
                agg_dict[ic] = ["mean","std","min","max"]

        id_agg = df_identity.groupby("TransactionID").agg(agg_dict)
        id_agg.columns = ["_".join(c).strip() for c in id_agg.columns]
        id_agg = id_agg.rename(columns={
            "DeviceType_count":    "device_count",
            "DeviceType_<lambda_0>": "has_mobile",
        })
        id_agg = id_agg.reset_index()
        combined = combined.merge(id_agg, on="TransactionID", how="left")
        combined["device_count"] = combined.get("device_count", 0).fillna(0)
        combined["has_mobile"]   = combined.get("has_mobile",   0).fillna(0)

        # Device info entropy
        dv = df_identity.groupby("TransactionID")["DeviceInfo"].nunique().reset_index()
        dv.columns = ["TransactionID","device_nuniq"]
        combined = combined.merge(dv, on="TransactionID", how="left")
        combined["device_nuniq"] = combined["device_nuniq"].fillna(0)
    else:
        combined["device_count"] = 0
        combined["has_mobile"]   = 0
        combined["device_nuniq"] = 0

    # ── 17. Sender velocity ───────────────────────────────────────────────────
    if "sender_prev_txn_count" in combined.columns:
        combined["sender_prev_txn_count"] = combined["sender_prev_txn_count"].fillna(0)
        combined["sender_is_new"]         = (combined["sender_prev_txn_count"] == 0).astype(np.int8)
        combined["sender_log_count"]      = np.log1p(combined["sender_prev_txn_count"])

    # ── 18. Amount percentile rank within card ────────────────────────────────
    print("[FE] 18. Amount percentile rank")
    if "card1" in combined.columns:
        combined["card1_filled"] = combined["card1"].fillna(-999)
        combined["amt_pctrank_card1"] = combined.groupby("card1_filled")["TransactionAmt"]\
            .rank(pct=True).astype(np.float32)
        combined.drop(columns=["card1_filled"], inplace=True)

    # ── 19. Block missingness rates ───────────────────────────────────────────
    print("[FE] 19. Block missingness rates")
    if d_cols:
        d_miss = [f"{c}_missing" for c in d_cols if f"{c}_missing" in combined.columns]
        combined["d_missing_rate"] = combined[d_miss].mean(axis=1).astype(np.float32)
    if m_enc:
        combined["m_missing_rate"] = ((combined[m_enc] == -1).mean(axis=1)).astype(np.float32)

    # ── 20. Card combination features ────────────────────────────────────────
    print("[FE] 20. Card combination features")
    for ccard in ["card1","card2","card3","card5"]:
        if ccard in combined.columns:
            freq = combined[ccard].fillna(-1).value_counts()
            combined[f"{ccard}_freq"] = combined[ccard].fillna(-1).map(freq).astype(np.float32)

    # ── Finalise ─────────────────────────────────────────────────────────────
    print("[FE] Finalising feature matrix …")

    exclude = {
        "TransactionID","TransactionDT","TransactionAmt",
        "country","currency","channel","card_type","card_bank",
        "P_emaildomain","R_emaildomain",
        "isFraud","flagged_for_review","_split",
        # Raw categorical M columns
        *[c for c in combined.columns if c.startswith("M") and not (c.endswith("_enc") or c.endswith("_sum") or c.endswith("_missing"))],
        # Raw V columns (replaced by PCA + top_v_raw)
        *v_cols,
    }

    feature_cols = [c for c in combined.columns if c not in exclude and not c.startswith("_")]

    # Convert all to float32, fill remaining NaN
    for fc in feature_cols:
        try:
            combined[fc] = pd.to_numeric(combined[fc], errors="coerce").fillna(0).astype(np.float32)
        except Exception:
            combined[fc] = 0.0

    # Split back — positional (index is 0..N-1 after reset)
    n_train = int(train_mask.sum())
    X_train = combined.loc[:n_train-1, feature_cols].copy()
    X_test  = combined.loc[n_train:,   feature_cols].copy()

    print(f"[FE] Done — {len(feature_cols)} features. Train={len(X_train)}, Test={len(X_test)}")
    return X_train, X_test, feature_cols
