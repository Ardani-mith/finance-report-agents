from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from finance_agent.market_data import ForwardPriceOutcome, fetch_forward_price_outcome

DATASET_COLUMNS = [
    "created_at_utc",
    "ticker",
    "event_date",
    "event_type",
    "source",
    "intent_mode",
    "price_in_status",
    "outcome_context",
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
    intent_mode: str = ""
    price_in_status: str = ""
    outcome_context: str = ""
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


def load_events(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    normalized: list[dict[str, str]] = []
    for row in rows:
        normalized.append({column: row.get(column, "") for column in DATASET_COLUMNS})
    return normalized


def save_events(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=DATASET_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def enrich_price_labels(path: Path, ticker_suffix: str = ".JK") -> dict[str, int]:
    rows = load_events(path)
    updated = 0
    skipped = 0

    for row in rows:
        ticker = (row.get("ticker") or "").strip().upper()
        event_date = (row.get("event_date") or "").strip()
        if not ticker or not event_date:
            skipped += 1
            continue
        if row.get("price_t0") and row.get("price_t3") and row.get("price_t7"):
            skipped += 1
            continue

        market_ticker = ticker if ticker.startswith("^") or "=" in ticker or "-" in ticker else f"{ticker}{ticker_suffix}"
        outcome = fetch_forward_price_outcome(market_ticker, event_date)
        _write_outcome(row, outcome)
        updated += 1

    save_events(path, rows)
    return {"updated": updated, "skipped": skipped, "total": len(rows)}


def format_enrich_summary(result: dict[str, int], path: Path) -> str:
    return (
        f"Dataset diperbarui: {path}\n"
        f"Updated: {result['updated']}\n"
        f"Skipped: {result['skipped']}\n"
        f"Total rows: {result['total']}"
    )


def _write_outcome(row: dict[str, Any], outcome: ForwardPriceOutcome) -> None:
    row["price_t0"] = _fmt_num(outcome.price_t0)
    row["price_t3"] = _fmt_num(outcome.price_t3)
    row["return_3d_pct"] = _fmt_num(outcome.return_3d_pct)
    row["price_t7"] = _fmt_num(outcome.price_t7)
    row["return_7d_pct"] = _fmt_num(outcome.return_7d_pct)
    row["label_3d_up_10pct"] = (
        ""
        if outcome.label_3d_up_10pct is None
        else "true" if outcome.label_3d_up_10pct
        else "false"
    )


def _fmt_num(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.4f}"
