from __future__ import annotations

from pathlib import Path

from openai import OpenAI

from finance_agent.config import Settings
from finance_agent.document_loader import build_file_content
from finance_agent.market_data import DEFAULT_TICKERS, fetch_market_snapshot, format_market_snapshot
from finance_agent.prompts import SYSTEM_PROMPT, build_user_prompt


class FinancialAnalysisAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = OpenAI(api_key=settings.openai_api_key)

    def analyze(
        self,
        file_path: Path,
        question: str | None = None,
        tickers: list[str] | None = None,
        use_web_search: bool = True,
    ) -> str:
        market_snapshot = fetch_market_snapshot(tickers or DEFAULT_TICKERS)
        formatted_market = format_market_snapshot(market_snapshot)
        file_content = build_file_content(file_path)

        content = [
            *file_content,
            {
                "type": "input_text",
                "text": build_user_prompt(question=question, market_snapshot=formatted_market),
            },
        ]

        tools = [{"type": "web_search"}] if use_web_search else []
        response = self.client.responses.create(
            model=self.settings.openai_model,
            instructions=SYSTEM_PROMPT,
            input=[{"role": "user", "content": content}],
            tools=tools,
        )

        return response.output_text
