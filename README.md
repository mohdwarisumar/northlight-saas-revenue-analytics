# Northlight Analytics — SaaS Revenue & Churn Analytics

SQL + Power BI project modeling MRR, churn, and net revenue retention for a fictional B2B project-analytics SaaS company, January 2022 through July 2026.

## Why this project

Retail and HR are the two most common Power BI portfolio topics; SaaS metrics are less common but arguably more relevant if you're targeting product, growth, or RevOps-adjacent analyst roles — and they force you to actually understand the difference between "revenue went up" and "revenue went up *because of what*," which is a genuinely different (and harder) analytical skill than a straightforward sales report. I built this with an event-sourced subscription model — a log of every signup/upgrade/downgrade/churn/reactivation — rather than a static end-state table, because that's what lets you build the MRR waterfall, which is the chart every SaaS business actually reports on.

## The business questions

- Is MRR growing, and how much of that growth is new customers vs. expansion from existing ones?
- What's net revenue retention, and is it above or below the 100% line that separates "growing even without new sales" from "leaky bucket"?
- Where is churn concentrated — which plan tiers, which acquisition channels?
- How long does it typically take an account to expand to a higher plan?
- Which customers and industries make up the revenue base, and how concentrated is that risk?

## Data model

```
dim_plan ──┐
           ├── fact_mrr_monthly (snapshot: one row per account per month)
dim_account┘
           └── fact_subscription_event (transaction log: one row per event)
```

1,506 accounts signed up over the window; 911 are still active as of July 2026. The event log holds 2,804 events (New, Upgrade, Downgrade, Churn, Reactivation) and the monthly snapshot has 23,437 rows. Four plan tiers: Starter (£49/mo) through Enterprise (£1,250/mo), with a modeled price increase on the Growth plan partway through the dataset (£149 → £169 from April 2024) — a small deliberate anomaly, because real pricing history almost always has at least one of these and it's worth knowing how to handle in a trend query.

Full schema: `sql/01_schema.sql`.

Every analysis query sticks to core SQL — `WHERE`, aggregates, `GROUP BY`, `ORDER BY`, joins (including a self-join for the trickiest metric, NRR), `UNION`, and subqueries. No CTEs, no window functions.

## What's in this folder

```
data/generate_data.py        — the data generator
data/northlight.db           — the SQLite database
sql/01_schema.sql            — table definitions
sql/02_analysis_queries.sql  — 11 analytical queries (MRR waterfall, NRR, cohorts, etc.)
sql/03_export_csv.py         — CSV fallback for Power BI import
sql/04_views_and_maintenance.sql — keys, a CREATE VIEW example, and UPDATE/DELETE/ALTER/TRUNCATE
docs/powerbi_build_guide.md  — Power BI assembly guide, including the NRR DAX measure
                                (the trickiest one in this whole portfolio)
docs/walkthrough_and_interview_prep.md — plain-English explanation of every query + likely
                                           interview questions
docs/theme.json               — custom Power BI theme
dashboard/dashboard.html      — standalone interactive dashboard, including a real
                                 floating-bar MRR waterfall chart
```

## Findings worth calling out

MRR grew from £3.8k to £272k over 4.5 years — a ~70x increase, reasonable for an early-stage B2B SaaS company scaling from a handful of pilot customers to just under a thousand paying accounts. Net revenue retention sits at 102.6% on a trailing 12-month basis, meaning expansion revenue from existing customers is outpacing what's lost to churn and downgrades within that same group — a genuinely healthy signal, not just "revenue went up."

Logo churn (customers lost) runs consistently higher than what you'd see if you only looked at revenue churn, because Starter-tier accounts (highest churn, £49/mo) churn far more often than Enterprise accounts (lowest churn, £1,250/mo) — losing ten Starter customers barely dents MRR compared to losing one Enterprise account. This is the standard SaaS pattern where the customer-count story and the revenue story genuinely diverge, and reporting only one of them gives a misleading picture.

Accounts that ever upgrade take an average of about 13 months to do so for the first time — worth knowing if you're setting expectations for when expansion revenue should start showing up after a cohort signs up; it's not immediate.

## Reproducing it

```bash
cd data
python3 generate_data.py
```

Then run `sql/02_analysis_queries.sql` against `northlight.db`, or follow `docs/powerbi_build_guide.md`. `dashboard/dashboard.html` opens directly in a browser — no server needed.

## Honest limitations

The churn and expansion probabilities are modeled, calibrated to look like typical SaaS benchmarks (Starter churning faster than Enterprise, a healthy-but-not-extreme NRR) rather than observed from a real business. A real SaaS analytics project would also want product usage data — login frequency, feature adoption — since usage is usually the earliest and strongest predictor of churn, well before a cancellation event shows up in billing data, which is the one thing this dataset structurally can't include since there's no underlying "product" being simulated, only the billing relationship.

— Mohammad Waris
