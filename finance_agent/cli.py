from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from finance_agent.agent import FinancialAnalysisAgent
from finance_agent.config import load_settings
from finance_agent.market_data import DEFAULT_TICKERS

app = typer.Typer(help="AI Agent untuk analisis laporan keuangan, berita, dan market global.")
console = Console()


@app.command()
def analyze(
    file_path: Path = typer.Argument(..., help="Path file laporan/berita yang akan dianalisis."),
    question: str | None = typer.Option(
        None,
        "--question",
        "-q",
        help="Pertanyaan atau fokus analisis tambahan.",
    ),
    tickers: list[str] = typer.Option(
        DEFAULT_TICKERS,
        "--tickers",
        "-t",
        help="Ticker market global atau aset yang ingin dipantau.",
    ),
    no_web_search: bool = typer.Option(
        False,
        "--no-web-search",
        help="Matikan web search bawaan OpenAI dan hanya gunakan file + yfinance.",
    ),
) -> None:
    settings = load_settings()
    agent = FinancialAnalysisAgent(settings)

    console.print(
        Panel.fit(
            f"File: {file_path}\nModel: {settings.openai_model}\nTickers: {', '.join(tickers)}",
            title="Menjalankan agent",
        )
    )
    result = agent.analyze(
        file_path=file_path,
        question=question,
        tickers=tickers,
        use_web_search=not no_web_search,
    )
    console.print(result)


if __name__ == "__main__":
    app()

