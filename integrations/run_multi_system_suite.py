#!/usr/bin/env python3
"""
Run each system's benchmark pipeline (shell commands), then merge normalized JSONL
outputs into one common-schema table (JSONL + CSV).

Usage:
  python3 integrations/run_multi_system_suite.py --config integrations/multi_system_suite.example.json

See integrations/multi_system_suite.example.json for the config format.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
INTEGRATIONS_ROOT = REPO_ROOT / "integrations"
if str(INTEGRATIONS_ROOT) not in sys.path:
    sys.path.insert(0, str(INTEGRATIONS_ROOT))

from common_schema.fields import COMMON_FIELDS  # noqa: E402
from common_schema.io import validate_rows  # noqa: E402


def _resolve_path(root: Path, path_text: str) -> Path:
    p = Path(path_text)
    return p if p.is_absolute() else root / p


def _run_shell(command: str, cwd: Path) -> None:
    result = subprocess.run(
        command,
        cwd=str(cwd),
        shell=True,
        executable="/bin/bash",
    )
    if result.returncode != 0:
        raise RuntimeError(f"Command failed ({result.returncode}): {command}")


def _load_jsonl_rows(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise RuntimeError(f"Missing JSONL output: {path}")
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    validate_rows(rows)
    return rows


def _write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COMMON_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in COMMON_FIELDS})


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run per-system benchmark steps and merge common-schema JSONL outputs."
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to JSON config (see integrations/multi_system_suite.example.json).",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue with remaining systems after a failure.",
    )
    args = parser.parse_args()

    config_path = _resolve_path(REPO_ROOT, args.config)
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    systems = cfg.get("systems", [])
    if not systems:
        raise SystemExit("Config must define a non-empty 'systems' list.")

    merged_rows: List[Dict[str, Any]] = []
    failures: List[str] = []

    for system in systems:
        system_id = system.get("id", "unknown")
        if not system.get("enabled", True):
            print(f"[skip] {system_id} (enabled=false)")
            continue

        print(f"[run] {system_id}")
        try:
            for step in system.get("steps", []):
                command = step["command"]
                step_cwd = _resolve_path(REPO_ROOT, step.get("cwd", "."))
                print(f"  -> {step.get('name', 'step')}: {command}")
                _run_shell(command, step_cwd)

            for output in system.get("normalized_jsonl_outputs", []):
                out_path = _resolve_path(REPO_ROOT, output)
                rows = _load_jsonl_rows(out_path)
                merged_rows.extend(rows)
                print(f"  -> loaded {len(rows)} rows from {out_path}")
        except Exception as exc:  # noqa: BLE001
            msg = f"{system_id}: {exc}"
            failures.append(msg)
            print(f"[error] {msg}")
            if not args.continue_on_error:
                break

    merged_cfg = cfg.get("merged_output", {})
    merged_jsonl = _resolve_path(
        REPO_ROOT,
        merged_cfg.get("jsonl", "multi-system-results/all_systems_common.jsonl"),
    )
    merged_csv = _resolve_path(
        REPO_ROOT,
        merged_cfg.get("csv", "multi-system-results/all_systems_common.csv"),
    )

    _write_jsonl(merged_jsonl, merged_rows)
    _write_csv(merged_csv, merged_rows)

    print(f"\nMerged rows: {len(merged_rows)}")
    print(f"JSONL: {merged_jsonl}")
    print(f"CSV:   {merged_csv}")

    if failures:
        print("\nFailures:")
        for f in failures:
            print(f"- {f}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
