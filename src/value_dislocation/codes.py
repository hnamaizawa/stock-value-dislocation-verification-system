from __future__ import annotations

import re


def normalize_tse_code(value: object) -> str:
    """Return the canonical five-character J-Quants/TSE code.

    Common four-digit codes such as 7203 are represented as 72030 by
    J-Quants V2. Non-numeric values are stripped to digits first.
    """
    text = re.sub(r"\D", "", str(value or "").strip())
    if len(text) == 4:
        return text + "0"
    if len(text) == 5:
        return text
    return text


def display_tse_code(value: object) -> str:
    code = normalize_tse_code(value)
    return code[:4] if len(code) == 5 and code.endswith("0") else code
