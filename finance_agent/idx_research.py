from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import requests
from requests import RequestException
from bs4 import BeautifulSoup

SEARCH_URL = "https://duckduckgo.com/html/"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
)
MAX_DOWNLOAD_BYTES = 35 * 1024 * 1024


@dataclass(frozen=True)
class IDXReportRequest:
    ticker: str
    period: str | None = None
    focus: str | None = None


@dataclass(frozen=True)
class DownloadedReport:
    path: Path
    source_url: str
    title: str


class IDXReportNotFound(RuntimeError):
    pass


def parse_idx_command(text: str) -> IDXReportRequest:
    parts = text.strip().split(maxsplit=2)
    if not parts:
        raise ValueError("Format: /idx TICKER [PERIODE/FOKUS]. Contoh: /idx ESIP FY2025 cek arus kas")

    ticker = parts[0].upper().strip()
    if not re.fullmatch(r"[A-Z0-9.:-]{2,12}", ticker):
        raise ValueError("Ticker tidak valid. Contoh: /idx ESIP FY2025")

    period = None
    focus = None
    if len(parts) >= 2:
        remainder = parts[1] if len(parts) == 2 else f"{parts[1]} {parts[2]}"
        period_match = re.search(r"\b(FY|Q[1-4]|TW[1-4])\s*20\d{2}\b|\b20\d{2}\b", remainder, re.I)
        if period_match:
            period = period_match.group(0).upper().replace(" ", "")
        focus = remainder.strip()

    return IDXReportRequest(ticker=ticker, period=period, focus=focus)


def find_and_download_idx_report(request: IDXReportRequest, output_dir: Path) -> DownloadedReport:
    output_dir.mkdir(parents=True, exist_ok=True)
    candidates = search_idx_report_candidates(request)
    if not candidates:
        raise IDXReportNotFound(_not_found_message(request))

    errors: list[str] = []
    for candidate in candidates[:8]:
        url = candidate["url"]
        try:
            downloaded = download_pdf(url, output_dir, request.ticker, candidate.get("title") or url)
            return downloaded
        except Exception as exc:
            errors.append(f"{url}: {exc}")

    detail = "\n".join(errors[:3])
    raise IDXReportNotFound(
        f"Laporan {request.ticker} belum berhasil didownload. Detail kandidat gagal:\n{detail}"
    )


def search_idx_report_candidates(request: IDXReportRequest) -> list[dict[str, str]]:
    queries = _build_queries(request)
    seen: set[str] = set()
    results: list[dict[str, str]] = []

    for query in queries:
        try:
            response = requests.get(
                SEARCH_URL,
                params={"q": query},
                headers={"User-Agent": USER_AGENT},
                timeout=20,
            )
            response.raise_for_status()
        except RequestException as exc:
            raise IDXReportNotFound(
                "Pencarian laporan publik sedang tidak bisa diakses dari mesin ini. "
                "Coba lagi nanti, gunakan periode yang lebih spesifik, atau upload PDF laporan langsung."
            ) from exc

        soup = BeautifulSoup(response.text, "html.parser")

        for link in soup.select("a.result__a"):
            href = link.get("href") or ""
            url = _normalize_duckduckgo_url(href)
            title = link.get_text(" ", strip=True)
            if not url or url in seen:
                continue
            if _looks_like_report_url(url, title, request):
                seen.add(url)
                results.append({"url": url, "title": title})

    return results


def download_pdf(url: str, output_dir: Path, ticker: str, title: str) -> DownloadedReport:
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=45, stream=True)
    response.raise_for_status()

    content_type = response.headers.get("content-type", "").lower()
    if "pdf" not in content_type and not url.lower().split("?", 1)[0].endswith(".pdf"):
        raise ValueError(f"URL bukan PDF: content-type={content_type or 'unknown'}")

    file_name = _safe_filename(f"{ticker}_{title}")[:140] + ".pdf"
    path = output_dir / file_name
    bytes_written = 0
    with path.open("wb") as handle:
        for chunk in response.iter_content(chunk_size=1024 * 256):
            if not chunk:
                continue
            bytes_written += len(chunk)
            if bytes_written > MAX_DOWNLOAD_BYTES:
                raise ValueError("PDF terlalu besar untuk mode Telegram saat ini")
            handle.write(chunk)

    if bytes_written < 1024:
        raise ValueError("PDF terlalu kecil atau gagal didownload")

    return DownloadedReport(path=path, source_url=url, title=title)


def _build_queries(request: IDXReportRequest) -> list[str]:
    period = request.period or "financial statement annual report"
    ticker = request.ticker
    return [
        f"site:idx.co.id {ticker} {period} laporan keuangan filetype:pdf",
        f"site:idx.co.id {ticker} {period} annual report filetype:pdf",
        f"{ticker} {period} laporan keuangan idx pdf",
        f"{ticker} {period} annual report idx pdf",
    ]


def _looks_like_report_url(url: str, title: str, request: IDXReportRequest) -> bool:
    haystack = f"{url} {title}".lower()
    ticker = request.ticker.lower()
    if ticker not in haystack:
        return False
    report_words = ["laporan", "financial", "annual", "report", "keuangan", "quarter", "interim"]
    if not any(word in haystack for word in report_words):
        return False
    if request.period and request.period.lower().replace("fy", "") not in haystack.replace(" ", ""):
        return any(word in haystack for word in ["annual", "tahunan", "financial", "keuangan"])
    return True


def _normalize_duckduckgo_url(href: str) -> str:
    if not href:
        return ""
    parsed = urlparse(href)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        return unquote(target)
    if href.startswith("//"):
        return "https:" + href
    return href


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_")
    return cleaned or "idx_report"


def _not_found_message(request: IDXReportRequest) -> str:
    period = f" {request.period}" if request.period else ""
    return (
        f"Saya belum menemukan PDF laporan {request.ticker}{period} dari pencarian publik. "
        "Coba tulis periode lebih spesifik, misalnya /idx ESIP FY2025, atau upload PDF laporan langsung."
    )
