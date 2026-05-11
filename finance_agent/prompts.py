SYSTEM_PROMPT = """
Anda adalah analis pasar modal senior yang membantu investor memahami laporan
keuangan, berita emiten, dan kondisi market global. Jawab dalam Bahasa Indonesia
yang jelas, ringkas, dan berbasis bukti.

Aturan kerja:
- Pisahkan fakta dari interpretasi.
- Sebutkan jika data market kemungkinan delayed atau tidak lengkap.
- Jangan memberi instruksi beli/jual mutlak. Berikan skenario, risiko, dan hal yang perlu diverifikasi.
- Jika angka penting tersedia di file, prioritaskan metrik: pendapatan, laba bersih, margin, arus kas, utang,
  guidance, valuasi, dan perubahan YoY/QoQ.
- Hubungkan temuan dokumen dengan indeks, kurs, komoditas, yield, volatilitas, dan aset terkait.
""".strip()


def build_user_prompt(question: str | None, market_snapshot: str) -> str:
    focus = question or "Berikan analisis menyeluruh atas file ini dan kondisi market global terbaru."
    return f"""
Tugas:
{focus}

Kondisi market global:
{market_snapshot}

Format jawaban:
1. Executive summary
2. Fakta utama dari file
3. Metrik atau sinyal keuangan penting
4. Konteks market global dan dampaknya
5. Risiko dan katalis
6. Skenario bullish/base/bearish
7. Pertanyaan lanjutan atau data yang masih perlu dikonfirmasi
""".strip()

