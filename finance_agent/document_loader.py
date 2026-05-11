from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".xml", ".html", ".log"}
SUPPORTED_FILE_EXTENSIONS = TEXT_EXTENSIONS | {".pdf"}
MAX_DOCUMENT_CHARS = 180_000


def extract_document_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {path}")

    extension = path.suffix.lower()
    if extension not in SUPPORTED_FILE_EXTENSIONS:
        raise ValueError(
            f"Format {extension or '(tanpa ekstensi)'} belum didukung. "
            "Gunakan PDF, TXT, MD, CSV, JSON, XML, HTML, atau LOG."
        )

    if extension == ".pdf":
        text = _extract_pdf_text(path)
    else:
        text = path.read_text(encoding="utf-8")

    if not text.strip():
        raise ValueError(
            "Teks dari file kosong atau tidak bisa diekstrak. Jika PDF berupa scan gambar, "
            "perlu OCR terlebih dahulu."
        )

    if len(text) > MAX_DOCUMENT_CHARS:
        return (
            text[:MAX_DOCUMENT_CHARS]
            + "\n\n[Dokumen dipotong karena terlalu panjang. Kirim bagian spesifik jika butuh analisis penuh.]"
        )

    return text


def _extract_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    pages: list[str] = []
    for index, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""
        pages.append(f"\n\n--- Halaman {index} ---\n{page_text}")
    return "".join(pages)
