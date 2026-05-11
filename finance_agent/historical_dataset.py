from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable

DATASET_COLUMNS = [
    "created_at_utc",
    "ticker",
    "event_date",
    "event_type",
    "source",
    "period",
    "bullish_score",
    "model_verdict",
    "features_json",
    "price_t0",
    "price_t3",
    "return_3d_pct",
    "price_t7",
    "return_7d_pct",
    "label_3d_up_10pct",
    "notes",
]


@dataclass(frozen=True)
class HistoricalEvent:
    ticker: str
    event_date: str
    event_type: str
    source: str
    period: str = ""
    bullish_score: str = ""
    model_verdict: str = ""
    features_json: str = "{}"
    price_t0: str = ""
    price_t3: str = ""
    return_3d_pct: str = ""
    price_t7: str = ""
    return_7d_pct: str = ""
    label_3d_up_10pct: str = ""
    notes: str = ""


def append_event(path: Path, event: HistoricalEvent) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    row = {"created_at_utc": datetime.now(timezone.utc).isoformat(), **asdict(event)}
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=DATASET_COLUMNS)
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def dataset_template(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=DATASET_COLUMNS)
        writer.writeheader()
