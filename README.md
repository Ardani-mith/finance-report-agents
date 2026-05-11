# AI Agent Analisis Laporan Keuangan dan Market Global

Starter project Python untuk menganalisis laporan keuangan atau berita dari file yang Anda kirim, lalu menggabungkannya dengan kondisi market global terbaru.

## Fitur

- Membaca file teks, Markdown, CSV, JSON, dan PDF.
- Untuk PDF, agent mengekstrak teks secara lokal lalu mengirim hasil ekstraksi ke NVIDIA hosted API.
- Mengambil snapshot market global melalui Yahoo Finance (`yfinance`).
- Menghasilkan analisis forensik laporan keuangan: temuan kritis, narasi investasi, verdict keyakinan, risiko tersembunyi, dan data yang belum tersedia.


## Profil Analisis

Agent memakai profil `analisis-laporan-keuangan`: membaca laporan secara forensik, memeriksa footnotes, MD&A, kualitas arus kas, related party, off-balance sheet, perubahan akuntansi, auditor, segment reporting, status koreksi/revisi, dan sinyal khusus micro-cap IDX seperti margin akselerasi, OCF/Net Income, neraca ultra-bersih, serta anomali effective tax rate.

Format output utama:

- 📍 Temuan Kritis
- 📊 Narasi Investasi
- 🎯 Level Keyakinan
- ⚠️ Risiko Tersembunyi
- Data Tidak Tersedia

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Isi `NVIDIA_API_KEY` dan `TELEGRAM_BOT_TOKEN` di `.env`.

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

## Sumber Implementasi NVIDIA

Project ini memakai NVIDIA NIM hosted API melalui endpoint OpenAI-compatible `chat.completions`. PDF diekstrak lokal menjadi teks sebelum dikirim ke model NVIDIA.





## Dev Request dari Telegram

Bot mendukung request coding dari Telegram tanpa langsung mengubah repository atau push ke GitHub:

```text
/dev_request tambahkan fitur X
/dev_requests
```

Request disimpan di `dev_requests/inbox.jsonl` dengan aturan:

- `auto_allow_agent_changes=true`: Codex boleh mengerjakan perubahan yang diminta.
- `review_required_before_github_push=true`: perubahan wajib direview sebelum push.
- `github_push_allowed=false`: bot/Codex tidak boleh push otomatis ke GitHub.

Setelah request diproses oleh Codex, bot Python perlu dijalankan ulang agar command baru aktif.

## Bullish Scoring dan Training Dataset

Untuk input manual seperti post StockbitReports yang Anda paste sendiri, bot mendukung:

```text
/score INI TEKS BERITA ATAU POST
```

Outputnya memberi bullish score 0-100, ticker terdeteksi, horizon 3/7 hari, alasan skor, red flags, dan fitur yang layak disimpan untuk dataset historis.

Untuk jangka menengah, dataset historis disiapkan di `data/historical_events.csv`. Buat template lewat Telegram:

```text
/dataset_template
```

Label utama yang disiapkan: apakah setelah event laporan/berita muncul saham naik minimal 10% dalam 3 hari bursa (`label_3d_up_10pct`). Dataset ini nantinya bisa dipakai untuk backtest, kalibrasi scoring, atau training model klasifikasi.

## Index Alpha

Project ini mendukung Index Alpha untuk broker summary IDX. Dokumentasi Index Alpha menyebut autentikasi memakai Bearer token, base URL `https://api.indexalpha.id/`, endpoint `GET /stocks/broker-summary`, dan endpoint `GET /usage`. Data broker summary Regular Market diperbarui setiap hari bursa pukul 12:00 GMT / 19:00 WIB, dengan histori tersedia mulai Juni 2025.

Tambahkan ke `.env`:

```bash
INDEX_ALPHA_API_KEY=ia_live-your-api-key
INDEX_ALPHA_BASE_URL=https://api.indexalpha.id
```

Command Telegram:

```text
/indexalpha
/broker BBCA 2026-03-26 2026-03-26 all
```

Parameter investor: `all`, `f` untuk foreign, `d` untuk domestic, atau `or` sesuai dokumentasi Index Alpha.

## Research Mandiri IDX

Bot mendukung command best-effort untuk mencari laporan publik IDX tanpa API resmi:

```text
/idx ESIP FY2025 cek kualitas arus kas
```

Alurnya: bot mencari kandidat PDF laporan publik, mendownload PDF yang paling relevan, mengekstrak teks, lalu menjalankan analisis forensik. Mode ini tidak seandal API resmi karena website/sumber publik bisa berubah, hasil pencarian bisa melewatkan dokumen, dan beberapa PDF scan membutuhkan OCR. Jika gagal, upload PDF laporan secara manual.

Untuk production, lebih stabil memakai API data pasar/filing pihak ketiga atau pipeline download dokumen IDX yang dikelola sendiri.

## Telegram Bot

Untuk menjalankan bot ini, gunakan API key dari NVIDIA API Catalog dan token Telegram dari BotFather.

1. Buat bot di Telegram lewat `@BotFather`, lalu ambil token bot.
2. Isi `.env`:

```bash
NVIDIA_API_KEY=nvapi-your-api-key
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_MODEL=meta/llama-3.3-70b-instruct
TELEGRAM_BOT_TOKEN=123456789:your-telegram-bot-token
```

3. Jalankan bot:

```bash
python3 -m finance_agent.telegram_bot
```

Cara pakai di Telegram:

- Kirim `/start` untuk membuka instruksi.
- Kirim `/analyze` diikuti teks berita untuk analisis cepat.
- Kirim file PDF/TXT/CSV/JSON/MD dan gunakan caption sebagai fokus analisis.

## Deploy VPS

Setelah perubahan terbaru sudah di-push ke GitHub, jalankan ini di VPS:

```bash
cd ~/finance-report-agents
./scripts/deploy_vps.sh
```

Script ini akan:

- `git pull --ff-only`
- membuat `.venv` jika belum ada
- install/update dependency dari `requirements.txt`
- memastikan `.env` ada
- restart bot di `screen` session `finance_report_bot`

Jika folder project di VPS bukan `~/finance-report-agents`, jalankan:

```bash
APP_DIR=/path/ke/finance-report-agents ./scripts/deploy_vps.sh
```
