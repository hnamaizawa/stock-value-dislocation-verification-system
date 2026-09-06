# Application Generator

## Purpose

`harness/app_blueprint.yaml` is the machine-readable definition of this application family. It defines capabilities, required files, safety invariants, runtime-state exclusions, and acceptance commands.

`scripts/generate_app.py` uses the current verified repository as the canonical template and creates a clean clone without `.env`, `.venv`, API keys, fetched market data, review records, portfolio files, or outputs.

## Windows usage

1. Run `setup_windows.cmd` in the canonical project.
2. Run `check_harness.cmd` and confirm every check passes.
3. Double-click `generate_similar_app.cmd`.
4. Enter the new application name.
5. Open the new folder under `generated`.
6. Run `setup_windows.cmd`, `check_harness.cmd`, and `run_real.cmd` in the generated application.

## Command-line usage

```powershell
.\.venv\Scripts\python.exe scripts\generate_app.py `
  --name "My Japanese Equity Research" `
  --destination C:\temp\my-japanese-equity-research
```

Use `--force` only when intentionally replacing the destination.

## Generated manifest

Every generated application contains `generation_manifest.json` with:

- blueprint and source version;
- generation timestamp;
- inherited safety invariants;
- copied file list hashes;
- generated package name.

## Self-test

```powershell
.\.venv\Scripts\python.exe scripts\generate_app.py --self-test
```

The harness runs this self-test automatically. A generation is rejected when required files are missing or secret/runtime state is copied.
