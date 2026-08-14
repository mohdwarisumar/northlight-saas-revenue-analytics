"""
Northlight Analytics — synthetic B2B SaaS subscription data generator
------------------------------------------------------------------------
A fictional project-analytics SaaS tool, Jan 2022 - Jul 2026. Simulates
account signups, plan tier, monthly churn/upgrade/downgrade/reactivation
events, and a monthly MRR snapshot per account — the standard shape of a
real subscription billing data warehouse (think Stripe/Chargebee exports
rolled up into a mart), not a static all-time snapshot.

Realism built in:
  - Monthly new-logo growth accelerates over time (typical early-stage SaaS)
  - Churn probability varies sharply by plan tier (Starter churns much
    faster than Enterprise — the standard SaaS pattern)
  - Expansion (upgrades) and contraction (downgrades) both happen, so net
    revenue retention isn't just "100% minus churn"
  - A small reactivation trickle (churned accounts occasionally come back)
  - A pricing change event: Growth plan price increases once, contributing
    a a small anomaly in the revenue trend (real SaaS data almost always
    has at least one of these)
"""
import sqlite3
import random
import os
import numpy as np
from datetime import date, timedelta

random.seed(6521)
np.random.seed(6521)

DB_PATH = "northlight.db"
START = date(2022, 1, 1)
END = date(2026, 7, 31)

# ----------------------------------------------------------------------------
# dim_plan
# ----------------------------------------------------------------------------
dim_plan = [
    {"plan_id": 1, "plan_name": "Starter",    "tier_rank": 1, "monthly_price_gbp": 49,   "monthly_churn_base": 0.048},
    {"plan_id": 2, "plan_name": "Growth",     "tier_rank": 2, "monthly_price_gbp": 149,  "monthly_churn_base": 0.028},
    {"plan_id": 3, "plan_name": "Scale",      "tier_rank": 3, "monthly_price_gbp": 399,  "monthly_churn_base": 0.018},
    {"plan_id": 4, "plan_name": "Enterprise", "tier_rank": 4, "monthly_price_gbp": 1250, "monthly_churn_base": 0.010},
]
plan_price = {p["plan_id"]: p["monthly_price_gbp"] for p in dim_plan}
plan_churn = {p["plan_id"]: p["monthly_churn_base"] for p in dim_plan}
GROWTH_PRICE_INCREASE_DATE = date(2024, 4, 1)  # Growth plan: 149 -> 169
GROWTH_NEW_PRICE = 169

# ----------------------------------------------------------------------------
# Company name generator — original, not recognizable
# ----------------------------------------------------------------------------
name_parts_a = ["Vantage","Northlane","Brightfield","Cobalt","Ember","Fenwick","Halcyon","Ironwood",
                 "Juniper","Kestrel","Lumen","Meridian","Nimbus","Onyx","Parallax","Quill","Ridgeline",
                 "Sable","Trailhead","Undercroft","Vellum","Westgate","Yarrow","Zenith","Anchorpoint",
                 "Bramblewood","Crestline","Driftwood","Elmcourt","Foxglove"]
name_parts_b = ["Systems","Labs","Analytics","Works","Group","Partners","Studio","Digital","Solutions",
                 "Technologies","Collective","Ventures","Data","Software","Networks"]
industries = ["SaaS / Software", "E-commerce", "Financial Services", "Healthcare", "Manufacturing",
              "Media & Publishing", "Professional Services", "Logistics", "Education", "Nonprofit",
              "Real Estate", "Hospitality"]
industry_weights = [0.22, 0.13, 0.10, 0.08, 0.09, 0.06, 0.12, 0.06, 0.05, 0.03, 0.04, 0.02]
company_sizes = ["1-10", "11-50", "51-200", "201-500", "501-1000", "1000+"]
size_weights = [0.20, 0.32, 0.26, 0.13, 0.06, 0.03]
countries = ["United Kingdom", "United States", "Ireland", "Germany", "Netherlands", "Canada", "Australia", "France"]
country_weights = [0.44, 0.22, 0.08, 0.08, 0.06, 0.05, 0.04, 0.03]
channels = ["Self-serve: Organic", "Self-serve: Paid Search", "Sales-assisted: Outbound", "Sales-assisted: Partner", "Self-serve: Referral"]
channel_weights = [0.28, 0.20, 0.22, 0.13, 0.17]

used_company_names = set()
def gen_company_name():
    for _ in range(20):
        n = f"{random.choice(name_parts_a)} {random.choice(name_parts_b)}"
        if n not in used_company_names:
            used_company_names.add(n)
            return n
    return f"{random.choice(name_parts_a)} {random.choice(name_parts_b)} {random.randint(2,99)}"

# ----------------------------------------------------------------------------
# Monthly new-signup volume (accelerating growth, with noise)
# ----------------------------------------------------------------------------
months = []
m = date(START.year, START.month, 1)
while m <= END:
    months.append(m)
    m = (m.replace(day=28) + timedelta(days=4)).replace(day=1)

def new_signups_this_month(month, idx):
    base = 14 + idx * 0.55  # grows from ~14/mo to ~45/mo by month 55
    noise = np.random.normal(1.0, 0.18)
    if month.month in (12, 1):  # holiday slowdown
        noise *= 0.75
    return max(int(round(base * max(noise, 0.3))), 3)

plan_signup_weights = [0.52, 0.31, 0.13, 0.04]  # Starter, Growth, Scale, Enterprise

# ----------------------------------------------------------------------------
# Simulate accounts + monthly MRR
# ----------------------------------------------------------------------------
accounts = {}   # account_id -> dict of static attrs
account_state = {}  # account_id -> {'plan_id':..., 'status':'active'/'churned', 'mrr':...}
mrr_snapshots = []   # rows for fact_mrr_monthly
events = []          # rows for fact_subscription_event
account_id_counter = 1
event_id_counter = 1

for idx, month in enumerate(months):
    # ---- new signups this month ----
    n_new = new_signups_this_month(month, idx)
    for _ in range(n_new):
        aid = account_id_counter; account_id_counter += 1
        plan_id = int(np.random.choice([1,2,3,4], p=plan_signup_weights))
        channel = str(np.random.choice(channels, p=channel_weights))
        signup_day = random.randint(1, 28)
        signup_date = date(month.year, month.month, signup_day)
        accounts[aid] = {
            "account_id": aid,
            "company_name": gen_company_name(),
            "industry": str(np.random.choice(industries, p=industry_weights)),
            "company_size_band": str(np.random.choice(company_sizes, p=size_weights)),
            "country": str(np.random.choice(countries, p=country_weights)),
            "signup_date": signup_date.isoformat(),
            "acquisition_channel": channel,
        }
        account_state[aid] = {"plan_id": plan_id, "status": "active", "months_active": 0, "months_since_upgrade": 0}
        price = GROWTH_NEW_PRICE if (plan_id == 2 and month >= GROWTH_PRICE_INCREASE_DATE) else plan_price[plan_id]
        events.append({"event_id": event_id_counter, "account_id": aid, "event_date": signup_date.isoformat(),
                        "event_type": "New", "from_plan_id": None, "to_plan_id": plan_id, "mrr_delta": price})
        event_id_counter += 1

    # ---- process existing active accounts for churn / upgrade / downgrade ----
    active_ids = [aid for aid, st in account_state.items() if st["status"] == "active"]
    for aid in active_ids:
        st = account_state[aid]
        # skip accounts that just signed up this exact month (already have their New event / MRR row added below)
        if st["months_active"] == 0:
            pass
        plan_id = st["plan_id"]
        churn_p = plan_churn[plan_id] * (1.4 if st["months_active"] < 2 else 1.0) * (0.7 if st["months_active"] > 24 else 1.0)
        roll = random.random()
        event_date = date(month.year, month.month, min(random.randint(1,28), 28))
        if st["months_active"] > 0 and roll < churn_p:
            price = GROWTH_NEW_PRICE if (plan_id == 2 and month >= GROWTH_PRICE_INCREASE_DATE) else plan_price[plan_id]
            events.append({"event_id": event_id_counter, "account_id": aid, "event_date": event_date.isoformat(),
                            "event_type": "Churn", "from_plan_id": plan_id, "to_plan_id": None, "mrr_delta": -price})
            event_id_counter += 1
            st["status"] = "churned"
            st["churned_month_idx"] = idx
            continue
        elif st["months_active"] > 2:
            upgrade_p = 0.020 if plan_id < 4 else 0.0
            downgrade_p = 0.009 if plan_id > 1 else 0.0
            r2 = random.random()
            if r2 < upgrade_p:
                old_plan = plan_id
                new_plan = plan_id + 1
                old_price = GROWTH_NEW_PRICE if (old_plan == 2 and month >= GROWTH_PRICE_INCREASE_DATE) else plan_price[old_plan]
                new_price = GROWTH_NEW_PRICE if (new_plan == 2 and month >= GROWTH_PRICE_INCREASE_DATE) else plan_price[new_plan]
                events.append({"event_id": event_id_counter, "account_id": aid, "event_date": event_date.isoformat(),
                                "event_type": "Upgrade", "from_plan_id": old_plan, "to_plan_id": new_plan,
                                "mrr_delta": new_price - old_price})
                event_id_counter += 1
                st["plan_id"] = new_plan
                st["months_since_upgrade"] = 0
            elif r2 < upgrade_p + downgrade_p:
                old_plan = plan_id
                new_plan = plan_id - 1
                old_price = GROWTH_NEW_PRICE if (old_plan == 2 and month >= GROWTH_PRICE_INCREASE_DATE) else plan_price[old_plan]
                new_price = GROWTH_NEW_PRICE if (new_plan == 2 and month >= GROWTH_PRICE_INCREASE_DATE) else plan_price[new_plan]
                events.append({"event_id": event_id_counter, "account_id": aid, "event_date": event_date.isoformat(),
                                "event_type": "Downgrade", "from_plan_id": old_plan, "to_plan_id": new_plan,
                                "mrr_delta": new_price - old_price})
                event_id_counter += 1
                st["plan_id"] = new_plan

    # ---- small reactivation trickle among churned accounts ----
    churned_ids = [aid for aid, st in account_state.items() if st["status"] == "churned" and idx - st.get("churned_month_idx", -99) >= 2]
    for aid in churned_ids:
        if random.random() < 0.012:
            st = account_state[aid]
            plan_id = st["plan_id"]  # reactivate at same plan they left on
            price = GROWTH_NEW_PRICE if (plan_id == 2 and month >= GROWTH_PRICE_INCREASE_DATE) else plan_price[plan_id]
            event_date = date(month.year, month.month, min(random.randint(1,28), 28))
            events.append({"event_id": event_id_counter, "account_id": aid, "event_date": event_date.isoformat(),
                            "event_type": "Reactivation", "from_plan_id": None, "to_plan_id": plan_id, "mrr_delta": price})
            event_id_counter += 1
            st["status"] = "active"
            st["months_active"] = 0

    # ---- snapshot MRR for all active accounts this month ----
    for aid, st in account_state.items():
        if st["status"] == "active":
            plan_id = st["plan_id"]
            price = GROWTH_NEW_PRICE if (plan_id == 2 and month >= GROWTH_PRICE_INCREASE_DATE) else plan_price[plan_id]
            mrr_snapshots.append({"account_id": aid, "period": month.strftime("%Y-%m"), "plan_id": plan_id, "mrr": price})
            st["months_active"] += 1

n_accounts = len(accounts)
n_active_end = sum(1 for st in account_state.values() if st["status"] == "active")
print(f"Total accounts ever signed up: {n_accounts:,}")
print(f"Active at end of window: {n_active_end:,}")
print(f"Events: {len(events):,}, MRR snapshot rows: {len(mrr_snapshots):,}")

# ----------------------------------------------------------------------------
# Load into SQLite
# ----------------------------------------------------------------------------
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.executescript("""
CREATE TABLE dim_plan (
    plan_id INTEGER PRIMARY KEY, plan_name TEXT, tier_rank INTEGER, monthly_price_gbp INTEGER
);
CREATE TABLE dim_account (
    account_id INTEGER PRIMARY KEY, company_name TEXT, industry TEXT, company_size_band TEXT,
    country TEXT, signup_date TEXT, acquisition_channel TEXT
);
CREATE TABLE fact_subscription_event (
    event_id INTEGER PRIMARY KEY, account_id INTEGER, event_date TEXT, event_type TEXT,
    from_plan_id INTEGER, to_plan_id INTEGER, mrr_delta REAL,
    FOREIGN KEY (account_id) REFERENCES dim_account(account_id)
);
CREATE TABLE fact_mrr_monthly (
    account_id INTEGER, period TEXT, plan_id INTEGER, mrr REAL,
    PRIMARY KEY (account_id, period),
    FOREIGN KEY (account_id) REFERENCES dim_account(account_id),
    FOREIGN KEY (plan_id) REFERENCES dim_plan(plan_id)
);
CREATE INDEX idx_event_account ON fact_subscription_event(account_id);
CREATE INDEX idx_mrr_period ON fact_mrr_monthly(period);
CREATE INDEX idx_mrr_account ON fact_mrr_monthly(account_id);
""")

cur.executemany("INSERT INTO dim_plan VALUES (:plan_id,:plan_name,:tier_rank,:monthly_price_gbp)",
                 [{k:v for k,v in p.items() if k != 'monthly_churn_base'} for p in dim_plan])
cur.executemany("INSERT INTO dim_account VALUES (:account_id,:company_name,:industry,:company_size_band,:country,:signup_date,:acquisition_channel)",
                 list(accounts.values()))
cur.executemany("INSERT INTO fact_subscription_event VALUES (:event_id,:account_id,:event_date,:event_type,:from_plan_id,:to_plan_id,:mrr_delta)", events)
cur.executemany("INSERT INTO fact_mrr_monthly VALUES (:account_id,:period,:plan_id,:mrr)", mrr_snapshots)

conn.commit()

cur.execute("SELECT period, ROUND(SUM(mrr),0) FROM fact_mrr_monthly GROUP BY period ORDER BY period DESC LIMIT 3")
print("Latest MRR:", cur.fetchall())
conn.close()
print("Done ->", DB_PATH)
