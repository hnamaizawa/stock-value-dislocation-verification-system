# v0.6.63 Walk-Forward / matched controls / external-shock attribution

## Purpose

Validate the value-dislocation quantitative screen without waiting only for future live outcomes.
The validation layer never reconstructs historical news or human external-event approval. It replays the **current quantitative + structural screen** at historical as-of dates using only data available by each date.

## Point-in-time rule

For every replay date:

1. Price features use rows with `date <= replay_date`.
2. Financial features use rows with `disclosure_date <= replay_date`.
3. Selection is completed before any future price is joined.
4. 10/20/30/60/90/180 **trading-session** returns are used only to score the already-selected event.
5. The newest historical security-master snapshot on or before the replay date defines the company universe.
6. No J-Quants or Yahoo fetch is triggered by Walk-Forward execution; it uses certified local data only.

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

The six-month stock return is decomposed as:

`stock = market + (sector - market) + (stock - sector)`

The attribution ratio is the fraction of an observed stock decline explained by negative market and sector components, capped to 0..100%.
It is descriptive evidence only; it does not prove causality and never replaces the human external-event review.
Missing benchmark/sector data remains missing and is never fabricated as zero.


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
date. `actual_days_Nd` remains the observed calendar-day distance for audit purposes.


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
