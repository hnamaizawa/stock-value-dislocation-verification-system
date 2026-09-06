from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = ROOT / "harness" / "app_blueprint.yaml"
EXCLUDED_NAMES = {
    ".env", ".venv", ".git", ".pytest_cache", "__pycache__", "outputs", "generated"
}
EXCLUDED_RELATIVE = {
    Path("data/raw"), Path("data/curated"), Path("data/staged"), Path("data/reviews"),
    Path("data/portfolio"), Path("data/history"), Path("config/user_profiles"), Path("config/external_event_reviews"), Path("config/ui_preferences.json"),
}


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip()).strip("-").lower()
    return slug or "japanese-equity-research-app"


def should_ignore(path: Path) -> bool:
    try:
        rel = path.relative_to(ROOT)
    except ValueError:
        return False
    if any(part in EXCLUDED_NAMES for part in rel.parts):
        return True
    return any(rel == excluded or excluded in rel.parents for excluded in EXCLUDED_RELATIVE)


def copy_project(destination: Path) -> list[str]:
    copied: list[str] = []
    for source in ROOT.rglob("*"):
        if should_ignore(source):
            continue
        rel = source.relative_to(ROOT)
        target = destination / rel
        if source.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(rel.as_posix())
    for rel in ["outputs", "outputs/real", "data/raw", "data/curated", "data/staged", "data/reviews", "data/portfolio", "data/history", "config/user_profiles", "config/external_event_reviews"]:
        (destination / rel).mkdir(parents=True, exist_ok=True)
    return copied


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def customize(destination: Path, app_name: str, package_name: str) -> None:
    pyproject = destination / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    text = re.sub(r'^name = ".*"$', f'name = "{package_name}"', text, count=1, flags=re.MULTILINE)
    pyproject.write_text(text, encoding="utf-8")

    readme = destination / "README.md"
    text = readme.read_text(encoding="utf-8")
    text = re.sub(r"^# .+$", f"# {app_name}", text, count=1, flags=re.MULTILINE)
    readme.write_text(text, encoding="utf-8")


def validate(destination: Path, blueprint: dict) -> list[str]:
    missing = [p for p in blueprint["required_files"] if not (destination / p).exists()]
    if missing:
        raise RuntimeError(f"Generated app is incomplete: {missing}")
    forbidden = [destination / ".env", destination / ".venv"]
    leaked = [str(p) for p in forbidden if p.exists()]
    if leaked:
        raise RuntimeError(f"Secrets/runtime state leaked into generated app: {leaked}")
    return missing


def generate(destination: Path, app_name: str, force: bool = False) -> Path:
    blueprint = yaml.safe_load(BLUEPRINT.read_text(encoding="utf-8"))
    destination = destination.resolve()
    if destination == ROOT or ROOT in destination.parents and destination.name == "":
        raise ValueError("Destination must be a separate application folder")
    if destination.exists():
        if not force:
            raise FileExistsError(f"Destination already exists: {destination}")
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    copied = copy_project(destination)
    package_name = slugify(app_name)
    customize(destination, app_name, package_name)
    validate(destination, blueprint)

    file_hashes = {
        rel: sha256(destination / rel)
        for rel in copied
        if (destination / rel).is_file() and not rel.endswith("generation_manifest.json")
    }
    manifest = {
        "schema_version": "1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "generator_blueprint": blueprint["blueprint_name"],
        "blueprint_version": blueprint["blueprint_version"],
        "app_name": app_name,
        "package_name": package_name,
        "source_project_version": "0.6.40",
        "safety_invariants": blueprint["non_negotiable_invariants"],
        "copied_file_count": len(file_hashes),
        "file_hashes": file_hashes,
    }
    (destination / "generation_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return destination


def self_test() -> None:
    with tempfile.TemporaryDirectory(prefix="value-dislocation-generator-") as tmp:
        dest = Path(tmp) / "generated-app"
        generated = generate(dest, "Generated Japanese Equity Research App")
        if not (generated / "generation_manifest.json").exists():
            raise RuntimeError("generation_manifest.json was not created")
        if (generated / ".env").exists():
            raise RuntimeError(".env must not be copied")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a reproducible Japanese equity research app")
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--name", default="Japanese Equity Value Dislocation Research")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        print("Generator self-test passed.")
        return 0
    destination = args.destination or (ROOT / "generated" / slugify(args.name))
    generated = generate(destination, args.name, force=args.force)
    print(f"Generated app: {generated}")
    print("Next: run setup_windows.cmd, check_harness.cmd, then run_real.cmd in that folder.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
