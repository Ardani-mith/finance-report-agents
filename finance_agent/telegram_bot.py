from __future__ import annotations

import fcntl
import logging
import sys
import tempfile
from pathlib import Path

from openai import APIConnectionError, APIStatusError, AuthenticationError, RateLimitError

from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

from finance_agent.agent import FinancialAnalysisAgent
from finance_agent.config import load_settings, require_telegram_token
from finance_agent.document_loader import SUPPORTED_FILE_EXTENSIONS, extract_document_text
from finance_agent.dev_requests import create_dev_request, format_dev_request, format_dev_request_list, list_dev_requests
from finance_agent.event_drafts import (
    append_event_draft,
    approve_event_draft,
    create_event_draft_from_document,
    format_event_draft,
    format_event_draft_list,
    list_event_drafts,
    reject_event_draft,
)
from finance_agent.idx_research import IDXReportNotFound, find_and_download_idx_report, parse_idx_command
from finance_agent.index_alpha import IndexAlphaClient, format_broker_summary, format_usage, parse_broker_summary_args
from finance_agent.historical_dataset import (
    HistoricalEvent,
    append_event,
    dataset_template,
    enrich_price_labels,
    format_enrich_summary,
)

MAX_TELEGRAM_MESSAGE_LENGTH = 3900
logger = logging.getLogger(__name__)
_lock_file = None


def acquire_single_instance_lock() -> None:
    global _lock_file
    lock_path = Path("logs/telegram_bot.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    _lock_file = lock_path.open("w")
    try:
        fcntl.flock(_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print(
            "Bot Telegram sudah berjalan di proses lain. "
            "Hentikan proses lama dulu sebelum menjalankan ulang.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    _lock_file.write(str(Path.cwd()))
    _lock_file.flush()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Kirim file laporan/berita, lalu saya analisis dengan konteks market global.\n\n"
        "Perintah:\n"
        "/analyze pertanyaan Anda - analisis teks langsung\n"
        "/idx TICKER PERIODE - cari laporan IDX dan analisis\n"
        "/broker TICKER FROM [TO] [INVESTOR] - broker summary Index Alpha\n"
        "/indexalpha - cek quota Index Alpha\n"
        "/score TEKS - beri bullish score untuk berita/post\n"
        "/dataset_template - buat template dataset historis\n"
        "/add_event TICKER YYYY-MM-DD TYPE - simpan event historis\n"
        "/label_dataset - isi label harga t+3 dan t+7\n"
        "/approve_event ID - setujui draft event\n"
        "/reject_event ID - tolak draft event\n"
        "/pending_events - lihat draft event\n"
        "/dev_request TEKS - simpan request coding untuk Codex\n"
        "/dev_requests - lihat request terakhir\n"
        "/help - cara pakai"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    extensions = ", ".join(sorted(SUPPORTED_FILE_EXTENSIONS))
    await update.message.reply_text(
        "Cara pakai:\n"
        "1. Kirim PDF/TXT/CSV/JSON/MD berisi laporan atau berita.\n"
        "2. Tambahkan caption sebagai fokus analisis, misalnya: dampak ke IHSG dan USD/IDR.\n"
        "3. Atau kirim /analyze diikuti teks berita.\n"
        "4. Pakai /idx TICKER PERIODE untuk mencoba mencari laporan publik IDX.\n"
        "5. Pakai /broker BBCA 2026-03-26 2026-03-26 all untuk broker summary Index Alpha.\n"
        "6. Pakai /indexalpha untuk cek quota API.\n"
        "7. Pakai /score lalu paste berita/post untuk bullish score.\n"
        "8. Pakai /add_event untuk menyimpan event ke dataset historis.\n"
        "9. Pakai /label_dataset untuk isi outcome harga otomatis.\n"
        "10. Draft event akan dibuat otomatis setelah analisis dokumen; approve dengan /approve_event.\n"
        "11. Pakai /dev_request untuk menyimpan permintaan coding tanpa push GitHub.\n\n"
        "Contoh: /idx ESIP FY2025 cek kualitas arus kas\n"
        f"Format file didukung: {extensions}"
    )


async def approve_event(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Format: /approve_event ID")
        return
    try:
        approved = approve_event_draft(context.args[0])
    except Exception as exc:
        await _reply_error(update, exc)
        return
    await update.message.reply_text(
        f"Event disetujui dan masuk dataset: {approved['ticker']} {approved['event_date']} {approved['event_type']}"
    )


async def reject_event(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Format: /reject_event ID")
        return
    try:
        rejected = reject_event_draft(context.args[0])
    except Exception as exc:
        await _reply_error(update, exc)
        return
    await update.message.reply_text(
        f"Draft event ditolak: {rejected['id']}"
    )


async def show_pending_events(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    rows = list_event_drafts()
    await update.message.reply_text(format_event_draft_list(rows))


async def save_dev_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = " ".join(context.args).strip()
    if not text:
        await update.message.reply_text("Format: /dev_request jelaskan perubahan coding yang Anda inginkan")
        return

    user = update.effective_user
    chat = update.effective_chat
    try:
        request = create_dev_request(
            text=text,
            chat_id=chat.id if chat else None,
            user_id=user.id if user else None,
            username=user.username if user else None,
        )
    except Exception as exc:
        await _reply_error(update, exc)
        return

    await update.message.reply_text(format_dev_request(request))


async def show_dev_requests(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    requests = list_dev_requests(limit=5)
    await update.message.reply_text(format_dev_request_list(requests))


async def bullish_score(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = " ".join(context.args).strip()
    if not text:
        await update.message.reply_text("Format: /score paste teks berita/post yang ingin dinilai")
        return

    await update.message.chat.send_action(ChatAction.TYPING)
    await update.message.reply_text("Sedang saya beri bullish score. Tunggu sebentar...")
    try:
        agent = FinancialAnalysisAgent(load_settings())
        result = agent.score_text(text=text, source="telegram_manual")
    except Exception as exc:
        await _reply_error(update, exc)
        return

    await _reply_long(update, result)
    if 'draft' in locals():
        await message.reply_text(format_event_draft(draft))
    if 'draft' in locals():
        await update.message.reply_text(format_event_draft(draft))


async def add_historical_event(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 3:
        await update.message.reply_text(
            "Format: /add_event TICKER YYYY-MM-DD TYPE [notes]. Contoh: /add_event BBCA 2026-05-12 earnings_report laba kuat"
        )
        return

    ticker = context.args[0].upper()
    event_date = context.args[1]
    event_type = context.args[2]
    notes = " ".join(context.args[3:]).strip()

    event = HistoricalEvent(
        ticker=ticker,
        event_date=event_date,
        event_type=event_type,
        source="telegram_manual",
        notes=notes,
    )
    dataset_path = Path("data/historical_events.csv")
    dataset_template(dataset_path)
    append_event(dataset_path, event)
    await update.message.reply_text(f"Event tersimpan: {ticker} {event_date} {event_type}")


async def label_historical_dataset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    dataset_path = Path("data/historical_events.csv")
    await update.message.chat.send_action(ChatAction.TYPING)
    await update.message.reply_text("Sedang isi label harga t+3 dan t+7 ke dataset...")
    try:
        result = enrich_price_labels(dataset_path)
    except Exception as exc:
        await _reply_error(update, exc)
        return

    await update.message.reply_text(format_enrich_summary(result, dataset_path))


async def create_dataset_template(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    dataset_path = Path("data/historical_events.csv")
    dataset_template(dataset_path)
    await update.message.reply_text(f"Template dataset siap: {dataset_path}")


async def index_alpha_usage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.chat.send_action(ChatAction.TYPING)
    await update.message.reply_text("Sedang cek quota Index Alpha...")
    try:
        client = IndexAlphaClient(load_settings())
        result = format_usage(client.usage())
    except Exception as exc:
        await _reply_error(update, exc)
        return

    await update.message.reply_text(result)


async def broker_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        request = parse_broker_summary_args(context.args)
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return

    await update.message.chat.send_action(ChatAction.TYPING)
    await update.message.reply_text("Sedang ambil broker summary dan menyusun analisis...")
    try:
        client = IndexAlphaClient(load_settings())
        payload = client.broker_summary(request)
        summary = format_broker_summary(payload)
        question = (
            f"Analisis broker summary Index Alpha untuk {request.ticker} "
            f"periode {request.date_from} sampai {request.date_to}, investor={request.investor}.\n\n"
            f"{summary}\n\n"
            "Fokus: siapa akumulator/distributor dominan, apakah sinyal broker flow mendukung atau melemahkan tesis investasi, "
            "dan apa risiko interpretasi data broker summary ini."
        )
        agent = FinancialAnalysisAgent(load_settings())
        result = agent.analyze_text(question=question)
    except Exception as exc:
        await _reply_error(update, exc)
        return

    await _reply_long(update, result)


async def analyze_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    question = " ".join(context.args).strip()
    if not question:
        await update.message.reply_text("Tulis pertanyaannya setelah /analyze.")
        return

    await update.message.chat.send_action(ChatAction.TYPING)
    await update.message.reply_text("Sedang saya analisis. Tunggu sebentar...")
    try:
        agent = FinancialAnalysisAgent(load_settings())
        result = agent.analyze_text(question=question)
    except Exception as exc:
        await _reply_error(update, exc)
        return

    await _reply_long(update, result)


async def analyze_idx_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    raw_query = " ".join(context.args).strip()
    if not raw_query:
        await update.message.reply_text("Format: /idx TICKER [PERIODE/FOKUS]. Contoh: /idx ESIP FY2025 cek arus kas")
        return

    try:
        request = parse_idx_command(raw_query)
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return

    await update.message.chat.send_action(ChatAction.TYPING)
    await update.message.reply_text(
        f"Saya mulai cari laporan publik untuk {request.ticker}"
        f"{f' {request.period}' if request.period else ''}. Ini mode best-effort tanpa API resmi IDX."
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            downloaded = find_and_download_idx_report(request, Path(temp_dir))
            focus = request.focus or f"Analisis forensik laporan {request.ticker} {request.period or ''}".strip()
            question = f"{focus}\nSaham: {request.ticker}\nPeriode: {request.period or 'tidak disebutkan'}\nBursa: IDX\nSumber laporan: {downloaded.source_url}"
            agent = FinancialAnalysisAgent(load_settings())
            result = agent.analyze(file_path=downloaded.path, question=question)
        except IDXReportNotFound as exc:
            await update.message.reply_text(str(exc))
            return
        except Exception as exc:
            await _reply_error(update, exc)
            return

    await _reply_long(update, result)


async def analyze_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    document = message.document
    if document is None:
        return

    file_name = document.file_name or "uploaded_file"
    suffix = Path(file_name).suffix.lower()
    if suffix not in SUPPORTED_FILE_EXTENSIONS:
        await message.reply_text(
            f"Format {suffix or '(tanpa ekstensi)'} belum didukung. "
            "Kirim PDF, TXT, MD, CSV, JSON, XML, HTML, atau LOG."
        )
        return

    await message.chat.send_action(ChatAction.UPLOAD_DOCUMENT)
    telegram_file = await document.get_file()

    with tempfile.TemporaryDirectory() as temp_dir:
        local_path = Path(temp_dir) / file_name
        await telegram_file.download_to_drive(custom_path=local_path)

        await message.chat.send_action(ChatAction.TYPING)
        await message.reply_text("File sudah diterima. Sedang saya baca dan analisis...")
        try:
            document_text = extract_document_text(local_path)
            agent = FinancialAnalysisAgent(load_settings())
            result = agent.analyze(
                file_path=local_path,
                question=message.caption,
            )
            draft = create_event_draft_from_document(
                file_name=file_name,
                document_text=document_text,
                question=message.caption,
                source="telegram_document",
            )
            append_event_draft(draft)
        except Exception as exc:
            await _reply_error(update, exc)
            return

    await _reply_long(update, result)


async def _reply_long(update: Update, text: str) -> None:
    message = update.message
    for start_index in range(0, len(text), MAX_TELEGRAM_MESSAGE_LENGTH):
        chunk = text[start_index : start_index + MAX_TELEGRAM_MESSAGE_LENGTH]
        try:
            await message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            await message.reply_text(chunk)


async def _reply_error(update: Update, exc: Exception) -> None:
    logger.error("Telegram bot request failed", exc_info=exc)
    message = update.effective_message
    if message is None:
        return

    if isinstance(exc, RateLimitError):
        body_getter = getattr(getattr(exc, "body", None), "get", lambda _key, _default=None: _default)
        error_code = body_getter("code")
        if error_code == "insufficient_quota" or "insufficient_quota" in str(exc):
            await message.reply_text(
                "NVIDIA API key valid, tapi quota/rate limit/billing NVIDIA API belum tersedia atau sudah habis.\n\n"
                "Yang perlu dicek:\n"
                "1. Buka NVIDIA API Catalog / build.nvidia.com dan cek akses API.\n"
                "2. Pastikan API key NVIDIA masih aktif dan memiliki kuota.\n"
                "3. Pastikan NVIDIA_MODEL tersedia untuk key tersebut.\n\n"
                "Catatan: bot ini sekarang memakai NVIDIA API, bukan ChatGPT Plus/OpenAI billing."
            )
            return

        await message.reply_text(
            "NVIDIA API sedang membatasi request. Coba lagi beberapa saat lagi atau cek limit akun NVIDIA Anda."
        )
        return

    if isinstance(exc, AuthenticationError):
        await message.reply_text("NVIDIA_API_KEY ditolak. Cek ulang API key NVIDIA di file .env.")
        return

    if isinstance(exc, APIConnectionError):
        await message.reply_text("Tidak bisa terhubung ke NVIDIA API. Cek koneksi internet lalu coba lagi.")
        return

    if isinstance(exc, APIStatusError):
        await message.reply_text(
            f"NVIDIA API mengembalikan error {exc.status_code}. Coba lagi atau cek konfigurasi model/API."
        )
        return

    await message.reply_text("Terjadi error saat menganalisis file. Cek terminal untuk detail teknisnya.")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled Telegram error", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message is not None:
        await _reply_error(update, context.error or RuntimeError("Unknown Telegram error"))


def main() -> None:
    acquire_single_instance_lock()
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    settings = load_settings()
    token = require_telegram_token(settings)

    application = ApplicationBuilder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("analyze", analyze_text))
    application.add_handler(CommandHandler("indexalpha", index_alpha_usage))
    application.add_handler(CommandHandler("score", bullish_score))
    application.add_handler(CommandHandler("approve_event", approve_event))
    application.add_handler(CommandHandler("reject_event", reject_event))
    application.add_handler(CommandHandler("pending_events", show_pending_events))
    application.add_handler(CommandHandler("dev_request", save_dev_request))
    application.add_handler(CommandHandler("dev_requests", show_dev_requests))
    application.add_handler(CommandHandler("dataset_template", create_dataset_template))
    application.add_handler(CommandHandler("add_event", add_historical_event))
    application.add_handler(CommandHandler("label_dataset", label_historical_dataset))
    application.add_handler(CommandHandler("broker", broker_summary))
    application.add_handler(CommandHandler("idx", analyze_idx_report))
    application.add_handler(MessageHandler(filters.Document.ALL, analyze_document))
    application.add_error_handler(error_handler)
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
