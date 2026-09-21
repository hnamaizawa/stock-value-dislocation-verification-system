# v0.6.63 Walk-Forward / matched controls / external-shock attribution

## Purpose

Validate the value-dislocation quantitative screen without waiting only for future live outcomes.
The validation layer never reconstructs historical news or human external-event approval. It replays the **current quantitative + structural screen** at historical as-of dates using only data available by each date.

## Point-in-time rule

For every replay date:

1. Price features use rows with `date <= replay_date`.
2. Financial features use rows with `disclosure_date <= replay_date`.
3. Selection is completed before any future price is joined.
4. 10/20/30/60/90/180-day prices are used only to score the already-selected event.
5. No J-Quants or Yahoo fetch is triggered by Walk-Forward execution; it uses the certified local curated snapshot.

## Matched non-selected controls

Each selected event is compared with up to five securities that were **not selected on that replay date**.
Same-sector controls are preferred. If the sector pool is too small, the same market is used.
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
