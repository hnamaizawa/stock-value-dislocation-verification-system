from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

from ..codes import display_tse_code, normalize_tse_code
from ..strategy.features import financial_features, price_features


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class RealDataNotReadyError(RuntimeError):
    pass


def load_curated_latest(project_root: Path) -> dict[str, pd.DataFrame]:
    base = project_root / "data" / "curated" / "latest"
    manifest_path = base / "manifest.json"
    if not manifest_path.exists():
        raise RealDataNotReadyError(
            "Actual-data manifest is missing. Run run_real.cmd or value-dislocation run-real first."
        )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RealDataNotReadyError("Actual-data manifest is invalid.") from exc
    if manifest.get("actual_data") is not True or manifest.get("sample_data") is not False:
        raise RealDataNotReadyError(
            "The curated dataset is not certified as actual data; sample/actual mixing is rejected."
        )
    required = ["companies", "prices", "financials"]
    result: dict[str, pd.DataFrame] = {}
    for name in required + ["earnings", "topix"]:
        path = base / f"{name}.csv"
        if name in required and not path.exists():
            raise RealDataNotReadyError(
                "Real data is not ready. Run run_real.cmd or value-dislocation run-real first."
            )
        if path.exists():
            expected = manifest.get("curated_files", {}).get(name, {}).get("sha256")
            if expected and _sha256(path) != expected:
                raise RealDataNotReadyError(
                    f"Curated file hash mismatch: {name}. Re-run actual-data retrieval."
                )
            date_cols = {
                "prices": ["date"],
                "financials": ["disclosure_date", "period_end"],
                "earnings": ["date"],
                "topix": ["date"],
            }.get(name, [])
            df = pd.read_csv(path, dtype={"code": str})
            for col in date_cols:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors="coerce")
            result[name] = df
    result["manifest"] = manifest
    return result


_COMPANY_NOISE_WORDS = (
    "株式会社", "（株）", "(株)", "有限会社", "合同会社", "ホールディングス",
    "ホールディング", "グループ", "company", "co.,ltd.", "co., ltd.", "co ltd",
)


def _katakana_to_hiragana(text: str) -> str:
    chars = []
    for ch in text:
        codepoint = ord(ch)
        if 0x30A1 <= codepoint <= 0x30F6:
            chars.append(chr(codepoint - 0x60))
        else:
            chars.append(ch)
    return "".join(chars)


def normalize_company_search_text(value: object) -> str:
    """Normalize Japanese company/query text for beginner-friendly fuzzy search.

    This intentionally keeps kanji intact while normalizing width/case, katakana/hiragana,
    common corporate suffixes, spaces and punctuation.
    """
    text = unicodedata.normalize("NFKC", str(value or "")).casefold().strip()
    text = _katakana_to_hiragana(text)
    for word in _COMPANY_NOISE_WORDS:
        normalized_word = _katakana_to_hiragana(unicodedata.normalize("NFKC", word).casefold())
        text = text.replace(normalized_word, "")
    text = re.sub(r"[^0-9a-zぁ-ん一-龯々〆ヵヶ]+", "", text)
    return text


def _fuzzy_company_score(query_norm: str, name_norm: str) -> tuple[float, str]:
    if not query_norm or not name_norm:
        return 0.0, ""
    if query_norm == name_norm:
        return 1.0, "企業名完全一致"
    if name_norm.startswith(query_norm):
        coverage = min(1.0, len(query_norm) / max(len(name_norm), 1))
        return 0.94 + coverage * 0.04, "企業名先頭一致"
    if query_norm in name_norm:
        coverage = min(1.0, len(query_norm) / max(len(name_norm), 1))
        return 0.86 + coverage * 0.06, "企業名部分一致"
    ratio = SequenceMatcher(None, query_norm, name_norm).ratio()
    # Short Japanese abbreviations often have a lower whole-string ratio. Reward shared prefix.
    prefix = 0
    for a, b in zip(query_norm, name_norm):
        if a != b:
            break
        prefix += 1
    prefix_bonus = min(0.12, prefix * 0.025)
    return min(0.84, ratio + prefix_bonus), "あいまい一致"


def search_companies(companies: pd.DataFrame, query: str, limit: int = 30) -> pd.DataFrame:
    q = str(query or "").strip()
    if not q:
        return companies.head(0).copy()

    query_norm = normalize_company_search_text(q)
    digits = "".join(ch for ch in unicodedata.normalize("NFKC", q) if ch.isdigit())
    canonical_code = normalize_tse_code(digits) if len(digits) >= 4 else ""

    rows = []
    for row in companies.itertuples(index=False):
        raw_code = str(getattr(row, "code"))
        display_code = display_tse_code(raw_code)
        name = str(getattr(row, "name"))
        name_norm = normalize_company_search_text(name)

        score = 0.0
        match_type = ""
        if canonical_code and raw_code == canonical_code:
            score, match_type = 1.20, "証券コード完全一致"
        elif digits and (raw_code.startswith(digits) or display_code.startswith(digits)):
            score, match_type = 1.05, "証券コード前方一致"
        else:
            score, match_type = _fuzzy_company_score(query_norm, name_norm)

        # Conservative floor prevents unrelated names from flooding the candidate dialog.
        min_score = 0.42 if len(query_norm) >= 3 else 0.58
        if score < min_score:
            continue

        item = row._asdict()
        item["display_code"] = display_code
        item["search_score"] = round(float(score), 4)
        item["match_type"] = match_type
        rows.append(item)

    if not rows:
        return companies.head(0).assign(
            display_code=pd.Series(dtype=str),
            search_score=pd.Series(dtype=float),
            match_type=pd.Series(dtype=str),
        )

    out = pd.DataFrame(rows)
    out = out.sort_values(
        ["search_score", "display_code", "name"],
        ascending=[False, True, True],
        kind="stable",
    ).head(limit).reset_index(drop=True)
    return out


def stock_detail(data: dict[str, pd.DataFrame], code: str) -> dict[str, object]:
    canonical = normalize_tse_code(code)
    companies = data["companies"]
    prices = data["prices"]
    financials = data["financials"]
    company_rows = companies.loc[companies["code"] == canonical]
    if company_rows.empty:
        raise KeyError(f"Stock code not found: {code}")
    company = company_rows.iloc[-1].to_dict()
    price_rows = prices.loc[prices["code"] == canonical].sort_values("date")
    financial_rows = financials.loc[financials["code"] == canonical].sort_values("disclosure_date")
    if price_rows.empty:
        raise KeyError(f"No price data for: {code}")
    as_of = pd.Timestamp(price_rows["date"].max())
    pf = price_features(price_rows, as_of)
    ff = financial_features(financial_rows, as_of)
    metrics = {}
    if not pf.empty:
        metrics.update(pf.iloc[-1].to_dict())
    if not ff.empty:
        metrics.update(ff.iloc[-1].to_dict())
    earnings = data.get("earnings", pd.DataFrame())
    upcoming = pd.DataFrame()
    if not earnings.empty and "code" in earnings.columns:
        upcoming = earnings.loc[(earnings["code"] == canonical) & (earnings["date"] >= as_of)].sort_values("date").head(5)
    return {
        "company": company,
        "metrics": metrics,
        "prices": price_rows.tail(260).reset_index(drop=True),
        "financials": financial_rows.tail(20).reset_index(drop=True),
        "earnings": upcoming.reset_index(drop=True),
        "as_of": as_of,
    }
