/* ============================================================================
   Northlight Analytics — Views, Keys & Maintenance Statements
   Database: northlight.db (SQLite)
   ----------------------------------------------------------------------------
   Same purpose as the other two projects' file of this name. Safe to run
   against a copy of the database.
   ============================================================================ */


/* ----------------------------------------------------------------------------
   KEYS — see sql/01_schema.sql. fact_mrr_monthly uses a composite PRIMARY
   KEY (account_id, period) — together they're unique, since one account
   can only have one MRR figure per month — plus FOREIGN KEYs back to
   dim_account and dim_plan.
---------------------------------------------------------------------------- */


/* ----------------------------------------------------------------------------
   VIEW — current-month MRR per account with plan and account details
   already joined in, since almost every "who's paying us and how much"
   question starts from exactly this shape.
---------------------------------------------------------------------------- */
CREATE VIEW IF NOT EXISTS v_current_mrr AS
SELECT
    a.account_id, a.company_name, a.industry, a.country, a.acquisition_channel,
    p.plan_name, m.mrr, m.period
FROM fact_mrr_monthly m
JOIN dim_account a ON m.account_id = a.account_id
JOIN dim_plan p ON m.plan_id = p.plan_id
WHERE m.period = (SELECT MAX(period) FROM fact_mrr_monthly);

-- now "MRR by plan, this month" is a one-liner:
SELECT plan_name, COUNT(*) AS accounts, ROUND(SUM(mrr), 0) AS mrr
FROM v_current_mrr
GROUP BY plan_name
ORDER BY mrr DESC;


/* ----------------------------------------------------------------------------
   UPDATE — correct a single row. Example: sales corrects an account's
   industry classification after a data entry error.
---------------------------------------------------------------------------- */
UPDATE dim_account
SET industry = 'SaaS / Software'
WHERE account_id = 1;


/* ----------------------------------------------------------------------------
   DELETE — remove specific rows. Example: a duplicate subscription event
   needs to be removed after a billing system replay.
---------------------------------------------------------------------------- */
DELETE FROM fact_subscription_event
WHERE event_id = 1;


/* ----------------------------------------------------------------------------
   ALTER TABLE — change a table's structure. Example: the business wants to
   start tracking each account's assigned Customer Success manager.
---------------------------------------------------------------------------- */
ALTER TABLE dim_account ADD COLUMN cs_manager TEXT;


/* ----------------------------------------------------------------------------
   TRUNCATE — SQLite has no TRUNCATE keyword; standard SQL (MySQL/SQL
   Server/Postgres) would use:

       TRUNCATE TABLE fact_subscription_event;

   The SQLite equivalent is an unconditional DELETE:
---------------------------------------------------------------------------- */
DELETE FROM fact_subscription_event WHERE 1=0;  -- harmless no-op version for this demo file;
                                                -- a real truncate would be: DELETE FROM table_name;
