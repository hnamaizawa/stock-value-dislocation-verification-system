# Beginner Condition UI

## Purpose

The condition screen lets a beginner change quantitative screening rules without editing YAML or calling J-Quants again. It always uses the certified files under `data/curated/latest/` and the verified manifest.

## Presets

### 安全重視

- Prime / Standard
- Higher liquidity
- Equity ratio 40% or more
- Operating cash flow positive in all observed three years
- Smaller forecast decline tolerance
- Moderate price decline requirement

### 標準

- Prime / Standard / Growth
- Equity ratio 30% or more
- Operating cash flow positive in at least two of three years
- Forecast operating-profit decline no worse than 20%
- 52-week drawdown of at least 18%

### 割安重視

- Wider universe and lower liquidity threshold
- Equity ratio 25% or more
- Larger 52-week drawdown requirement
- Lower quantitative-score threshold
- More warnings are expected and must be reviewed

## Rule classes

1. **必須条件** remove a security when failed.
2. **定量スコア** ranks securities that pass the hard conditions.
3. **警告** keeps a security visible but states missing data or research work.

## TOPIX

When TOPIX is absent, the application never substitutes the security's own return. The relative value stays empty. If the TOPIX condition is enabled, it is skipped with a warning; the limitation remains visible on every candidate.

## Dynamic calculation

Changing a widget calls `apply_quantitative_criteria` against a cached `prepare_quantitative_universe` result. It does not call J-Quants and does not alter the certified snapshot.

## Profiles

Profiles are stored locally under `config/user_profiles/*.json`. They contain only screening conditions. They must not contain API keys, broker credentials, portfolio data, or retrieved market data.

Generated similar applications exclude saved profiles. A new application starts with the built-in presets.

## Acceptance criteria

- Preset selection updates all controls.
- Sliders and check boxes recalculate the funnel and candidates immediately.
- The candidate table shows pass reasons and warnings.
- Near-miss securities show failure reasons.
- Profile save/load round-trips the conditions.
- JSON and candidate CSV downloads work.
- No J-Quants request is performed by condition changes.
