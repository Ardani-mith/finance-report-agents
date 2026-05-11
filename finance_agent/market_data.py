from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

import yfinance as yf


DEFAULT_TICKERS = [
    "^GSPC",
    "^IXIC",
    "^DJI",
    "^VIX",
    "DX-Y.NYB",
    "GC=F",
    "CL=F",
    "BTC-USD",
    "EURUSD=X",
    "JPY=X",
    "^TNX",
    "^JKSE",
]


@dataclass(frozen=True)
class MarketPoint:
    ticker: str
    name: str
    price: float | None
    change_percent: float | None
    currency: str | None
    market_state: str | None


def fetch_market_snapshot(tickers: Iterable[str] = DEFAULT_TICKERS) -> dict:
    points: list[MarketPoint] = []

    for ticker in tickers:
        symbol = ticker.strip()
        if not symbol:
            continue

        try:
            item = yf.Ticker(symbol)
            fast_info = item.fast_info
            info = item.get_info()
            previous_close = _as_float(
                fast_info.get("previous_close") or info.get("previousClose")
            )
            price = _as_float(
                fast_info.get("last_price")
                or info.get("regularMarketPrice")
                or info.get("currentPrice")
            )
            change_percent = None
            if price is not None and previous_close:
                change_percent = ((price - previous_close) / previous_close) * 100

            points.append(
                MarketPoint(
                    ticker=symbol,
                    name=info.get("shortName") or info.get("longName") or symbol,
                    price=price,
                    change_percent=change_percent,
                    currency=info.get("currency"),
                    market_state=info.get("marketState"),
                )
            )
        except Exception as exc:
            points.append(
                MarketPoint(
                    ticker=symbol,
                    name=f"ERROR: {exc}",
                    price=None,
                    change_percent=None,
                    currency=None,
                    market_state=None,
                )
            )

    return {
        "as_of_utc": datetime.now(timezone.utc).isoformat(),
        "provider": "Yahoo Finance via yfinance",
        "note": "Quotes may be delayed depending on exchange and symbol.",
        "items": [point.__dict__ for point in points],
    }


def format_market_snapshot(snapshot: dict) -> str:
    lines = [
        f"Market snapshot as of UTC: {snapshot['as_of_utc']}",
        f"Provider: {snapshot['provider']}",
        f"Note: {snapshot['note']}",
        "",
        "| Ticker | Name | Price | Change % | Currency | State |",
        "| --- | --- | ---: | ---: | --- | --- |",
    ]

    for item in snapshot["items"]:
        price = _format_number(item["price"])
        change = _format_number(item["change_percent"])
        lines.append(
            f"| {item['ticker']} | {item['name']} | {price} | {change} | "
            f"{item['currency'] or '-'} | {item['market_state'] or '-'} |"
        )

    return "\n".join(lines)


def _as_float(value: object) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_number(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:,.2f}"

