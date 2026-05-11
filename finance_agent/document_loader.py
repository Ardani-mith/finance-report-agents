from __future__ import annotations

import base64
import mimetypes
from pathlib import Path


TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".xml", ".html", ".log"}
SUPPORTED_FILE_EXTENSIONS = TEXT_EXTENSIONS | {".pdf"}


def build_file_content(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {path}")

    extension = path.suffix.lower()
    if extension not in SUPPORTED_FILE_EXTENSIONS:
        raise ValueError(
            f"Format {extension or '(tanpa ekstensi)'} belum didukung. "
            "Gunakan PDF, TXT, MD, CSV, JSON, XML, HTML, atau LOG."
        )

    if extension == ".pdf":
        mime_type = mimetypes.guess_type(path.name)[0] or "application/pdf"
        encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
        return [
            {
                "type": "input_file",
                "filename": path.name,
                "file_data": f"data:{mime_type};base64,{encoded}",
            }
        ]

    return [{"type": "input_text", "text": path.read_text(encoding="utf-8")}]

