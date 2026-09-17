from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .config import load_config, project_root_from_config
from .data.jquants import date_window, fetch_and_curate_jquants, fetch_policy_from_config
from .data.search import load_curated_latest
from .data.snapshot import now_jst, read_manifest, write_dataframe
from .data.performance import build_feature_snapshot
from .strategy.criteria import (
    apply_quantitative_criteria,
    prepare_quantitative_universe,
    screening_funnel,
    shortlist_from_table,
)
from .strategy.quantitative import make_external_event_review_queue
from .hypothesis_invalidation import evaluate_saved_reviews
from .history import write_daily_analysis_snapshot, write_star_outcomes


def run_real_pipeline(
    config_path: Path,
    *,
    end: str | None = None,
    client=None,
) -> dict[str, Path | str | int | bool]:
    # Ordinary configuration reads are intentionally cheap. Learned-rule history is
    # refreshed exactly once below, after the market-data snapshot has been updated.
    cfg = load_config(config_path)
    root = project_root_from_config(config_path)
    runtime = cfg.get("runtime", {})
    provider = cfg.get("providers", {}).get("jquants", {})
    start, end_date, financial_start = date_window(
        end,
        int(runtime.get("price_lookback_days", 400)),
        int(runtime.get("financial_lookback_days", 1150)),
    )
    paths = fetch_and_curate_jquants(
        project_root=root,
        start=start,
        end=end_date,
        financial_start=financial_start,
        api_key_env=str(provider.get("api_key_env", "JQUANTS_API_KEY")),
        include_topix=bool(provider.get("include_topix", True)),
        include_earnings=bool(provider.get("include_earnings_calendar", True)),
        client=client,
        fetch_policy=fetch_policy_from_config(provider),
    )

    # Rule learning may scan point-in-time history and attach forward returns. Keep
    # that CPU-heavy work out of Streamlit navigation and run it only for this explicit
    # data-refresh path, using the freshly persisted local price snapshot.
    cfg = load_config(config_path, refresh_rule_learning=True)

    data = load_curated_latest(root)
    prices = data["prices"]
    as_of = pd.Timestamp(prices["date"].max())

    # Price/financial feature aggregation is the other expensive CPU step. Compute it
    # once, persist exactly that frame, then apply the current thresholds to it.
    prepared = prepare_quantitative_universe(
        data["companies"], data["prices"], data["financials"], as_of
    )
    feature_meta = build_feature_snapshot(
        data["companies"],
        data["prices"],
        data["financials"],
        as_of,
        root / "data" / "curated" / "latest",
        prepared=prepared,
    )
    audit = apply_quantitative_criteria(prepared, cfg)
    shortlist = shortlist_from_table(audit, cfg)
    funnel = screening_funnel(audit)

    # Preserve the point-in-time analysis for later search and outcome validation.
    # Same-day reruns replace that date only, so this does not grow duplicate rows.
    analysis_history_path = write_daily_analysis_snapshot(
        root, audit, analysis_date=now_jst().date(), run_id=paths.run_id, data_as_of=as_of.date()
    )
    # Recalculate any ◎☆ forward outcomes that have become observable from saved evaluations.
    star_outcomes_path = write_star_outcomes(root)

    manifest = read_manifest(paths.manifest_path)
    request_meta = manifest.get("request", {})
    subscription_coverage = manifest.get("subscription_coverage")
    today_jst = now_jst().date()
    data_age_days = max(0, (today_jst - as_of.date()).days)
    maximum_order_preview_age = int(runtime.get("max_data_age_days_for_order_preview", 7))
    topix_available = bool(audit.get("topix_available", pd.Series(dtype=bool)).any())
    proxy_available = bool(audit.get("topix_proxy_available", pd.Series(dtype=bool)).any())
    benchmark_source = "official_topix" if topix_available else ("topix_etf_proxy" if proxy_available else "none")
    benchmark_label = "正式TOPIX"
    if benchmark_source == "topix_etf_proxy":
        labels = audit.get("topix_proxy_label", pd.Series(dtype=str)).dropna()
        benchmark_label = str(labels.iloc[0]) if not labels.empty else "TOPIX連動ETF代理値"
    elif benchmark_source == "none":
        benchmark_label = "市場比較なし"
    data_fresh_enough_for_order_preview = data_age_days <= maximum_order_preview_age
    # Candidate-specific external-event approval is stored separately from the market-data run.
    # Therefore a pipeline run alone can never make a candidate order-preview eligible.
    base_order_preview_eligible = data_fresh_enough_for_order_preview and (topix_available or proxy_available)
    order_preview_eligible = False

    metadata = {
        "run_id": paths.run_id,
        "as_of": as_of.isoformat(),
        "data_cutoff_at": manifest["data_cutoff_at"],
        "generated_at": now_jst().isoformat(),
        "provider": "J-Quants API V2",
        "actual_data": True,
        "sample_data": False,
        "source_snapshot": paths.manifest_path.as_posix(),
        "requested_price_end": request_meta.get("requested_price_end"),
        "effective_price_end": request_meta.get("effective_price_end"),
        "subscription_coverage_end": (
            subscription_coverage.get("end")
            if isinstance(subscription_coverage, dict)
            else None
        ),
        "data_age_days": data_age_days,
        "topix_available": topix_available,
        "topix_proxy_available": proxy_available,
        "benchmark_source": benchmark_source,
        "benchmark_label": benchmark_label,
        "data_fresh_enough_for_order_preview": data_fresh_enough_for_order_preview,
        "base_order_preview_eligible": base_order_preview_eligible,
        "external_event_review_required": True,
        "order_preview_eligible": order_preview_eligible,
    }
    for key, value in metadata.items():
        shortlist[key] = value

    output_dir = paths.output_dir
    shortlist_path = output_dir / "quantitative_shortlist_latest.csv"
    write_dataframe(shortlist, shortlist_path)

    audit_path = output_dir / "quantitative_audit_latest.csv"
    write_dataframe(audit, audit_path)
    funnel_path = output_dir / "screening_funnel_latest.json"
    funnel_path.write_text(json.dumps(funnel, ensure_ascii=False, indent=2), encoding="utf-8")

    review = make_external_event_review_queue(
        shortlist, paths.run_id, str(manifest["data_cutoff_at"])
    )
    review_path = output_dir / "external_event_review_queue_latest.csv"
    write_dataframe(review, review_path)
    review_archive = root / "data" / "reviews" / f"external_event_review_queue_{paths.run_id}.csv"
    write_dataframe(review, review_archive)

    # Reuse the freshly computed feature frame. Re-reading the persisted parquet here
    # only adds I/O and memory pressure and cannot make the data newer.
    invalidation_results = evaluate_saved_reviews(
        root / "config" / "external_event_reviews", prepared
    )
    invalidation_path = output_dir / "hypothesis_invalidation_latest.csv"
    write_dataframe(invalidation_results, invalidation_path)

    warnings = list(manifest.get("warnings", []))
    if not topix_available and proxy_available:
        warnings.append(f"Official TOPIX is unavailable. {benchmark_label} adjusted close is used as a clearly labelled proxy.")
    elif not topix_available and not proxy_available:
        warnings.append("Official TOPIX and TOPIX ETF proxy are unavailable. The relative filter is skipped with an explicit limitation.")
    if not data_fresh_enough_for_order_preview:
        warnings.append(
            f"Market data is {data_age_days} days old; order-preview eligibility is blocked "
            f"above {maximum_order_preview_age} days."
        )

    status = {
        **metadata,
        "price_rows": int(len(data["prices"])),
        "financial_rows": int(len(data["financials"])),
        "company_rows": int(len(data["companies"])),
        "audit_rows": int(len(audit)),
        "shortlist_rows": int(len(shortlist)),
        "orders_generated": 0,
        "order_transmission": False,
        "warnings": warnings,
        "screening_funnel": funnel,
        "feature_snapshot": feature_meta,
        "hypothesis_invalidation_rows": int(len(invalidation_results)),
        "hypothesis_invalidation_breaches": int((invalidation_results.get("status", pd.Series(dtype=str)) == "breached").sum()),
        "analysis_history_path": analysis_history_path.as_posix(),
        "star_outcomes_path": star_outcomes_path.as_posix(),
    }
    status_path = output_dir / "run_status_latest.json"
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "run_id": paths.run_id,
        "as_of": as_of.isoformat(),
        "shortlist_count": len(shortlist),
        "shortlist_path": shortlist_path,
        "audit_path": audit_path,
        "funnel_path": funnel_path,
        "review_path": review_path,
        "invalidation_path": invalidation_path,
        "analysis_history_path": analysis_history_path,
        "star_outcomes_path": star_outcomes_path,
        "manifest_path": paths.manifest_path,
        "status_path": status_path,
        "requested_price_end": request_meta.get("requested_price_end"),
        "effective_price_end": request_meta.get("effective_price_end"),
        "subscription_coverage_end": (
            subscription_coverage.get("end")
            if isinstance(subscription_coverage, dict)
            else None
        ),
        "order_preview_eligible": order_preview_eligible,
    }
