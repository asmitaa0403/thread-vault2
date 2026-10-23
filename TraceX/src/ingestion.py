from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

DATASET_FILES = {
    "fir": DATA_DIR / "fir.csv",
    "cdr": DATA_DIR / "cdr.csv",
    "transactions": DATA_DIR / "transactions.csv",
    "social": DATA_DIR / "social.csv",
}

REQUIRED_COLUMNS = {
    "fir": ["case_id", "fir_id", "date", "location", "description"],
    "cdr": ["case_id", "cdr_id", "timestamp", "caller", "receiver", "duration_seconds"],
    "transactions": [
        "case_id",
        "transaction_id",
        "timestamp",
        "sender",
        "receiver",
        "amount",
        "description",
    ],
    "social": [
        "case_id",
        "post_id",
        "timestamp",
        "author",
        "mentioned_person",
        "location",
        "content",
    ],
}


def _load_dataset(name: str) -> pd.DataFrame:
    path = DATASET_FILES[name]
    if not path.exists():
        raise FileNotFoundError(f"Missing dataset file: {path}")

    df = pd.read_csv(path)
    required = REQUIRED_COLUMNS[name]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"Dataset '{name}' is missing required columns: {missing}")

    if "case_id" not in df.columns:
        raise ValueError(f"Dataset '{name}' is missing 'case_id'")

    return df


def get_available_cases() -> List[str]:
    """Return sorted case IDs present across all available synthetic datasets."""
    case_ids = set()
    for dataset_name in DATASET_FILES:
        path = DATASET_FILES[dataset_name]
        if not path.exists():
            continue
        df = pd.read_csv(path)
        if "case_id" not in df.columns:
            continue
        case_ids.update(df["case_id"].dropna().astype(str).str.strip().tolist())
    return sorted(case_ids)


def load_case(case_id: str) -> Dict[str, object]:
    """Load one synthetic case from the CSV datasets and return the raw records."""
    normalized_case_id = str(case_id).strip()
    if not normalized_case_id:
        raise ValueError("case_id cannot be empty")

    datasets: Dict[str, pd.DataFrame] = {}
    counts: Dict[str, int] = {}

    for name in DATASET_FILES:
        df = _load_dataset(name)
        filtered = df[df["case_id"].astype(str).str.strip() == normalized_case_id].copy()
        datasets[name] = filtered
        counts[name] = len(filtered)

    return {
        "case_id": normalized_case_id,
        "datasets": datasets,
        "counts": counts,
    }
