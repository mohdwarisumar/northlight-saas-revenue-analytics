# Northlight Analytics — Power BI Build Guide

Recipe for `data/northlight.db`. This is the most DAX-heavy of the three projects in this portfolio — SaaS metrics (MRR, churn, NRR) genuinely need a few non-trivial measures, so budget more like 90 minutes if you're building it fresh.

## 1. Get the data in

Same pattern as the other two projects: **Get Data → SQLite database** (ODBC driver) pointed at `data/northlight.db`, or run `sql/03_export_csv.py` and use **Get Data → Folder**. Load `dim_plan`, `dim_account`, `fact_subscription_event`, `fact_mrr_monthly`.

## 2. Data model

```
dim_plan ──┐
           ├── fact_mrr_monthly
dim_account┘
           └── fact_subscription_event
```

`fact_mrr_monthly` is a **periodic snapshot fact** (one row per account per month, at `period` grain — a text `YYYY-MM`), which is a different shape from the transaction-level fact tables in the other two projects. `fact_subscription_event` is the transaction-level companion — every New/Upgrade/Downgrade/Churn/Reactivation event with its MRR delta. You need both: the snapshot table for "what does MRR look like right now," the event table for "how did it get there" (the waterfall chart needs the event table specifically).

Convert `fact_mrr_monthly[period]` (currently text `"2026-07"`) to a proper date for time intelligence:
```dax
Period Date = DATE(VALUE(LEFT(fact_mrr_monthly[period],4)), VALUE(RIGHT(fact_mrr_monthly[period],2)), 1)
```
Then build a **Calendar** table off that column's min/max and mark it as a date table, same as the other projects. Relate `Calendar[Date]` to `fact_mrr_monthly[Period Date]` (many-to-one) AND separately to `fact_subscription_event[event_date]` — Power BI supports both as active relationships since they're on different fact tables.

## 3. Measures

```dax
MRR = SUM(fact_mrr_monthly[mrr])

ARR = [MRR] * 12

Active Accounts = DISTINCTCOUNT(fact_mrr_monthly[account_id])

ARPA = DIVIDE([MRR], [Active Accounts])

New MRR = CALCULATE(SUM(fact_subscription_event[mrr_delta]), fact_subscription_event[event_type] = "New")

Expansion MRR = CALCULATE(SUM(fact_subscription_event[mrr_delta]), fact_subscription_event[event_type] = "Upgrade")

Contraction MRR = CALCULATE(SUM(fact_subscription_event[mrr_delta]), fact_subscription_event[event_type] = "Downgrade")

Churned MRR = CALCULATE(-SUM(fact_subscription_event[mrr_delta]), fact_subscription_event[event_type] = "Churn")

Reactivation MRR = CALCULATE(SUM(fact_subscription_event[mrr_delta]), fact_subscription_event[event_type] = "Reactivation")

Net New MRR = [New MRR] + [Expansion MRR] + [Contraction MRR] - [Churned MRR] + [Reactivation MRR]

-- Logo churn: accounts churned this period / accounts active at period start
Logo Churn Rate % =
VAR ChurnedAccounts = CALCULATE(COUNTROWS(fact_subscription_event), fact_subscription_event[event_type] = "Churn")
VAR StartingAccounts = [Active Accounts]
RETURN DIVIDE(ChurnedAccounts, StartingAccounts)

Revenue Churn Rate % = DIVIDE([Churned MRR], [MRR])

-- Net Revenue Retention needs a fixed 12-month-ago cohort, not a rolling filter,
-- so this one deliberately does NOT respond to arbitrary date slicing the way
-- the measures above do — it always compares to exactly 12 months prior.
NRR % =
VAR CohortMonth = DATE(YEAR(MAX(Calendar[Date])), MONTH(MAX(Calendar[Date])), 1) - 365
VAR CohortAccounts = CALCULATETABLE(VALUES(fact_mrr_monthly[account_id]), DATESINPERIOD(Calendar[Date], CohortMonth, -1, MONTH))
VAR CohortBaseMRR = CALCULATE(SUM(fact_mrr_monthly[mrr]), DATESINPERIOD(Calendar[Date], CohortMonth, -1, MONTH))
VAR CohortNowMRR =
    CALCULATE(
        SUM(fact_mrr_monthly[mrr]),
        FILTER(ALL(fact_mrr_monthly), fact_mrr_monthly[account_id] IN CohortAccounts),
        fact_mrr_monthly[period] = FORMAT(MAX(Calendar[Date]), "YYYY-MM")
    )
RETURN DIVIDE(CohortNowMRR, CohortBaseMRR)
```

The `NRR %` measure is the one worth understanding rather than copy-pasting blindly: it fixes a cohort (accounts active exactly 12 months before the selected date), then asks "how much MRR is that *same set of accounts* generating now" — including zero from anyone who's since churned. That's what makes NRR > 100% meaningful: it says expansion from the survivors outweighs churn and contraction, and it's why it's the single most-watched SaaS metric in the report.

## 4. Report pages

### Page 1 — Revenue Overview
- Cards: **MRR**, **ARR**, **NRR %**, **Logo Churn Rate %**, **Active Accounts**
- Line chart: MRR over time
- **Waterfall chart** (Power BI's native waterfall visual): New MRR, Expansion MRR, Contraction MRR (negative), Churned MRR (negative), Reactivation MRR, Net New MRR as the total — this is the single most important visual in the report and the one that actually demonstrates you understand SaaS metrics beyond "revenue went up"
- Slicer: Period range

### Page 2 — Churn & Retention
- Line: Logo churn rate % and Revenue churn rate % over time (two lines, same 0-100% axis — fine, not a dual-axis violation since both are percentages on the same scale)
- Bar: Churn rate by acquisition channel — a genuinely actionable "which channel brings customers who stick" chart
- Cohort retention heatmap/matrix: cohort month (rows) × months-since-signup (columns), % retained — build from SQL query #8 imported as a table, since the recursive date-math is much easier to keep in SQL than to replicate in DAX
- KPI: Average time-to-first-upgrade

### Page 3 — Accounts & Segments
- Table: Top 15 accounts by current MRR (query #9) — a genuine "who are our most important customers" list, the kind of thing a CS or account management team would actually use
- Stacked bar: MRR by industry
- Stacked bar: Plan mix over time (Starter/Growth/Scale/Enterprise as % of accounts) — shows whether the business is moving upmarket

## 5. Formatting

Theme `docs/theme.json` — a cooler, more "product/tech" palette than the other two projects (teal/indigo) rather than reusing the retail or finance color schemes. Use the waterfall visual's built-in increase/decrease/total color roles rather than fighting them with a custom theme override — waterfall charts read better when they stick to convention (green up, red down) even in an otherwise custom-themed report.
