from __future__ import annotations

import io
import re
from dataclasses import dataclass
from typing import BinaryIO

import pandas as pd

from ..codes import normalize_tse_code


@dataclass(frozen=True)
class SBIImportResult:
    rows: pd.DataFrame
    encoding: str
    mapping: dict[str, str]
    warnings: list[str]


ALIASES = {
    "code": ["銘柄コード", "コード", "証券コード", "code", "ticker"],
    "name": ["銘柄名", "会社名", "名称", "name"],
    "market": ["市場", "市場区分", "market"],
    "price": ["現在値", "株価", "終値", "price", "close"],
    "per": ["PER", "予想PER", "per"],
    "pbr": ["PBR", "実績PBR", "pbr"],
    "equity_ratio": ["自己資本比率", "自己資本比率(%)", "equity_ratio"],
    "sales_growth": ["売上高成長率", "売上成長率", "sales_growth"],
    "op_growth": ["営業利益成長率", "営業増益率", "op_growth"],
}


def _norm(value: object) -> str:
    return re.sub(r"[\s　_()%％・/\-]", "", str(value)).lower()


def _decode(payload: bytes) -> tuple[str, str]:
    for encoding in ("utf-8-sig", "cp932", "shift_jis", "utf-8"):
        try:
            return payload.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return payload.decode("utf-8", errors="replace"), "utf-8-replace"


def _mapping(columns: list[str]) -> dict[str, str]:
    normalized = {_norm(c): c for c in columns}
    result: dict[str, str] = {}
    for target, aliases in ALIASES.items():
        for alias in aliases:
            key = _norm(alias)
            if key in normalized:
                result[target] = normalized[key]
                break
    return result


def parse_sbi_screening_csv(source: bytes | BinaryIO) -> SBIImportResult:
    payload = source if isinstance(source, bytes) else source.read()
    text, encoding = _decode(payload)
    frame = pd.read_csv(io.StringIO(text))
    mapping = _mapping([str(c) for c in frame.columns])
    if "code" not in mapping:
        raise ValueError("銘柄コード列を識別できません。SBIの検索結果CSVを指定してください。")
    out = pd.DataFrame()
    out["code"] = frame[mapping["code"]].astype(str).map(normalize_tse_code)
    for target, source_col in mapping.items():
        if target == "code":
            continue
        out[target] = frame[source_col]
    out = out.loc[out["code"].str.len() >= 4].drop_duplicates("code").reset_index(drop=True)
    warnings: list[str] = []
    if "name" not in mapping:
        warnings.append("銘柄名列を識別できなかったため、アプリ側の銘柄マスターで補完します。")
    return SBIImportResult(out, encoding, mapping, warnings)
