from __future__ import annotations

from pathlib import Path

from openai import OpenAI

from finance_agent.config import Settings, require_nvidia_key
from finance_agent.document_loader import extract_document_text
from finance_agent.market_data import DEFAULT_TICKERS, fetch_market_snapshot, format_market_snapshot
from finance_agent.prompts import SYSTEM_PROMPT, build_bullish_score_prompt, build_user_prompt


class FinancialAnalysisAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = OpenAI(
            base_url=settings.nvidia_base_url,
            api_key=require_nvidia_key(settings),
        )

    def analyze(
        self,
        file_path: Path,
        question: str | None = None,
        tickers: list[str] | None = None,
        use_web_search: bool = False,
    ) -> str:
        market_snapshot = fetch_market_snapshot(tickers or DEFAULT_TICKERS)
        formatted_market = format_market_snapshot(market_snapshot)
        document_text = extract_document_text(file_path)
        document_type = detect_document_type(file_path=file_path, document_text=document_text, question=question)
        prompt = build_user_prompt(
            question=question,
            market_snapshot=formatted_market,
            document_type=document_type,
            file_name=file_path.name,
        )

        user_content = f"""
{prompt}

Isi dokumen yang diekstrak dari file {file_path.name}:
{document_text}
""".strip()

        return self._chat(user_content)

    def analyze_text(
        self,
        question: str,
        tickers: list[str] | None = None,
        use_web_search: bool = False,
    ) -> str:
        market_snapshot = fetch_market_snapshot(tickers or DEFAULT_TICKERS)
        formatted_market = format_market_snapshot(market_snapshot)
        prompt = build_user_prompt(question=question, market_snapshot=formatted_market)
        return self._chat(prompt)

    def score_text(self, text: str, source: str = "manual") -> str:
        prompt = build_bullish_score_prompt(text=text, source=source)
        return self._chat(prompt)

    def _chat(self, user_content: str) -> str:
        response = self.client.chat.completions.create(
            model=self.settings.nvidia_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content or ""


def detect_document_type(file_path: Path, document_text: str, question: str | None = None) -> str:
    haystack = "\n".join([file_path.name, question or "", document_text[:6000]]).lower()

    if any(keyword in haystack for keyword in [
        "laporan keuangan",
        "financial statements",
        "statement of profit or loss",
        "arus kas",
        "catatan atas laporan keuangan",
        "balance sheet",
        "neraca",
    ]):
        return "financial_report"

    if any(keyword in haystack for keyword in [
        "keterbukaan informasi",
        "rights issue",
        "private placement",
        "akuisisi",
        "merger",
        "divestasi",
        "tender offer",
        "buyback",
        "penambahan modal",
    ]):
        return "corporate_action"

    if any(keyword in haystack for keyword in [
        "presentation",
        "public expose",
        "paparan publik",
        "investor presentation",
        "company presentation",
        "corporate presentation",
    ]):
        return "presentation"

    if any(keyword in haystack for keyword in [
        "news",
        "berita",
        "breaking",
        "headline",
        "press release",
        "media release",
    ]):
        return "news"

    return "general"
