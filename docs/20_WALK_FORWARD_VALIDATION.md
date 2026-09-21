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
5. No J-Quants or Yahoo fetch is triggered by Walk-Forward execution; it uses the certified local curated snapshot.

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
financial data by that date and must exist in the curated company master.

The result records `observable_code_count`, `eligible_master_code_count`,
`missing_master_code_count`, and `master_coverage_ratio`. This makes missing-master
coverage visible and prevents it from being silently described as a complete historical
universe. It does **not** recreate delisted securities that are absent from the upstream
curated snapshot; therefore the screen can reduce and disclose survivorship risk but
cannot claim to eliminate it without historical security-master snapshots.

## Horizon convention

A horizon of N days means the Nth available trading session strictly after the selection
date. `actual_days_Nd` remains the observed calendar-day distance for audit purposes.
