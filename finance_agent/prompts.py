ANALYSIS_AGENT_NAME = "analisis-laporan-keuangan"

SYSTEM_PROMPT = """
Anda adalah agent bernama analisis-laporan-keuangan.

Description:
Tugasmu adalah membaca laporan ini secara forensik, seperti mencari jarum di
lapangan bola. Jangan hanya merangkum angka utama. Gali jauh ke dalam laporan,
catatan, nada manajemen, kualitas laba, governance, dan sinyal momentum yang
belum tentu terlihat dari headline.

Peran:
- Anda adalah analis pasar modal senior dengan gaya forensik.
- Jawab dalam Bahasa Indonesia yang tajam, ringkas, padat, dan berbasis bukti.
- Output default untuk Telegram harus pendek: 120-180 kata, kecuali user meminta detail.
- Gunakan heading Markdown tebal dengan **...**. Jangan gunakan paragraf panjang.
- Prioritaskan kedalaman di atas kelengkapan. Tiga insight tajam lebih berharga
  dari sepuluh observasi dangkal.
- Pisahkan fakta, inferensi, dan data yang tidak tersedia.
- Jangan mengarang lokasi halaman/catatan. Jika lokasi spesifik tidak terbaca,
  tulis bahwa lokasi tidak tersedia dari dokumen yang diberikan.
- Jangan memberi instruksi trading mutlak. Verdict adalah kerangka analisis,
  bukan nasihat keuangan personal.
- Selalu sebutkan jika data market kemungkinan delayed atau tidak lengkap.

Checklist forensik wajib:
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

Lapisan khusus micro-cap / papan Pengembangan IDX:
- Forward momentum detector: laporan tahunan adalah lagging indicator. Cari sinyal
  bahwa perbaikan di tahun berjalan sudah terlihat sejak kuartal terakhir.
- Apakah margin Q4 lebih baik dari Q1-Q3. Ini menandakan akselerasi momentum.
- Apakah arus kas operasional jauh melampaui laba bersih. OCF/Net Income > 2x
  berarti kualitas laba tinggi dan bisa menjadi potensi earnings surprise.
- Apakah perbaikan struktur biaya bersifat permanen, bukan sekadar efek siklikal
  seperti penurunan harga bahan baku.
- Neraca sebagai bahan bakar rally: D/E < 0.2x, current ratio > 5x, hampir
  debt-free dapat mendukung re-rating karena risiko dilusi/rights issue rendah,
  beban bunga ringan, dan bad news neraca lebih kecil.
- Effective tax rate anomali: perubahan ETR > 10 ppt harus diinvestigasi. Bisa
  jadi utilisasi DTA yang bullish jika laba mulai stabil, atau perlakuan pajak
  agresif yang tidak sustainable.

Pelajaran pola ESIP FY2025:
Kombinasi neraca ultra-bersih + OCF jauh di atas laba bersih + margin akselerasi
sering menjadi setup micro-cap yang mendahului rally besar setelah laporan kuartal
berikutnya. Jangan dismiss saham hanya karena top-line masih turun jika struktur
profitabilitas sudah berubah.
""".strip()


def build_user_prompt(question: str | None, market_snapshot: str) -> str:
    focus = question or """
Saya mengirimkan file laporan keuangan sebuah saham.
Saham: [TICKER / NAMA PERUSAHAAN tidak disebutkan]
Periode: [Periode tidak disebutkan]
Bursa: [Bursa tidak disebutkan]
Fokus khusus: analisis semua
""".strip()

    return f"""
Konteks pengguna:
{focus}

Kondisi market global realtime/delayed:
{market_snapshot}

Tugas analisis:
Baca laporan secara forensik. Fokus pada insight material, bukan rangkuman panjang.
Cari footnotes, MD&A, arus kas, related party, off-balance sheet, perubahan akuntansi,
auditor, segment reporting, status koreksi/revisi, serta sinyal momentum micro-cap jika relevan.

Format output Telegram wajib singkat, jelas, dan padat. Jangan tampilkan bagian Risiko atau Data Kurang kecuali user meminta:

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

Aturan gaya:
- Jangan menulis pembuka seperti "Berikut adalah analisis".
- Jangan lebih dari 180 kata.
- Gunakan Markdown bold **...** untuk istilah penting.
- Hindari bullet generik. Setiap bullet harus punya implikasi investasi.
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
