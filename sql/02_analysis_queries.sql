/* ============================================================================
   Northlight Analytics — SaaS Revenue & Churn Analytical Queries
   Database: northlight.db (SQLite)
   Author: Mohammad Waris
   ----------------------------------------------------------------------------
   Written using core SQL only: WHERE, aggregate functions, GROUP BY, HAVING,
   ORDER BY, JOINs (including a self-join), UNION, and subqueries. No CTEs
   (WITH...AS) and no window functions.
   ============================================================================ */


/* ----------------------------------------------------------------------------
   1. MRR and ARR trend by month
   Topics: aggregate functions, GROUP BY, ORDER BY
---------------------------------------------------------------------------- */
SELECT
    period,
    ROUND(SUM(mrr), 0)         AS mrr,
    ROUND(SUM(mrr) * 12, 0)    AS arr_run_rate,
    COUNT(DISTINCT account_id) AS active_accounts
FROM fact_mrr_monthly
GROUP BY period
ORDER BY period;


/* ----------------------------------------------------------------------------
   2. MRR movement waterfall: New, Expansion, Contraction, Churned, Reactivation
   This is the standard SaaS "bridge" view — how did MRR actually move each
   month, not just the net total.
   Topics: CASE, aggregate functions, GROUP BY, ORDER BY
---------------------------------------------------------------------------- */
SELECT
    STRFTIME('%Y-%m', event_date) AS period,
    CASE
        WHEN event_type = 'New' THEN 'New MRR'
        WHEN event_type = 'Reactivation' THEN 'Reactivation MRR'
        WHEN event_type = 'Upgrade' THEN 'Expansion MRR'
        WHEN event_type = 'Downgrade' THEN 'Contraction MRR'
        WHEN event_type = 'Churn' THEN 'Churned MRR'
    END AS movement_type,
    ROUND(SUM(mrr_delta), 0) AS mrr_delta
FROM fact_subscription_event
GROUP BY period, movement_type
ORDER BY period, movement_type;


/* ----------------------------------------------------------------------------
   3. Logo churn rate and revenue churn rate by month
      Logo churn    = accounts churned / accounts active at start of month
      Revenue churn = MRR lost to churn / MRR at start of month
   Topics: subquery (derived table) x2, LEFT JOIN, aggregate functions
---------------------------------------------------------------------------- */
SELECT
    m.period, m.accounts, m.mrr,
    COALESCE(c.churned_accounts, 0) AS churned_accounts,
    COALESCE(c.churned_mrr, 0)      AS churned_mrr,
    ROUND(100.0 * COALESCE(c.churned_accounts,0) / m.accounts, 2) AS logo_churn_rate_pct,
    ROUND(100.0 * COALESCE(c.churned_mrr,0) / m.mrr, 2)           AS revenue_churn_rate_pct
FROM (
    SELECT period, COUNT(DISTINCT account_id) AS accounts, SUM(mrr) AS mrr
    FROM fact_mrr_monthly
    GROUP BY period
) m
LEFT JOIN (
    SELECT STRFTIME('%Y-%m', event_date) AS period,
           COUNT(*) AS churned_accounts, ROUND(-SUM(mrr_delta), 0) AS churned_mrr
    FROM fact_subscription_event
    WHERE event_type = 'Churn'
    GROUP BY period
) c ON m.period = c.period
ORDER BY m.period;


/* ----------------------------------------------------------------------------
   4. Net Revenue Retention (NRR) — a fixed cohort (accounts active 12 months
      ago), compared to what that SAME set of accounts generates today.
      A genuine self-join: fact_mrr_monthly joined to itself, once filtered
      to 12 months ago ("base") and once to today ("now"), matched on
      account_id. Accounts that have since churned just get NULL on the
      "now" side (and count as £0 via COALESCE) — they don't disappear from
      the comparison, which is the whole point of this metric.
   Topics: self-join, WHERE, aggregate functions
---------------------------------------------------------------------------- */
SELECT
    ROUND(SUM(base.mrr), 0)                                        AS base_mrr_12mo_ago,
    ROUND(SUM(COALESCE(now.mrr, 0)), 0)                            AS same_cohort_mrr_now,
    ROUND(100.0 * SUM(COALESCE(now.mrr, 0)) / SUM(base.mrr), 1)    AS net_revenue_retention_pct
FROM fact_mrr_monthly base
LEFT JOIN fact_mrr_monthly now
    ON base.account_id = now.account_id
   AND now.period = '2026-07'
WHERE base.period = '2025-07';


/* ----------------------------------------------------------------------------
   5. Plan mix and ARPA (average revenue per account) over time
   Topics: JOIN, WHERE, aggregate functions, GROUP BY, ORDER BY
---------------------------------------------------------------------------- */
SELECT
    m.period, p.plan_name,
    COUNT(*)                              AS accounts,
    ROUND(SUM(m.mrr), 0)                  AS mrr,
    ROUND(AVG(m.mrr), 2)                  AS arpa
FROM fact_mrr_monthly m
JOIN dim_plan p ON m.plan_id = p.plan_id
WHERE m.period IN ('2023-07', '2024-07', '2025-07', '2026-07')
GROUP BY m.period, p.tier_rank
ORDER BY m.period, p.tier_rank;


/* ----------------------------------------------------------------------------
   6. Churn rate by acquisition channel — which channels bring durable customers?
   Topics: subquery (derived table), LEFT JOIN, GROUP BY, ORDER BY
---------------------------------------------------------------------------- */
SELECT
    a.acquisition_channel,
    COUNT(*)                                                           AS total_signups,
    SUM(CASE WHEN e.event_type = 'Churn' THEN 1 ELSE 0 END)            AS churned,
    ROUND(100.0 * SUM(CASE WHEN e.event_type = 'Churn' THEN 1 ELSE 0 END) / COUNT(*), 1) AS churn_rate_pct
FROM dim_account a
LEFT JOIN (
    SELECT account_id, event_type FROM fact_subscription_event WHERE event_type = 'Churn'
) e ON a.account_id = e.account_id
GROUP BY a.acquisition_channel
ORDER BY churn_rate_pct DESC;


/* ----------------------------------------------------------------------------
   7. Time-to-first-upgrade — how long (in months) after signup does an
      account typically expand, for accounts that ever upgrade at all
   Topics: subquery (derived table), JOIN, aggregate functions
---------------------------------------------------------------------------- */
SELECT
    ROUND(AVG(CAST((JULIANDAY(fu.first_upgrade_date) - JULIANDAY(a.signup_date)) / 30.44 AS REAL)), 1) AS avg_months_to_first_upgrade,
    COUNT(*) AS accounts_that_upgraded
FROM (
    SELECT account_id, MIN(event_date) AS first_upgrade_date
    FROM fact_subscription_event
    WHERE event_type = 'Upgrade'
    GROUP BY account_id
) fu
JOIN dim_account a ON fu.account_id = a.account_id;


/* ----------------------------------------------------------------------------
   8. Six-month retention by signup cohort — of the accounts that signed up
      in a given month, what % were still paying customers exactly 6 months
      later? A fixed window instead of a full month-by-month curve, so the
      date logic stays a single JOIN condition instead of custom arithmetic.
   Topics: JOIN, GROUP BY, ORDER BY
---------------------------------------------------------------------------- */
SELECT
    STRFTIME('%Y-%m', a.signup_date) AS cohort_month,
    COUNT(DISTINCT a.account_id) AS cohort_size,
    COUNT(DISTINCT m.account_id) AS still_active_6mo_later,
    ROUND(100.0 * COUNT(DISTINCT m.account_id) / COUNT(DISTINCT a.account_id), 1) AS pct_retained_6mo
FROM dim_account a
LEFT JOIN fact_mrr_monthly m
    ON a.account_id = m.account_id
   AND m.period = STRFTIME('%Y-%m', DATE(a.signup_date, '+6 months'))
GROUP BY cohort_month
ORDER BY cohort_month;


/* ----------------------------------------------------------------------------
   9. Top accounts by current MRR (a "who matters most" list for CS teams)
   Topics: JOIN (x2), WHERE, ORDER BY, LIMIT
---------------------------------------------------------------------------- */
SELECT
    a.company_name, a.industry, a.country, p.plan_name, m.mrr,
    CAST((JULIANDAY('2026-07-31') - JULIANDAY(a.signup_date)) / 30.44 AS INTEGER) AS tenure_months
FROM fact_mrr_monthly m
JOIN dim_account a ON m.account_id = a.account_id
JOIN dim_plan p ON m.plan_id = p.plan_id
WHERE m.period = '2026-07'
ORDER BY m.mrr DESC
LIMIT 15;


/* ----------------------------------------------------------------------------
   10. Industry mix — where is the customer base concentrated?
   Topics: JOIN, WHERE, subquery (scalar), GROUP BY, ORDER BY
---------------------------------------------------------------------------- */
SELECT
    a.industry,
    COUNT(DISTINCT a.account_id)                                        AS accounts,
    ROUND(SUM(m.mrr), 0)                                                AS current_mrr,
    ROUND(100.0 * SUM(m.mrr) / (SELECT SUM(mrr) FROM fact_mrr_monthly WHERE period = '2026-07'), 1) AS pct_of_total_mrr
FROM fact_mrr_monthly m
JOIN dim_account a ON m.account_id = a.account_id
WHERE m.period = '2026-07'
GROUP BY a.industry
ORDER BY current_mrr DESC;


/* ----------------------------------------------------------------------------
   11. "Watch list" — top 5 accounts by current MRR, UNIONed with the top 5
       longest-tenured accounts. Same idea as a retail "featured products"
       list: two different reasons an account matters (biggest check vs.
       most loyal), combined into one list for the CS team to review.
   Topics: UNION, subquery, ORDER BY, LIMIT
---------------------------------------------------------------------------- */
SELECT company_name, industry, 'Highest MRR' AS reason, mrr AS metric_value
FROM (
    SELECT a.company_name, a.industry, m.mrr
    FROM fact_mrr_monthly m
    JOIN dim_account a ON m.account_id = a.account_id
    WHERE m.period = '2026-07'
    ORDER BY m.mrr DESC
    LIMIT 5
)

UNION

SELECT company_name, industry, 'Longest tenured' AS reason,
       CAST((JULIANDAY('2026-07-31') - JULIANDAY(signup_date)) / 30.44 AS INTEGER) AS metric_value
FROM (
    SELECT a.company_name, a.industry, a.signup_date
    FROM fact_mrr_monthly m
    JOIN dim_account a ON m.account_id = a.account_id
    WHERE m.period = '2026-07'
    GROUP BY a.account_id, a.company_name, a.industry, a.signup_date
    ORDER BY a.signup_date ASC
    LIMIT 5
);
