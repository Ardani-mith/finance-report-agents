ANALYSIS_AGENT_NAME = "analisis-laporan-keuangan"

SYSTEM_PROMPT = """
Anda adalah agent bernama analisis-laporan-keuangan.

Description:
Tugasmu adalah membaca dokumen bisnis, pasar modal, berita, laporan keuangan,
keterbukaan informasi, presentasi investor, atau memo operasional secara forensik.
Jangan hanya merangkum isi dokumen. Gali sinyal yang benar-benar material bagi
keputusan investasi atau monitoring.

Peran:
- Anda adalah analis pasar modal senior dengan gaya forensik.
- Jawab dalam Bahasa Indonesia yang tajam, ringkas, padat, dan berbasis bukti.
- Output default untuk Telegram harus pendek: 120-180 kata, kecuali user meminta detail.
- Gunakan heading Markdown tebal dengan **...**. Jangan gunakan paragraf panjang.
- Pisahkan fakta dari inferensi.
- Jangan mengarang lokasi halaman/catatan. Jika lokasi spesifik tidak terbaca,
  tulis bahwa lokasi tidak tersedia dari dokumen yang diberikan.
- Jangan memberi instruksi trading mutlak. Verdict adalah kerangka analisis,
  bukan nasihat keuangan personal.
- Selalu sebutkan jika data market kemungkinan delayed atau tidak lengkap.
- Jika dokumen bukan laporan keuangan, jangan paksakan format laporan keuangan.
  Pilih kerangka analisis yang paling cocok untuk tipe dokumennya.

Checklist tambahan untuk laporan keuangan:
- Footnotes dan catatan atas laporan keuangan.
- MD&A: tone manajemen, kalimat defensif, risiko yang disamarkan.
- Arus kas vs laba bersih. Divergensi adalah sinyal penting.
- Related party transactions.
- Off-balance sheet items.
- Perubahan kebijakan akuntansi atau estimasi.
- Auditor's report: going concern, opini, penekanan hal, pergantian auditor.
- Segment reporting yang tidak disorot manajemen.
- Status laporan: apakah versi KOREKSI/revisi. Jika ya, tandai sebagai red flag
  transparansi dan investigasi apa yang berubah dari versi sebelumnya.
""".strip()


def build_user_prompt(
    question: str | None,
    market_snapshot: str,
    document_type: str = "general",
    file_name: str | None = None,
) -> str:
    focus = question or """
Saya mengirimkan sebuah dokumen terkait saham/perusahaan/pasar.
Entitas: [tidak disebutkan]
Periode: [tidak disebutkan]
Bursa: [tidak disebutkan]
Fokus khusus: analisis semua
""".strip()

    file_hint = file_name or "dokumen"
    template = _template_for(document_type)

    return f"""
Konteks pengguna:
{focus}

Tipe dokumen terdeteksi:
{document_type}

Nama file:
{file_hint}

Kondisi market global realtime/delayed:
{market_snapshot}

{template}
""".strip()


def _template_for(document_type: str) -> str:
    templates = {
        "financial_report": _financial_report_template(),
        "news": _news_template(),
        "corporate_action": _corporate_action_template(),
        "presentation": _presentation_template(),
        "general": _general_document_template(),
    }
    return templates.get(document_type, templates["general"])


def _style_block() -> str:
    return """
Aturan gaya:
- Jangan menulis pembuka seperti "Berikut adalah analisis".
- Jangan lebih dari 180 kata.
- Gunakan Markdown bold **...** untuk istilah penting.
- Hindari bullet generik. Setiap bullet harus punya implikasi investasi.
""".strip()


def _financial_report_template() -> str:
    return f"""
Tugas analisis:
Baca laporan keuangan secara forensik. Fokus pada insight material, bukan rangkuman panjang.
Cari footnotes, MD&A, arus kas, related party, off-balance sheet, perubahan akuntansi,
auditor, segment reporting, status koreksi/revisi, serta sinyal momentum micro-cap jika relevan.

Format output Telegram wajib singkat, jelas, dan padat:

**📍 TEMUAN KRITIS**
- Maksimal 3 bullet.
- Format: **[isu]** — dampak investasi singkat. Cantumkan lokasi jika tersedia.
- Wajib tulis: **Koreksi/Revisi:** Ya/Tidak terindikasi/Tidak tersedia.

**📊 NARASI**
- Maksimal 3 kalimat.
- Sebutkan apakah perbaikan **struktural** atau **siklikal**.
- Jangan ulangi angka yang tidak penting.

**🎯 VERDICT**
- Satu baris saja: **Strong Buy / Accumulate / Watch / Avoid** — alasan inti.
- Jika Watch, tambah: **Konfirmasi Q berikutnya:** [1-2 hal].

{_style_block()}
""".strip()


def _news_template() -> str:
    return f"""
Tugas analisis:
Baca berita, post, atau update singkat ini sebagai katalis pasar. Fokus pada apa yang baru,
apa yang benar-benar material, dan apakah ini berpotensi menggerakkan harga dalam jangka pendek.

Format output Telegram wajib singkat, jelas, dan padat:

**📍 POIN UTAMA**
- Maksimal 3 bullet.
- Format: **[katalis]** — dampak singkat ke sentimen/fundamental.

**📊 MAKNA**
- Maksimal 3 kalimat.
- Jelaskan apakah efeknya **sementara**, **struktural**, atau **belum jelas**.

**🎯 VERDICT**
- Satu baris saja: **Bullish / Netral / Bearish** — alasan inti.

{_style_block()}
""".strip()


def _corporate_action_template() -> str:
    return f"""
Tugas analisis:
Baca keterbukaan informasi, aksi korporasi, atau pengumuman resmi ini. Fokus pada struktur transaksi,
dilusi, dampak ke valuasi, governance, dan siapa yang paling diuntungkan/dirugikan.

Format output Telegram wajib singkat, jelas, dan padat:

**📍 POIN KUNCI**
- Maksimal 3 bullet.
- Format: **[aksi]** — dampak investasi singkat.

**📊 MAKNA**
- Maksimal 3 kalimat.
- Sebutkan apakah ini **value accretive**, **dilutif**, atau **masih abu-abu**.

**🎯 VERDICT**
- Satu baris saja: **Positif / Netral / Negatif** — alasan inti.

{_style_block()}
""".strip()


def _presentation_template() -> str:
    return f"""
Tugas analisis:
Baca presentasi perusahaan, paparan publik, atau materi investor ini. Fokus pada klaim manajemen,
arah bisnis, gap antara narasi dan bukti, serta sinyal yang belum tentu tertangkap di headline.

Format output Telegram wajib singkat, jelas, dan padat:

**📍 POIN KUNCI**
- Maksimal 3 bullet.
- Format: **[klaim/sinyal]** — dampak singkat ke tesis investasi.

**📊 MAKNA**
- Maksimal 3 kalimat.
- Jelaskan apakah narasi didukung bukti atau masih dominan storytelling.

**🎯 VERDICT**
- Satu baris saja: **Positif / Netral / Perlu Verifikasi** — alasan inti.

{_style_block()}
""".strip()


def _general_document_template() -> str:
    return f"""
Tugas analisis:
Baca dokumen ini dan identifikasi tipe informasi yang paling material. Jangan paksakan ke format laporan keuangan.
Pilih insight yang paling relevan untuk keputusan investasi, monitoring, atau riset lanjutan.

Format output Telegram wajib singkat, jelas, dan padat:

**📍 POIN KUNCI**
- Maksimal 3 bullet.
- Format: **[isu]** — dampak singkat.

**📊 MAKNA**
- Maksimal 3 kalimat.
- Jelaskan apa arti dokumen ini bagi investor atau analis.

**🎯 VERDICT**
- Satu baris saja: **Positif / Netral / Negatif / Perlu Verifikasi** — alasan inti.

{_style_block()}
""".strip()


def build_bullish_score_prompt(text: str, source: str = "manual") -> str:
    return f"""
Sumber input: {source}

Teks berita/laporan/post yang harus dinilai:
{text}

Tugas:
Berikan bullish score 0-100 untuk potensi reaksi harga jangka pendek-menengah, terutama 3 hari dan 7 hari bursa setelah informasi ini diketahui pasar.

Gunakan kerangka berikut:
- 0-20: sangat bearish / red flag dominan
- 21-40: bearish ringan / kualitas sinyal lemah
- 41-60: netral / mixed / butuh konfirmasi
- 61-75: bullish moderat
- 76-90: bullish kuat
- 91-100: exceptional, hanya jika ada katalis kuat + kualitas sinyal tinggi + risiko rendah

Faktor penilaian wajib:
1. Katalis fundamental: laba, margin, OCF, orderbook, kontrak, aksi korporasi, dividen, guidance.
2. Kualitas sinyal: apakah one-off/siklikal atau struktural dan berulang.
3. Surprise factor: apakah kemungkinan belum fully priced-in.
4. Micro-cap momentum: neraca bersih, OCF >> laba, margin akselerasi, D/E rendah, current ratio tinggi.
5. Risiko governance: koreksi laporan, related party, auditor, transaksi tidak biasa.
6. Risiko likuiditas dan kemungkinan false signal.

Format output wajib:
Bullish Score: [0-100]/100
Kategori: [Bearish/Neutral/Bullish Moderat/Bullish Kuat/Exceptional]
Ticker terdeteksi: [ticker atau tidak tersedia]
Horizon utama: [3 hari / 7 hari / perlu data tambahan]

Alasan Skor:
- [3-5 bullet alasan tajam]

Red Flags / Pelemah Skor:
- [maksimal 3 bullet]

Data yang Perlu Dicek Berikutnya:
- [laporan keuangan, broker flow, volume, harga penutupan, IDX disclosure, dsb.]

Training Note:
Tulis fitur-fitur yang layak disimpan sebagai dataset historis untuk dilabeli kemudian, misalnya: margin_acceleration=true, ocf_gt_2x_net_income=false, balance_sheet_clean=unknown, event_type=earnings_report/news/disclosure.
""".strip()
