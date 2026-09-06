from pathlib import Path

import yaml

from scripts.generate_app import BLUEPRINT, generate


def test_generator_creates_clean_reproducible_app(tmp_path: Path):
    destination = tmp_path / "generated-app"
    generated = generate(destination, "Generated Equity App")
    blueprint = yaml.safe_load(BLUEPRINT.read_text(encoding="utf-8"))
    for relative in blueprint["required_files"]:
        assert (generated / relative).exists()
    assert (generated / "generation_manifest.json").exists()
    assert not (generated / ".env").exists()
    assert not (generated / ".venv").exists()
    assert not list((generated / "data" / "raw").glob("**/*.csv"))
    assert (generated / "config" / "external_event_reviews").exists()
    assert not list((generated / "config" / "external_event_reviews").glob("*.json"))


def test_generator_does_not_copy_saved_external_event_reviews(tmp_path: Path):
    from scripts import generate_app

    review_dir = generate_app.ROOT / "config" / "external_event_reviews"
    review_dir.mkdir(parents=True, exist_ok=True)
    sentinel = review_dir / "9999.json"
    sentinel.write_text('{"approval_status":"approved","secret":"runtime-only"}', encoding="utf-8")
    try:
        destination = tmp_path / "generated-no-reviews"
        generated = generate(destination, "Generated Equity App")
        assert not (generated / "config" / "external_event_reviews" / "9999.json").exists()
    finally:
        sentinel.unlink(missing_ok=True)
