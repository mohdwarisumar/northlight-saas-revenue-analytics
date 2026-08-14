# Northlight Analytics — Plain-English Walkthrough & Interview Prep

## The one-sentence pitch

"I built a synthetic B2B SaaS subscription dataset for a fictional analytics company, modeled it around the standard SaaS metrics — MRR, churn, expansion, net revenue retention — using an event-sourced structure like a real Stripe/Chargebee data warehouse would have, and built the analysis and reporting layer on top."

This is the most metrics-dense of the three projects, so it's worth being extra comfortable with the vocabulary — SaaS interviewers (or anyone hiring for a subscription business) will drill into MRR/NRR specifically.

## The data model, explained simply

Two fact tables, which is the one thing worth explaining up front because it trips people up:

- `fact_subscription_event` — one row per *thing that happened*: a new signup, an upgrade, a downgrade, a churn, a reactivation. This is the "transaction log."
- `fact_mrr_monthly` — one row per account per month, showing what plan they were on and what they paid *that month*. This is a "snapshot," not a transaction — it's the answer to "what does the world look like right now," rebuilt fresh for every month.

**Why both, if one theoretically implies the other?** Because they answer different questions efficiently. "What's our MRR right now" is a simple `SUM` over the snapshot table. "How did we get from £254k to £264k MRR last month" — new customers vs. upgrades vs. cancellations — needs the event log, because the snapshot alone can't tell you *why* the number moved, only that it did. Real subscription-billing data warehouses (Stripe's own reporting, for instance) keep exactly this split for the same reason.

## Query-by-query, in plain English

All queries use only WHERE, aggregate functions, `GROUP BY`, `ORDER BY`, `JOIN`s (including a self-join), `UNION`, and subqueries — no CTEs, no window functions.

**Query 1 — MRR/ARR trend.** Sums the snapshot table by month. ARR is just MRR × 12 (an annualized run-rate, not "money already collected this year" — a common point of confusion worth getting right if asked).

**Query 2 — MRR movement waterfall.** Groups the event log by month and event type, so you get "how much MRR did New signups add this month, how much did Upgrades add, how much did Churn remove." This is the data behind the waterfall chart, which is the single most important visual for explaining SaaS growth to anyone — "we grew" is a much weaker statement than "we grew because new logos outpaced churn by X."

**Query 3 — Churn rate (logo and revenue).** Two subqueries — one summarizing accounts/MRR active each month, one summarizing churn events each month — joined together. Two different churn numbers come out, and the difference matters: **logo churn** = what % of *customers* left; **revenue churn** = what % of *MRR* left. If your biggest customers are the ones leaving, revenue churn will be worse than logo churn — that gap is itself a useful signal (it means you're losing your best accounts disproportionately).

**Query 4 — Net Revenue Retention (NRR).** The single most important SaaS metric, and worth understanding cold. It's a genuine **self-join**: `fact_mrr_monthly` joined to itself, once filtered to 12 months ago (aliased `base`) and once to today (aliased `now`), matched on `account_id`. The `LEFT JOIN` matters — it keeps every account from the 12-months-ago side even if that account has since churned and has no row on the "now" side; `COALESCE(now.mrr, 0)` then treats "no longer exists" as literally £0, rather than dropping the row. That's what makes the metric honest: a churned account still counts as a zero, it doesn't just disappear from the comparison. NRR deliberately **excludes new customers acquired since then** — it measures how well you retain and grow the customers you already had, completely separately from new-logo growth. NRR above 100% (mine lands at 102.6%) means expansion from existing customers is outpacing churn and downgrades, considered a very healthy sign in SaaS — it means the business would keep growing even if new sales stopped entirely.

**Query 5 — Plan mix and ARPA over time.** ARPA = Average Revenue Per Account = MRR ÷ number of accounts. Tracking this over time shows whether the customer base is moving upmarket (higher ARPA) or downmarket.

**Query 6 — Churn by acquisition channel.** A subquery isolates churn events, then a `LEFT JOIN` brings that onto the full account list so accounts that never churned still count in the denominator. The business question it answers is real: if paid-search customers churn faster than referral customers, that changes how you'd value each channel beyond just cost-per-signup.

**Query 7 — Time to first upgrade.** A subquery finds each account's first upgrade date; the outer query averages, in months, how long after signup that happened. Uses `JULIANDAY()` to convert two dates into a day count, same trick as the other two projects.

**Query 8 — Six-month cohort retention.** Group accounts by signup month, then `LEFT JOIN` to the snapshot table filtered to exactly 6 months after each account's signup date (`DATE(signup_date, '+6 months')` computes that date directly in the join condition — no separate date arithmetic needed). Counting cohort size vs. accounts still present in that snapshot gives a straightforward 6-month retention percentage per cohort.

**Query 9 — Top accounts by MRR.** A simple sorted list, but it's genuinely the kind of query a Customer Success team runs to know who their highest-priority renewals are.

**Query 10 — MRR by industry.** Group-by, shows revenue concentration — useful for understanding how exposed the business is to any one vertical having a bad year.

**Query 11 — Account watch list.** Two subqueries — top 5 accounts by current MRR, top 5 by tenure — combined with `UNION` into one list, the same pattern as the retail project's "worth featuring" query. An account can show up for either reason (or, if it qualifies for both, just once).

## Likely interview questions

**"What's the difference between MRR growth and NRR, and why do you need both?"** MRR growth tells you the business is bigger than it was; it doesn't tell you *why* — could be new sales carrying a leaky bucket of churn, or it could be durable expansion from happy customers. NRR isolates the second story by holding the customer set fixed. A business can have great MRR growth and terrible NRR (if it's pouring money into new-customer acquisition to mask churn) — that combination is a genuine red flag investors look for.

**"Why is logo churn different from revenue churn, and which matters more?"** Depends on the business. If you're mostly SMB/self-serve, logo churn is closer to what matters because customers are similar sizes. If you have a few whale accounts, revenue churn matters more because losing one huge account can hurt more than losing fifty small ones, even if the logo-churn number looks fine.

**"Walk me through the waterfall chart."** Start MRR, plus New (brand-new customers), plus Expansion (existing customers upgrading), minus Contraction (existing customers downgrading), minus Churn (customers leaving entirely), plus Reactivation (previously churned customers coming back) = End MRR. Every one of those six numbers is a separate, addressable business lever — which is the whole point of breaking MRR movement down this way instead of just reporting the net change.

**"How would this scale to a real billing system with millions of events?"** The event-log-plus-snapshot pattern already scales reasonably well; the main change at real scale would be materializing the monthly snapshot as an actual scheduled job (dbt or similar) rather than a table generated once, and probably partitioning the event log by month since most queries filter on a date range anyway.

**"What's missing that a real SaaS analytics stack would have?"** Usage/product data (are customers actually using the features, which predicts churn *before* it happens, not just after), a proper CAC figure tied to actual marketing spend by channel, and support ticket volume as a leading churn indicator.

## Vocabulary to have cold

- **MRR / ARR** — Monthly/Annual Recurring Revenue (ARR is MRR × 12, a run-rate, not cash collected)
- **NRR (Net Revenue Retention)** — existing-customer revenue now ÷ existing-customer revenue 12 months ago, excluding new logos
- **Logo churn vs. revenue churn** — customer-count churn vs. dollar-value churn
- **Expansion / contraction** — existing customers paying more (upgrade) or less (downgrade)
- **Cohort** — a group of customers who share a start date, tracked forward over time
- **ARPA** — Average Revenue Per Account
- **Self-join** — joining a table to itself so you can compare one set of its rows to another set of its own rows (here: the same account's MRR at two different points in time)

## Also in this project

`sql/04_views_and_maintenance.sql` covers primary/foreign keys (pointing at the schema), a `CREATE VIEW` example, and `UPDATE`/`DELETE`/`ALTER TABLE`/the SQLite equivalent of `TRUNCATE`.
