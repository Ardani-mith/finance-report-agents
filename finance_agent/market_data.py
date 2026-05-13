from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Iterable

import yfinance as yf
from pandas import DataFrame


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


@dataclass(frozen=True)
class ForwardPriceOutcome:
    ticker: str
    event_date: str
    price_t0: float | None
    price_t3: float | None
    return_3d_pct: float | None
    price_t7: float | None
    return_7d_pct: float | None
    label_3d_up_10pct: bool | None


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


def fetch_forward_price_outcome(
    ticker: str,
    event_date: str,
    date_to_t0: int = 0,
    date_to_t3: int = 3,
    date_to_t7: int = 7,
) -> ForwardPriceOutcome:
    event_dt = date.fromisoformat(event_date)
    history = _fetch_price_history(ticker=ticker, event_dt=event_dt)
    closes = _extract_close_series(history)

    price_t0 = _close_at_or_after(closes, event_dt, trading_offset=date_to_t0)
    price_t3 = _close_at_or_after(closes, event_dt, trading_offset=date_to_t3)
    price_t7 = _close_at_or_after(closes, event_dt, trading_offset=date_to_t7)

    return_3d = _calc_return_pct(price_t0, price_t3)
    return_7d = _calc_return_pct(price_t0, price_t7)
    label_3d = return_3d is not None and return_3d >= 10.0

    return ForwardPriceOutcome(
        ticker=ticker,
        event_date=event_date,
        price_t0=price_t0,
        price_t3=price_t3,
        return_3d_pct=return_3d,
        price_t7=price_t7,
        return_7d_pct=return_7d,
        label_3d_up_10pct=label_3d if return_3d is not None else None,
    )


def format_market_snapshot(snapshot: dict) -> str:
    lines = [
        f"Market snapshot as of UTC: {snapshot['as_of_utc']}",
        f"Provider: {snapshot['provider']}",
        f"Note: {snapshot['note']}",
        f"Regime hint: {_summarize_market_regime(snapshot)}",
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


def _fetch_price_history(ticker: str, event_dt: date) -> DataFrame:
    start = event_dt - timedelta(days=10)
    end = event_dt + timedelta(days=20)
    return yf.Ticker(ticker).history(start=start.isoformat(), end=end.isoformat(), auto_adjust=False)


def _extract_close_series(history: DataFrame) -> list[tuple[date, float]]:
    if history.empty or "Close" not in history:
        return []

    closes: list[tuple[date, float]] = []
    for idx, row in history.iterrows():
        close = _as_float(row.get("Close"))
        if close is None:
            continue
        closes.append((idx.date(), close))
    return closes


def _close_at_or_after(
    closes: list[tuple[date, float]],
    event_dt: date,
    trading_offset: int,
) -> float | None:
    eligible = [(dt, close) for dt, close in closes if dt >= event_dt]
    if len(eligible) <= trading_offset:
        return None
    return eligible[trading_offset][1]


def _calc_return_pct(price_start: float | None, price_end: float | None) -> float | None:
    if price_start in (None, 0) or price_end is None:
        return None
    return ((price_end - price_start) / price_start) * 100


def _summarize_market_regime(snapshot: dict) -> str:
    by_ticker = {item["ticker"]: item for item in snapshot.get("items", [])}

    def change(symbol: str) -> float | None:
        item = by_ticker.get(symbol)
        if not item:
            return None
        return item.get("change_percent")

    hints: list[str] = []

    vix = change("^VIX")
    dxy = change("DX-Y.NYB")
    tnx = change("^TNX")
    oil = change("CL=F")
    gold = change("GC=F")
    jkse = change("^JKSE")

    if vix is not None:
        if vix >= 5:
            hints.append("risk-off menguat")
        elif vix <= -5:
            hints.append("risk appetite membaik")
    if dxy is not None:
        if dxy > 0.3:
            hints.append("USD cenderung menguat")
        elif dxy < -0.3:
            hints.append("USD melemah")
    if tnx is not None:
        if tnx > 0.5:
            hints.append("yield AS naik, duration sensitif")
        elif tnx < -0.5:
            hints.append("yield AS turun, valuasi growth terbantu")
    if oil is not None:
        if oil > 1:
            hints.append("energi menguat")
        elif oil < -1:
            hints.append("energi melemah")
    if gold is not None:
        if gold > 1:
            hints.append("demand defensif/logam mulia naik")
    if jkse is not None:
        if jkse > 0.75:
            hints.append("IHSG cukup suportif")
        elif jkse < -0.75:
            hints.append("IHSG sedang tertekan")

    if not hints:
        return "campuran, tidak ada sinyal makro dominan dari snapshot singkat"
    return "; ".join(hints[:4])
