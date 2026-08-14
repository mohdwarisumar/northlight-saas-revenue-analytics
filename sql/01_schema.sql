CREATE TABLE dim_account (
    account_id INTEGER PRIMARY KEY, company_name TEXT, industry TEXT, company_size_band TEXT,
    country TEXT, signup_date TEXT, acquisition_channel TEXT
);
CREATE TABLE dim_plan (
    plan_id INTEGER PRIMARY KEY, plan_name TEXT, tier_rank INTEGER, monthly_price_gbp INTEGER
);
CREATE TABLE fact_mrr_monthly (
    account_id INTEGER, period TEXT, plan_id INTEGER, mrr REAL,
    PRIMARY KEY (account_id, period),
    FOREIGN KEY (account_id) REFERENCES dim_account(account_id),
    FOREIGN KEY (plan_id) REFERENCES dim_plan(plan_id)
);
CREATE TABLE fact_subscription_event (
    event_id INTEGER PRIMARY KEY, account_id INTEGER, event_date TEXT, event_type TEXT,
    from_plan_id INTEGER, to_plan_id INTEGER, mrr_delta REAL,
    FOREIGN KEY (account_id) REFERENCES dim_account(account_id)
);
CREATE INDEX idx_event_account ON fact_subscription_event(account_id);
CREATE INDEX idx_mrr_period ON fact_mrr_monthly(period);
CREATE INDEX idx_mrr_account ON fact_mrr_monthly(account_id);
