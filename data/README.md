# Historical Training Dataset

Folder ini untuk menyimpan event historis laporan/berita dan outcome harga setelah event.

Target awal:
- label_3d_up_10pct = true jika saham naik minimal 10% dalam 3 hari bursa setelah laporan/berita muncul.
- return_7d_pct untuk melihat follow-through.
- features_json berisi fitur forensik dari agent, misalnya margin_acceleration, ocf_gt_2x_net_income, clean_balance_sheet, governance_red_flag.

Dataset ini nantinya bisa dipakai untuk kalibrasi scoring, backtest, atau training model klasifikasi.
