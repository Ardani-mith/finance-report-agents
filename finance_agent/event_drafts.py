from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from finance_agent.agent import detect_document_type
from finance_agent.historical_dataset import HistoricalEvent, append_event, dataset_template

EVENT_DRAFTS_PATH = Path("data/pending_event_drafts.jsonl")
ACTIVE_STATUSES = {"pending_approval", "live_monitoring", "needs_context"}


@dataclass(frozen=True)
class EventDraft:
    id: str
    created_at_utc: str
    status: str
    ticker: str
    event_date: str
    event_type: str
    source: str
    intent_mode: str = "unspecified"
    price_in_status: str = "unknown"
    outcome_context: str = ""
    notes: str = ""
    period: str = ""
    model_verdict: str = ""
    features_json: str = "{}"


def create_event_draft_from_document(
    file_name: str,
    document_text: str,
    question: str | None,
    source: str,
) -> EventDraft:
    doc_type = detect_document_type(Path(file_name), document_text, question)
    text = "\n".join([file_name, question or "", document_text[:12000]])
    ticker = _extract_ticker(text)
    event_date = _extract_event_date(text)
    event_type = _map_event_type(doc_type, text)
    event_context = infer_event_context(question or "")
    notes = (question or file_name).strip()
    draft_id = datetime.now(timezone.utc).strftime("EV-%Y%m%d-%H%M%S-%f")
    return EventDraft(
        id=draft_id,
        created_at_utc=datetime.now(timezone.utc).isoformat(),
        status=_status_for_intent(event_context["intent_mode"]),
        ticker=ticker,
        event_date=event_date,
        event_type=event_type,
        source=source,
        intent_mode=event_context["intent_mode"],
        price_in_status=event_context["price_in_status"],
        outcome_context=event_context["outcome_context"],
        notes=notes,
    )


def infer_event_context(text: str) -> dict[str, str]:
    normalized = " ".join(text.lower().split())
    if not normalized:
        return {
            "intent_mode": "unspecified",
            "price_in_status": "unknown",
            "outcome_context": "Konteks dataset/live belum diberikan.",
        }

    learn_score = 0
    live_score = 0

    learn_phrases = [
        "buat belajar",
        "untuk belajar",
        "dataset",
        "training",
        "latih",
        "historis",
        "historical",
        "setelah lapkeu",
        "setelah laporan",
        "setelah terbit",
        "naik",
        "melonjak",
        "lonjakan",
        "rally",
        "t+3",
        "t+7",
        "3 hari",
        "7 hari",
    ]
    live_phrases = [
        "fresh",
        "baru terbit",
        "baru rilis",
        "belum price in",
        "not priced in",
        "belum diprice in",
        "live",
        "monitor",
        "monitoring",
        "pantau",
        "cek sekarang",
    ]

    for phrase in learn_phrases:
        if phrase in normalized:
            learn_score += 1
    for phrase in live_phrases:
        if phrase in normalized:
            live_score += 1

    if "setelah" in normalized and ("naik" in normalized or "melonjak" in normalized):
        learn_score += 2
    if "belum" in normalized and "price in" in normalized:
        live_score += 2

    if learn_score > live_score and learn_score > 0:
        return {
            "intent_mode": "learn_dataset",
            "price_in_status": "post_event_move_confirmed",
            "outcome_context": text.strip(),
        }
    if live_score > 0:
        return {
            "intent_mode": "live_fresh",
            "price_in_status": "not_priced_in",
            "outcome_context": text.strip(),
        }
    return {
        "intent_mode": "unspecified",
        "price_in_status": "unknown",
        "outcome_context": text.strip() or "Konteks dataset/live belum diberikan.",
    }


def append_event_draft(draft: EventDraft, path: Path = EVENT_DRAFTS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(draft), ensure_ascii=False) + "\n")


def list_event_drafts(
    path: Path = EVENT_DRAFTS_PATH,
    status: str | None = None,
) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            row_status = row.get("status")
            if status is None:
                if row_status in ACTIVE_STATUSES:
                    rows.append(row)
            elif row_status == status:
                rows.append(row)
    return rows


def approve_event_draft(
    draft_id: str,
    drafts_path: Path = EVENT_DRAFTS_PATH,
    dataset_path: Path = Path("data/historical_events.csv"),
) -> dict[str, Any]:
    rows = _load_all(drafts_path)
    target = None
    for row in rows:
        if row.get("id") == draft_id:
            target = row
            break
    if target is None:
        raise ValueError(f"Draft event tidak ditemukan: {draft_id}")
    if target.get("status") == "approved":
        raise ValueError(f"Draft event {draft_id} sudah disetujui sebelumnya.")
    if target.get("status") == "rejected":
        raise ValueError(f"Draft event {draft_id} sudah ditolak sebelumnya.")

    target["status"] = "approved"
    _save_all(rows, drafts_path)

    dataset_template(dataset_path)
    append_event(
        dataset_path,
        HistoricalEvent(
            ticker=str(target.get("ticker") or "").upper(),
            event_date=str(target.get("event_date") or ""),
            event_type=str(target.get("event_type") or "general_event"),
            source=str(target.get("source") or "telegram_auto"),
            intent_mode=str(target.get("intent_mode") or ""),
            price_in_status=str(target.get("price_in_status") or ""),
            outcome_context=str(target.get("outcome_context") or ""),
            period=str(target.get("period") or ""),
            model_verdict=str(target.get("model_verdict") or ""),
            features_json=str(target.get("features_json") or "{}"),
            notes=str(target.get("notes") or ""),
        ),
    )
    return target


def reject_event_draft(draft_id: str, drafts_path: Path = EVENT_DRAFTS_PATH) -> dict[str, Any]:
    rows = _load_all(drafts_path)
    target = None
    for row in rows:
        if row.get("id") == draft_id:
            target = row
            break
    if target is None:
        raise ValueError(f"Draft event tidak ditemukan: {draft_id}")
    target["status"] = "rejected"
    _save_all(rows, drafts_path)
    return target


def mark_event_outcome(
    draft_id: str,
    outcome_context: str,
    drafts_path: Path = EVENT_DRAFTS_PATH,
) -> dict[str, Any]:
    outcome_context = outcome_context.strip()
    if not outcome_context:
        raise ValueError("Outcome context tidak boleh kosong.")

    rows = _load_all(drafts_path)
    target = None
    for row in rows:
        if row.get("id") == draft_id:
            target = row
            break
    if target is None:
        raise ValueError(f"Draft event tidak ditemukan: {draft_id}")
    if target.get("status") == "approved":
        raise ValueError(f"Draft event {draft_id} sudah masuk dataset.")
    if target.get("status") == "rejected":
        raise ValueError(f"Draft event {draft_id} sudah ditolak sebelumnya.")

    target["intent_mode"] = "learn_dataset"
    target["price_in_status"] = "post_event_move_confirmed"
    target["status"] = "pending_approval"
    target["outcome_context"] = outcome_context
    _save_all(rows, drafts_path)
    return target


def format_event_draft(draft: EventDraft | dict[str, Any]) -> str:
    row = asdict(draft) if isinstance(draft, EventDraft) else draft
    mode = str(row.get("intent_mode") or "unspecified")
    status = str(row.get("status") or "needs_context")
    context = str(row.get("outcome_context") or "-")

    lines = [
        "Draft event terdeteksi.",
        f"ID: {row['id']}",
        f"Ticker: {row['ticker']}",
        f"Tanggal: {row['event_date']}",
        f"Jenis: {row['event_type']}",
        f"Mode: {mode}",
        f"Price-in status: {row.get('price_in_status', 'unknown')}",
        f"Status draft: {status}",
        f"Konteks: {context}",
        "",
    ]

    if mode == "learn_dataset":
        lines.append("Dokumen ini terdeteksi sebagai bahan belajar dataset karena konteksnya sudah menyebut outcome harga setelah terbit.")
        lines.append(f"Approve: /approve_event {row['id']}")
        lines.append(f"Reject: /reject_event {row['id']}")
    elif mode == "live_fresh":
        lines.append("Dokumen ini terdeteksi sebagai laporan fresh/live. Belum saya masukkan ke dataset agar tidak mencampur sampel yang outcome-nya belum terbukti.")
        lines.append(f"Jika tetap ingin simpan ke dataset: /approve_event {row['id']}")
        lines.append(f"Abaikan draft ini: /reject_event {row['id']}")
    else:
        lines.append("Konteks belum cukup jelas untuk membedakan dataset vs live. Di Telegram, tambahkan caption seperti: 'untuk belajar dataset, setelah terbit naik 12% dalam 3 hari' atau 'fresh, belum price in'.")
        lines.append(f"Jika ingin simpan ke dataset: /approve_event {row['id']}")
        lines.append(f"Jika tidak: /reject_event {row['id']}")

    return "\n".join(lines)


def format_event_draft_list(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "Tidak ada draft event aktif."
    lines = ["Draft event aktif:"]
    for row in rows[-8:]:
        lines.append(
            f"- {row.get('id')}: {row.get('ticker')} {row.get('event_date')} {row.get('event_type')} | {row.get('intent_mode')} | {row.get('status')}"
        )
    return "\n".join(lines)


def _extract_ticker(text: str) -> str:
    upper_text = text.upper()
    blacklist = {
        "AKSI", "IDX", "PDF", "FYTD", "QTR", "PAGE", "HTML", "JSON", "TEXT", "NEWS", "NOTE",
        "INFO", "FILE", "DOKU", "DATA", "TBK", "WITH", "THIS", "THAT",
    }

    file_candidates = re.findall(r"(?<![A-Z0-9])[A-Z]{4}(?![A-Z0-9])", upper_text.splitlines()[0].replace('_', ' '))
    for match in file_candidates:
        if match not in blacklist:
            return match

    jk_matches = re.findall(r"\b([A-Z]{4})\.JK\b", upper_text)
    for match in jk_matches:
        if match not in blacklist:
            return match

    generic_matches = re.findall(r"\b[A-Z]{4}\b", upper_text)
    for match in generic_matches:
        if match not in blacklist:
            return match
    return "UNKNOWN"


def _extract_event_date(text: str) -> str:
    iso_match = re.search(r"\b20\d{2}-\d{2}-\d{2}\b", text)
    if iso_match:
        return iso_match.group(0)

    slash_match = re.search(r"\b(\d{2})/(\d{2})/(20\d{2})\b", text)
    if slash_match:
        day, month, year = slash_match.groups()
        return f"{year}-{month}-{day}"

    return datetime.now(timezone.utc).date().isoformat()


def _map_event_type(doc_type: str, text: str) -> str:
    if doc_type == "financial_report":
        return "earnings_report"
    if doc_type == "corporate_action":
        lowered = text.lower()
        if "rights issue" in lowered or "hmetd" in lowered:
            return "rights_issue"
        if "buyback" in lowered:
            return "buyback"
        if "akuisisi" in lowered or "acquisition" in lowered:
            return "acquisition"
        return "corporate_action"
    if doc_type == "presentation":
        return "investor_presentation"
    if doc_type == "news":
        return "news_event"
    return "general_event"


def _status_for_intent(intent_mode: str) -> str:
    if intent_mode == "learn_dataset":
        return "pending_approval"
    if intent_mode == "live_fresh":
        return "live_monitoring"
    return "needs_context"


def _load_all(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _save_all(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
