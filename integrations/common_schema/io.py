import csv
import json
from pathlib import Path
from typing import Dict, List

from .fields import COMMON_FIELDS


def _canonical_row(row: Dict) -> Dict:
    return {k: row.get(k) for k in COMMON_FIELDS}


def validate_rows(rows: List[Dict]) -> None:
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            raise RuntimeError(f"Row {idx} is not a JSON object.")
        missing = [k for k in COMMON_FIELDS if k not in row]
        if missing:
            raise RuntimeError(f"Row {idx} missing common schema fields: {missing}")


def write_jsonl(path: Path, rows: List[Dict]) -> None:
    validate_rows(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(_canonical_row(row)) + "\n")


def write_csv(path: Path, rows: List[Dict]) -> None:
    validate_rows(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COMMON_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(_canonical_row(row))
