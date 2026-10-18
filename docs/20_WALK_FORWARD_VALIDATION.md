# v0.6.63 Walk-Forward / matched controls / external-shock attribution

## Purpose

Validate the value-dislocation quantitative screen without waiting only for future live outcomes.
The validation layer never reconstructs historical news or human external-event approval. It replays the **current quantitative + structural screen and production ◎☆ badge functions** at historical as-of dates using only data available by each date.

## Point-in-time rule

For every replay date:

1. Price features use rows with `date <= replay_date`.
2. Financial features use rows with `disclosure_date <= replay_date`.
3. Selection is completed before any future price is joined.
4. The target horizons are 10/20/30/60/90/120/240/365 **trading sessions**. Forward returns are used only to score the already-selected event.
5. The newest historical security-master snapshot on or before the replay date defines the company universe.
6. No J-Quants or Yahoo fetch is triggered by Walk-Forward execution; it uses certified local data only.

## Feature-history consistency and replay exclusions (v0.6.81)

The production 52-week drawdown uses 252 daily observations; the six-month return uses
126. A replay date is eligible only when 252 trading sessions are present through that
date. Each security also needs 252 of its own dated price rows; newer listings or partial
histories are excluded from that date's candidate universe. The screen reports replay
dates omitted for short history or insufficient forward outcomes, plus excluded
security-date pairs. It never substitutes a shorter window and labels it as a full year.

The checked-in real-data configuration requests 400 **calendar** days. This workspace has
no curated real-data bundle, so its accumulated period cannot be measured here. A 400-day
request is generally too short for a full 252-session lookback plus a 180-session outcome.
For the default eight-date mode, a rough complete-history target is about 840 calendar
days (252 history + 180 outcome + 5 waiting sessions + seven 20-session gaps). Actual
availability depends on holidays, provider limits, and each security's listing date.
The configured lookback is not changed automatically; any extension applies only on the
next explicit data update and preserves the requested/effective period in its manifest.

## Episode-level counts and uncertainty (v0.6.81)

If one security is selected at adjacent replay dates, those rows share one episode whose
start is the first selected date. A gap with an intervening replay date where it was not
selected starts a new episode. Summary returns and bootstrap resampling use the first
selection in each episode; tables show both confirmed episodes and repeated event rows.

The mean selection effect is accompanied by a 95% episode-bootstrap interval. When this
interval includes zero, the UI says there is not enough evidence to claim a selection
effect. The reported resampling share at or below zero is descriptive and is not a
probability that the strategy works or fails.

## Rule-learning holdout (v0.6.81)

Rule learning excludes the latest configurable `final_holdout_trading_days` from training.
An event is eligible for training only when its primary-horizon outcome date is before
that holdout begins, so a label that uses holdout prices cannot leak into rule adjustment.
The default is 60 trading sessions, the minimum is 100 mature episodes, and
`auto_apply` defaults to false. Candidate rule changes remain proposals; they are not
applied automatically. The current data status shows matured episodes versus the required
count and the holdout length.

## Matched non-selected controls

Each selected event is compared with up to five securities that were **not selected on that replay date**.
Same-sector controls are ranked and retained first. If that pool is too small, only the missing slots are backfilled from the same market; any final shortfall may use the remaining non-selected universe.
Distance uses available point-in-time metrics only:

- log market capitalization
- 52-week drawdown
- 60-day volatility
- PER versus sector median
- PBR versus sector median

At least two comparable dimensions are required. The result reports the selected return, control mean return, and `selection_edge = selected - controls`.

## External Shock Attribution

The default `v2_sector_absolute` method calculates the share of a declining stock's fall
covered by the absolute decline of its sector median:

`clip(-sector_median_return_6m, 0, -stock_return_6m) / -stock_return_6m`

Market return is not added because the sector return already includes the market move.
The `v1_legacy` setting remains available for comparison and sums negative market and
sector-increment components. Both methods require a declining stock and at least five
sector peers; missing or insufficient sector data stays unavailable. The comparison view
evaluates both methods across the same local data and point-in-time replay dates, reporting
candidate counts, selection effect, positive rate, and confirmed counts. This ratio is
descriptive evidence only; it does not prove causality and never replaces human review.


## Point-in-time universe and survivorship coverage

Before each replay, prices are restricted to `date <= replay_date` and financials to
`disclosure_date <= replay_date`. A security must have both observable price and
financial data by that date and must exist in the selected historical company master.

Each J-Quants update archives its dated CompanyMaster. Existing certified curated runs are
backfilled without API access. Walk-Forward chooses the newest snapshot whose date is on or
before the replay date, so a delisted security retained in that snapshot can remain in the
historical universe even when it is absent from the current CompanyMaster.

The result records `universe_source`, `historical_master_available`, `master_snapshot_date`,
`master_snapshot_age_days`, `observable_code_count`, `eligible_master_code_count`,
`missing_master_code_count`, and `master_coverage_ratio`. When no snapshot exists on or
before the replay date, the current CompanyMaster is used only as an explicitly disclosed
fallback. This substantially reduces survivorship bias as snapshots accumulate, but cannot
reconstruct a security absent from every saved or backfilled master and therefore does not
claim complete elimination of survivorship bias.

## Horizon convention

A horizon of N days means the Nth available trading session strictly after the selection
date. `actual_days_Nd` remains the observed calendar-day distance for audit purposes. The
current implementation supports 10/20/30/60/90/180 sessions; 120/240/365 are goal-alignment
work and must not be presented as available until implemented and verified. Unsupported
horizons must remain visibly unavailable when local history cannot support them.


## v0.6.65 performance model

Walk-Forward remains local-only and point-in-time, but avoids repeating equivalent work:

- A per-security sorted NumPy date/close index resolves forward returns with binary search.
- Point-in-time quantitative feature tables are persisted by curated-data signature and replay date.
- Complete event results are persisted by curated-data signature, screening configuration,
  Walk-Forward settings, horizons, cache schema, and application version.
- Cache writes use a temporary parquet followed by an atomic replace.
- A changed data file, condition, mode, horizon, setting, or application version produces a
  different cache key; stale results are not silently reused.
- Progress reports the current replay number and date without triggering J-Quants or Yahoo access.

The dashboard provides three modes:

- **簡易**: 3 snapshots; 10/30/90 trading sessions.
- **標準**: 8 snapshots; all six horizons.
- **詳細**: 12 snapshots; all six horizons.

Users can override the settings or explicitly bypass the complete-result cache. Feature caches
may still be reused because they contain threshold-independent point-in-time metrics.

## v0.6.71 production badge cohorts and entry timing

Each point-in-time quantitative candidate is passed through the same `build_buy_readiness`
and `build_intuitive_signal` functions as the dashboard. Results retain
`legacy_star_eligible`, `reversal_star_eligible`, `star_rule_version`, evidence score, and
trend score. The dashboard compares the nested quantitative, legacy-star, and
reversal-confirmed-star cohorts over the same horizon.

Every cohort reports confirmed count, mean, median, positive rate, and the rate of returns
at or below -5%. A small stricter cohort must not be judged from its mean alone.

For reversal-confirmed stars, delayed-entry simulations use the close of the third or fifth
session after selection and measure the requested horizon from that entry session. These
future prices are joined only after eligibility is frozen and can never change the badge.
Replay dates reserve enough future sessions for the largest requested horizon plus entry
delay, reducing incomparable completion counts.

## v0.6.72 adapting to local price history

Before execution, the UI checks the number of unique stored trading sessions against the
60-session minimum history, each requested evaluation horizon, and the longest delayed
entry window. Unsupported longer horizons are omitted and disclosed; available shorter
horizons are still evaluated. If even the shortest requested horizon cannot be evaluated,
the UI reports both the available and minimum required session counts. If data is sufficient
but the replay produces no selected events, the UI says so separately from a history shortage.

## v0.6.73 diagnosing zero-candidate replays

When a replay has no selected candidates, the UI reports evaluated security rows across
replay dates and the most frequent `fail_reasons` from the point-in-time screen. Counts
are security-by-date occurrences, so one security can contribute to several reasons and
repeated dates. If no joined price/financial rows were available, the UI asks users to
check overlapping securities, historical disclosures, and local coverage. Diagnostics
never relax selection rules. An empty outcome cache is replayed to regenerate diagnostics
while reusing point-in-time feature caches.

## v0.6.74 using the applied screen configuration

The condition builder stores submitted values in Streamlit session state rather than
rewriting `config/real_data.yaml`. Walk-Forward therefore overlays the last submitted
`_current_overrides()` when `screening_revision` is positive. If no screen conditions were
submitted in that session, it uses the real configuration file and labels that source in
the UI. The merged config is included in the result cache key.
