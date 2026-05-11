from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import requests

from finance_agent.config import Settings, require_index_alpha_key


@dataclass(frozen=True)
class BrokerSummaryRequest:
    ticker: str
    date_from: date
    date_to: date
    investor: str = "all"


class IndexAlphaClient:
    def __init__(self, settings: Settings) -> None:
        self.base_url = settings.index_alpha_base_url.rstrip("/")
        self.api_key = require_index_alpha_key(settings)

    def usage(self) -> dict[str, Any]:
        return self._get("/usage")

    def broker_summary(self, request: BrokerSummaryRequest) -> dict[str, Any]:
        if request.investor not in {"all", "f", "or", "d"}:
            raise ValueError("Investor harus salah satu: all, f, or, d")

        return self._get(
            "/stocks/broker-summary",
            params={
                "ticker": request.ticker.upper(),
                "from": request.date_from.isoformat(),
                "to": request.date_to.isoformat(),
                "investor": request.investor,
            },
        )

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = requests.get(
            f"{self.base_url}{path}",
            headers={
                "accept": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("success", False):
            raise RuntimeError(payload.get("error") or "Index Alpha API request gagal")
        return payload


def parse_broker_summary_args(args: list[str]) -> BrokerSummaryRequest:
    if len(args) < 2:
        raise ValueError("Format: /broker TICKER FROM [TO] [INVESTOR]. Contoh: /broker BBCA 2026-03-26 2026-03-26 all")

    ticker = args[0].upper()
    date_from = date.fromisoformat(args[1])
    date_to = date.fromisoformat(args[2]) if len(args) >= 3 and _looks_like_date(args[2]) else date_from
    investor = args[3].lower() if len(args) >= 4 else "all"
    if len(args) == 3 and not _looks_like_date(args[2]):
        investor = args[2].lower()

    return BrokerSummaryRequest(ticker=ticker, date_from=date_from, date_to=date_to, investor=investor)


def format_usage(payload: dict[str, Any]) -> str:
    data = payload.get("data", {})
    return (
        "Index Alpha Usage\n"
        f"Monthly limit: {data.get('monthly_limit', '-')}\n"
        f"Current usage: {data.get('current_usage', '-')}\n"
        f"Remaining: {data.get('remaining', '-')}\n"
        f"Reset date: {data.get('reset_date', '-')}"
    )


def format_broker_summary(payload: dict[str, Any], limit: int = 15) -> str:
    rows = payload.get("data", [])
    if not rows:
        return "Tidak ada data broker summary dari Index Alpha untuk parameter tersebut."

    enriched = []
    for row in rows:
        buy_value = float(row.get("buy_value") or 0)
        sell_value = float(row.get("sell_value") or 0)
        enriched.append((buy_value - sell_value, row))
    enriched.sort(reverse=True, key=lambda item: abs(item[0]))

    lines = [
        "Index Alpha Broker Summary",
        "Broker | Net Value | Buy Value | Sell Value | Buy Avg | Sell Avg",
        "--- | ---: | ---: | ---: | ---: | ---:",
    ]
    for net_value, row in enriched[:limit]:
        lines.append(
            f"{row.get('code', '-')} | {_fmt(net_value)} | {_fmt(row.get('buy_value'))} | "
            f"{_fmt(row.get('sell_value'))} | {_fmt(row.get('buy_avg'))} | {_fmt(row.get('sell_avg'))}"
        )

    return "\n".join(lines)


def _looks_like_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def _fmt(value: Any) -> str:
    try:
        return f"{float(value):,.0f}"
    except (TypeError, ValueError):
        return "-"
