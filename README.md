# AI Agent Analisis Laporan Keuangan dan Market Global

Starter project Python untuk menganalisis laporan keuangan atau berita dari file yang Anda kirim, lalu menggabungkannya dengan kondisi market global terbaru.

## Fitur

- Membaca file teks, Markdown, CSV, JSON, dan PDF.
- Untuk PDF, agent mengirim file langsung ke OpenAI Responses API agar model bisa membaca teks dan tampilan halaman.
- Mengambil snapshot market global melalui Yahoo Finance (`yfinance`).
- Menghasilkan analisis terstruktur: ringkasan, metrik penting, dampak market, risiko, katalis, skenario, dan pertanyaan lanjutan.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Isi `OPENAI_API_KEY` di `.env`.

## Cara Menjalankan

```bash
python -m finance_agent.cli analyze path/to/laporan.pdf --tickers AAPL MSFT ^GSPC GC=F CL=F
```

Contoh untuk berita teks:

```bash
python -m finance_agent.cli analyze berita.txt --question "Apa dampaknya ke IHSG dan saham bank besar?"
```

## Catatan Data Market

Data market dari `yfinance` bergantung pada ketersediaan Yahoo Finance dan bisa delayed, terutama untuk beberapa bursa. Untuk kebutuhan trading production, sambungkan modul `market_data.py` ke vendor data resmi seperti Bloomberg, Refinitiv, Polygon, Twelve Data, Alpha Vantage, atau broker API.

## Sumber Implementasi OpenAI

Project ini mengikuti pola OpenAI Responses API: model dapat menerima `input_file` dari Files API dan tools seperti web/file search tersedia di Responses API. Dokumentasi resmi: [File inputs](https://developers.openai.com/api/docs/guides/file-inputs), [File search](https://developers.openai.com/api/docs/guides/tools-file-search), dan [Responses API](https://platform.openai.com/docs/api-reference/responses).

