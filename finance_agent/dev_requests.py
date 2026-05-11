from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEV_REQUESTS_PATH = Path("dev_requests/inbox.jsonl")


@dataclass(frozen=True)
class DevRequest:
    id: str
    created_at_utc: str
    chat_id: int | None
    user_id: int | None
    username: str | None
    text: str
    status: str = "pending_review"
    auto_allow_agent_changes: bool = True
    review_required_before_github_push: bool = True
    github_push_allowed: bool = False


def create_dev_request(
    text: str,
    chat_id: int | None = None,
    user_id: int | None = None,
    username: str | None = None,
    path: Path = DEV_REQUESTS_PATH,
) -> DevRequest:
    if not text.strip():
        raise ValueError("Isi dev request tidak boleh kosong.")

    created_at = datetime.now(timezone.utc).isoformat()
    request_id = datetime.now(timezone.utc).strftime("DR-%Y%m%d-%H%M%S-%f")
    request = DevRequest(
        id=request_id,
        created_at_utc=created_at,
        chat_id=chat_id,
        user_id=user_id,
        username=username,
        text=text.strip(),
    )
    append_dev_request(request, path=path)
    return request


def append_dev_request(request: DevRequest, path: Path = DEV_REQUESTS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(request), ensure_ascii=False) + "\n")


def list_dev_requests(limit: int = 5, path: Path = DEV_REQUESTS_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows[-limit:]


def format_dev_request(request: DevRequest) -> str:
    return (
        "Dev request tersimpan.\n"
        f"ID: {request.id}\n"
        f"Status: {request.status}\n"
        "Auto-allow agent changes: yes\n"
        "GitHub push: no, wajib review dulu"
    )


def format_dev_request_list(requests: list[dict[str, Any]]) -> str:
    if not requests:
        return "Belum ada dev request pending."

    lines = ["Dev requests terakhir:"]
    for item in requests:
        text = str(item.get("text", "")).replace("\n", " ")
        if len(text) > 120:
            text = text[:117] + "..."
        lines.append(f"- {item.get('id')} [{item.get('status')}]: {text}")
    return "\n".join(lines)
