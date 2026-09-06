# Performance and SBI CSV bridge

## Interactive performance

The J-Quants update pipeline precomputes one row per listed security and writes
`data/curated/latest/security_features.parquet` plus a CSV fallback. The dashboard
loads this feature snapshot rather than recalculating indicators from all daily
price rows. Condition widgets are inside a Streamlit form, so changing sliders does
not rerun screening until the user presses `条件を適用`.

## Incremental updates

J-Quants daily price and financial-summary retrieval remains serial, rate-limited,
and resumable. Completed dates are read from `data/raw/jquants/_cache`; subsequent
runs call the API only for dates that are not already cached. The feature snapshot
is rebuilt after the incremental update completes.

## SBI CSV bridge

The app imports screening-result CSV files exported from SBI Securities or HYPER
SBI 2. It supports UTF-8 and CP932/Shift-JIS and detects common Japanese column
names. Imported codes are matched against the certified J-Quants company master
and against the current local shortlist.

The bridge is intentionally file-based. It does not log in to SBI, store SBI
credentials, scrape broker pages, or transmit orders.
