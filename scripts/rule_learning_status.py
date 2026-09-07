from __future__ import annotations

import argparse
import json
from pathlib import Path

from value_dislocation.strategy.rule_learning import (
    active_rules_path,
    clear_active_rule_overrides,
    learning_state_path,
    load_active_rule_overrides,
)

ROOT = Path(__file__).resolve().parents[1]


def _read(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="自動ルール学習の現在状態を表示し、明示操作時だけ適用中ルールを解除します。"
    )
    parser.add_argument(
        "--reset-active",
        action="store_true",
        help="学習済みruntime overlayを解除し、real_data.yamlの基準条件へ戻します。",
    )
    args = parser.parse_args()

    if args.reset_active:
        clear_active_rule_overrides(ROOT)
        print("学習済みruntime overlayを解除しました。次回設定読込から基準YAMLへ戻ります。")
        return 0

    state = _read(learning_state_path(ROOT))
    active = load_active_rule_overrides(ROOT)
    print("=== Automatic Rule Learning ===")
    print(f"status: {state.get('status', 'not_evaluated')}")
    print(f"updated_at: {state.get('updated_at', '-')}")
    print(f"mature_event_count: {state.get('mature_event_count', 0)}")
    print(f"active_rules_path: {active_rules_path(ROOT)}")
    print("active_screen_overrides:")
    print(json.dumps(active, ensure_ascii=False, indent=2))
    if state.get("last_applied_change"):
        print("last_applied_change:")
        print(json.dumps(state["last_applied_change"], ensure_ascii=False, indent=2))
    elif state.get("best_proposal"):
        print("best_proposal:")
        print(json.dumps(state["best_proposal"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
