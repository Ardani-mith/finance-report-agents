from __future__ import annotations

import re
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
        strategy_clues = extract_document_strategy_clues(document_text)
        prompt = build_user_prompt(
            question=question,
            market_snapshot=formatted_market,
            document_type=document_type,
            file_name=file_path.name,
            document_clues=strategy_clues,
        )

        user_content = f"""
{prompt}

Isi dokumen yang diekstrak dari file {file_path.name}:
{document_text}
""".strip()

        return self._chat_with_validation(
            user_content=user_content,
            document_type=document_type,
            document_text=document_text,
            strategy_clues=strategy_clues,
        )

    def analyze_text(
        self,
        question: str,
        tickers: list[str] | None = None,
        use_web_search: bool = False,
    ) -> str:
        market_snapshot = fetch_market_snapshot(tickers or DEFAULT_TICKERS)
        formatted_market = format_market_snapshot(market_snapshot)
        question = (
            "Analisis hanya berdasarkan teks user berikut. "
            "Jika teks tidak berisi substansi dokumen/berita yang cukup, jangan kabur ke market snapshot; "
            "sebutkan bahwa konteks teks terlalu tipis dan perlu file atau isi dokumen.\n\n"
            f"{question}"
        )
        prompt = build_user_prompt(question=question, market_snapshot=formatted_market)
        return self._chat_with_validation(
            user_content=prompt,
            document_type="general",
            document_text=question,
            strategy_clues=extract_document_strategy_clues(question),
        )

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

    def _chat_with_validation(
        self,
        user_content: str,
        document_type: str,
        document_text: str,
        strategy_clues: str,
    ) -> str:
        first_pass = self._chat(user_content)
        if not needs_analysis_retry(first_pass, document_type, document_text):
            return first_pass

        retry_instruction = build_retry_instruction(strategy_clues=strategy_clues, deep=False)
        second_pass = self._chat(f"{user_content}\n\n{retry_instruction}")
        if not needs_analysis_retry(second_pass, document_type, document_text):
            return second_pass

        deep_pass_instruction = build_retry_instruction(strategy_clues=strategy_clues, deep=True)
        third_pass = self._chat(f"{user_content}\n\n{deep_pass_instruction}")
        if not needs_analysis_retry(third_pass, document_type, document_text):
            return third_pass
        return build_forensic_fallback_response(document_type, document_text, strategy_clues)


def build_retry_instruction(strategy_clues: str, deep: bool = False) -> str:
    if not deep:
        return f"""
Jawaban sebelumnya terlalu generik, terlalu bergantung pada market snapshot, atau terlalu cepat mengatakan informasi tidak cukup.
Ulangi analisis dengan aturan keras berikut:
- Abaikan jawaban generik seperti pendapatan naik/laba naik kecuali langsung dijelaskan driver dan implikasinya.
- Jangan jadikan market snapshot sebagai fokus utama. Snapshot hanya konteks, bukan objek analisis utama.
- Jika dokumen memang punya sedikit petunjuk, gunakan petunjuk strategis otomatis berikut untuk membangun hipotesis awal:
{strategy_clues}
- Jika dokumen minim data, tetap jawab apa yang paling mungkin penting dari struktur pembiayaan, partner, aset backbone, capex, related party, atau arah konsolidasi.
- Jangan menulis kalimat seperti "dokumen tidak cukup" kecuali benar-benar mustahil; gantikan dengan "Hipotesis yang paling masuk akal dari petunjuk yang ada adalah ...".
- Untuk laporan keuangan, jawab wajib: apa yang berubah, kenapa itu penting, dan puzzle strategis apa yang mungkin sedang terbentuk.

Berikan versi yang lebih tajam sekarang.
""".strip()

    return f"""
Mode: FORENSIC DEEP PASS.
Jawaban sebelumnya masih gagal karena terlalu umum, terlalu aman, atau tidak benar-benar membaca dokumen.
Sekarang ikuti aturan ini tanpa kompromi:
- Fokus utama adalah dokumen, footnotes, struktur pembiayaan, partner, aset inti, dan implikasi kontrol aset. Market snapshot hanya latar belakang.
- Pilih hanya 2-3 hal paling tajam. Tidak perlu sopan, perlu presisi.
- Larangan keras: jangan menulis VIX, crude oil, EUR/USD, "market global", atau "informasi tidak cukup" kecuali dokumen memang benar-benar tentang itu.
- Jika menemukan petunjuk tentang penjaminan, obligasi, sindikasi, pelanggan kunci, merger, akuisisi, backbone, kabel laut, capex, JV, atau related party, anggap itu kandidat puzzle besar.
- Gunakan petunjuk otomatis berikut sebagai titik awal, lalu bangun hipotesis yang paling mungkin:
{strategy_clues}
- Jika tetap belum ada bukti kuat, tulis satu **Hipotesis** terbaik yang paling bernilai bagi investor, bukan daftar ketiadaan informasi.
- Jawaban harus terasa spesifik untuk dokumen ini. Jika jawabannya masih bisa dipakai ke emiten lain tanpa ubah kata, berarti gagal.

Berikan hanya versi final yang tajam.
""".strip()


def detect_document_type(file_path: Path, document_text: str, question: str | None = None) -> str:
    haystack = "\n".join([file_path.name, question or "", document_text[:6000]]).lower()

    if any(keyword in haystack for keyword in [
        "laporan keuangan",
        "financial statements",
        "statement of profit or loss",
        "statement of financial position",
        "statement of cash flows",
        "arus kas",
        "catatan atas laporan keuangan",
        "laporan posisi keuangan",
        "laporan laba rugi",
        "laporan perubahan ekuitas",
        "penghasilan komprehensif",
        "aset lancar",
        "liabilitas jangka pendek",
        "ekuitas yang dapat diatribusikan",
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


def extract_document_strategy_clues(document_text: str, max_clues: int = 8) -> str:
    if not document_text.strip():
        return "- Tidak ada petunjuk strategis otomatis yang berhasil diekstrak."

    keyword_groups = {
        "Pendanaan/penjaminan": [
            "obligasi", "bond", "notes", "guarantee", "guarantor", "penjamin", "facility",
            "loan", "pinjaman", "syndication", "sindikasi", "covenant", "refinancing",
        ],
        "Mitra/transaksi strategis": [
            "partner", "kerja sama", "strategic", "joint venture", "customer", "pelanggan utama",
            "vendor", "supplier", "kontrak", "epc", "related party",
        ],
        "M&A/konsolidasi": [
            "akuisisi", "acquisition", "merger", "divestasi", "spin-off", "tender offer",
            "private placement", "rights issue", "convertible",
        ],
        "Aset backbone/infrastruktur": [
            "fiber optic", "fibre optic", "submarine cable", "kabel laut", "backbone", "data center",
            "landing station", "network", "infrastructure", "tower", "spectrum",
        ],
        "Capex/ekspansi": [
            "capex", "capital expenditure", "expansion", "ekspansi", "order book", "orderbook",
            "project", "proyek", "construction", "build", "rollout",
        ],
    }

    normalized = " ".join(document_text.split())
    sentences = re.split(r"(?<=[.!?])\s+|\n+", normalized)
    clues: list[str] = []
    seen: set[str] = set()

    for group_name, keywords in keyword_groups.items():
        for sentence in sentences:
            hay = sentence.lower()
            if not any(keyword in hay for keyword in keywords):
                continue
            snippet = sentence.strip()
            if len(snippet) > 220:
                snippet = snippet[:217].rstrip() + "..."
            clue = f"- {group_name}: {snippet}"
            key = f"{group_name}|{snippet.lower()}"
            if key in seen:
                continue
            seen.add(key)
            clues.append(clue)
            break
        if len(clues) >= max_clues:
            break

    entity_names = _extract_named_entities(normalized)
    if entity_names:
        clues.append(f"- Nama entitas yang sering muncul: {', '.join(entity_names[:8])}")

    if not clues:
        return "- Tidak ada petunjuk strategis otomatis yang berhasil diekstrak."
    return "\n".join(clues[:max_clues])


def _extract_named_entities(text: str) -> list[str]:
    candidates = re.findall(r"\b(?:[A-Z][a-zA-Z&.-]+(?:\s+[A-Z][a-zA-Z&.-]+){0,3})\b", text)
    blacklist = {
        "Statement", "Notes", "Financial Statements", "Balance Sheet", "Cash Flow",
        "Laporan Keuangan", "Catatan Atas", "The Company", "The Group",
    }
    counts: dict[str, int] = {}
    for candidate in candidates:
        cleaned = candidate.strip()
        if len(cleaned) < 4 or cleaned in blacklist:
            continue
        counts[cleaned] = counts.get(cleaned, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [name for name, _ in ranked[:10]]


def needs_analysis_retry(response_text: str, document_type: str, document_text: str) -> bool:
    if not response_text.strip():
        return True

    lowered = response_text.lower()
    document_length = len(document_text.strip())

    generic_markers = [
        "kondisi market global",
        "dokumen ini memberikan gambaran",
        "tidak ada informasi yang cukup",
        "dokumen tidak menyediakan informasi yang cukup",
        "tidak ada informasi tentang",
        "pendapatan grup meningkat",
        "laba grup meningkat",
        "utang grup berkurang",
        "perusahaan berhasil meningkatkan pendapatan",
        "membantu investor dalam membuat keputusan investasi yang tepat",
        "kondisi pasar yang relatif stabil",
        "aset backbone yang strategis",
        "ekspansi bisnis",
        "konsolidasi industri",
        "pengembangan teknologi",
        "dokumen hanya memberikan snapshot kondisi pasar",
    ]
    generic_hits = sum(1 for marker in generic_markers if marker in lowered)

    missing_puzzle_section = ("🧩" not in response_text and "PUZZLE" not in response_text.upper() and "STRATEGIS" not in response_text.upper())
    overfocus_market = (lowered.count("market") + lowered.count("vix") + lowered.count("crude oil") + lowered.count("eur/usd")) >= 3 and document_length > 500
    says_not_enough = ("tidak cukup" in lowered or "tidak menyediakan informasi" in lowered) and document_length > 1200
    too_short_for_financial = document_type == "financial_report" and len(response_text) < 260

    lacks_anchor = document_length > 1000 and not has_evidence_anchor(response_text)
    missing_explicit_evidence_tag = document_type == "financial_report" and "bukti dokumen:" not in lowered
    overaggressive_verdict = document_type == "financial_report" and "strong buy" in lowered and not has_minimum_conviction_anchors(response_text)
    return (
        generic_hits >= 2
        or missing_puzzle_section
        or overfocus_market
        or says_not_enough
        or too_short_for_financial
        or lacks_anchor
        or missing_explicit_evidence_tag
        or overaggressive_verdict
    )


def build_forensic_fallback_response(document_type: str, document_text: str, strategy_clues: str) -> str:
    clues = [line.strip('- ').strip() for line in strategy_clues.splitlines() if line.strip().startswith('- ')]
    clues = clues[:3]

    if document_type == 'financial_report':
        if clues:
            bullets = '\n'.join(f"- **{_labelize_clue(clue)}** — {clue}" for clue in clues)
            return (
                "**📍 TEMUAN KRITIS**\n"
                f"{bullets}\n"
                "- **Koreksi/Revisi:** Tidak tersedia dari ekstraksi dokumen.\n\n"
                "**🧩 PUZZLE BESAR**\n"
                f"- **Hipotesis** — {build_puzzle_hypothesis(clues)}\n"
                "- **So what** — Jika petunjuk ini valid, nilai strategis aset/relasi bisnis bisa lebih penting daripada laba tahun berjalan.\n\n"
                "**📊 NARASI**\n"
                "Petunjuk dokumen menunjukkan ada isu yang lebih penting dari sekadar pertumbuhan angka headline: struktur pembiayaan, relasi partner, atau kontrol atas aset inti. Ini cenderung **struktural** bila benar terkait reposisi aset atau integrasi vertikal, bukan sekadar perbaikan musiman.\n\n"
                "**🎯 VERDICT**\n"
                "**Watch** — laporan memberi jejak puzzle, tetapi validasi berikutnya harus datang dari pengungkapan partner, pembiayaan, capex, atau transaksi korporasi lanjutan."
            )

        return (
            "**📍 TEMUAN KRITIS**\n"
            "- **Ekstraksi dokumen minim sinyal** — model tidak menemukan petunjuk strategis yang cukup tajam dari teks hasil ekstraksi.\n"
            "- **Koreksi/Revisi:** Tidak tersedia dari ekstraksi dokumen.\n\n"
            "**🧩 PUZZLE BESAR**\n"
            "- **Hipotesis** — dokumen kemungkinan perlu OCR yang lebih baik atau bagian footnotes/MD&A yang lebih lengkap untuk membaca puzzle strategisnya.\n\n"
            "**📊 NARASI**\n"
            "Teks yang diekstrak belum cukup kaya untuk memisahkan apakah ini hanya perbaikan operasional biasa atau bagian dari reposisi aset yang lebih besar.\n\n"
            "**🎯 VERDICT**\n"
            "**Watch** — perlu teks/halaman yang lebih bersih agar analisis forensik bisa benar-benar tajam."
        )

    if clues:
        bullets = '\n'.join(f"- **{_labelize_clue(clue)}** — {clue}" for clue in clues)
        return (
            "**📍 POIN KUNCI**\n"
            f"{bullets}\n\n"
            "**🧩 MAKNA STRATEGIS**\n"
            f"- **Hipotesis** — {build_puzzle_hypothesis(clues)}\n\n"
            "**🎯 VERDICT**\n"
            "**Perlu Verifikasi** — ada petunjuk strategis, tetapi dokumen belum cukup lengkap untuk mengunci tesis dengan yakin."
        )

    return (
        "**📍 POIN KUNCI**\n"
        "- **Dokumen minim petunjuk** — tidak ada sinyal cukup tajam yang berhasil diekstrak dari teks ini.\n\n"
        "**🧩 MAKNA STRATEGIS**\n"
        "- **Hipotesis** — perlu dokumen yang lebih lengkap atau kualitas ekstraksi lebih baik untuk membangun puzzle.\n\n"
        "**🎯 VERDICT**\n"
        "**Perlu Verifikasi** — belum layak dijadikan dasar tesis investasi."
    )


def build_puzzle_hypothesis(clues: list[str]) -> str:
    joined = ' | '.join(clues).lower()
    if any(term in joined for term in ['kabel laut', 'submarine cable', 'backbone', 'fiber optic', 'network']):
        return 'aset backbone/infrastruktur tampaknya menjadi pusat optionality; pasar bisa sedang meng-underprice nilai kontrol atas jaringan dibanding laba headline.'
    if any(term in joined for term in ['guarantee', 'guarantor', 'penjamin', 'obligasi', 'bond', 'facility', 'loan']):
        return 'struktur pembiayaan atau penjaminan mungkin memberi petunjuk siapa pihak strategis yang benar-benar menopang ekspansi atau menyiapkan reposisi aset.'
    if any(term in joined for term in ['akuisisi', 'acquisition', 'merger', 'rights issue', 'private placement']):
        return 'dokumen ini mungkin bagian awal dari puzzle konsolidasi, bukan sekadar update operasional biasa.'
    if any(term in joined for term in ['partner', 'kerja sama', 'joint venture', 'related party', 'pelanggan utama']):
        return 'nilai perusahaan mungkin lebih ditentukan oleh kualitas relasi strategis dan kontrol rantai nilai daripada angka laba tahun berjalan.'
    return 'dokumen memberi sinyal bahwa ada optionality strategis di balik angka headline, tetapi pemicunya masih perlu dikonfirmasi lebih lanjut.'


def _labelize_clue(clue: str) -> str:
    head = clue.split(':', 1)[0].strip()
    return head or 'Clue'


def has_evidence_anchor(response_text: str) -> bool:
    lowered = response_text.lower()
    anchors = [
        "bukti dokumen", "catatan", "halaman", "related party", "pihak berelasi",
        "perjanjian", "kontrak", "pinjaman", "obligasi", "liabilitas", "piutang",
        "mora", "iforte", "indosat", "bahtera",
    ]
    return any(anchor in lowered for anchor in anchors)


def has_minimum_conviction_anchors(response_text: str) -> bool:
    lowered = response_text.lower()
    anchors = [
        "catatan", "halaman", "pihak berelasi", "related party", "perjanjian",
        "kontrak", "obligasi", "pinjaman", "mora", "iforte", "indosat",
    ]
    hit_count = sum(1 for anchor in anchors if anchor in lowered)
    has_confirmation_line = "konfirmasi q berikutnya" in lowered
    return hit_count >= 2 and has_confirmation_line
