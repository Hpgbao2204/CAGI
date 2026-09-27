# RQ1/RQ2/Ablation rerun sau fix `value_share` gộp-token + thêm incident thứ 12

Xem `results/reports/value_share_unit_mix_fix_v1.md` cho chi tiết bug + quá
trình rebuild dữ liệu. File này chỉ so sánh kết quả RQ1/RQ2/ablation
**TRƯỚC** (11 incident, dataset cũ) vs **SAU** (12 incident, dataset đã
rebuild đúng).

## RQ1: M1 (typed) vs B3 (untyped/flat)

| Model | Mean PR-AUC TRƯỚC (11 incident) | Mean PR-AUC SAU (12 incident, bootstrap pooled) |
|---|---|---|
| B0 | 0.0444 | 0.0498 |
| B1 | 0.4094 | 0.5019 |
| B2 | 0.0555 | 0.0651 |
| B3 | 0.7039 | 0.6837 |
| M1 | 0.7130 | 0.6231 |

**Paired M1 vs B3 (per-incident PR-AUC, chỉ trên incident có cả 2 lớp —
`radiant_capital_arbitrum_2024` bị loại khỏi so sánh paired vì CHƯA có
hard-negative mined riêng, `pr_auc=nan` cho mọi model, xem phần "Hạn chế" bên
dưới):**

| | Mean diff (M1-B3) | 95% CI | Wilcoxon p | Kết luận |
|---|---|---|---|---|
| TRƯỚC (11 incident) | +0.0024 | [-0.0734, +0.0772] | 1.0000 | KHÔNG ĐỦ BẰNG CHỨNG |
| **SAU (11 incident hợp lệ, dataset mới)** | **-0.0478** | **[-0.1268, +0.0076]** | **0.25** | **KHÔNG ĐỦ BẰNG CHỨNG** |

Dấu của mean diff đổi (+0.0024 → -0.0478, do trajectory nhiều incident thay
đổi RẤT LỚN — vd `paraluni_2022` 38→511 action, `ronin_bridge_2022`
113→1625) nhưng **kết luận RQ1 KHÔNG ĐỔI**: CI 95% của hiệu số vẫn chứa 0 dù
cận trên đã tiến sát 0 (+0.0076) — vẫn KHÔNG ĐỦ BẰNG CHỨNG để khẳng định M1
vượt hay thua B3 có ý nghĩa thống kê. Nhất quán với pattern đã thấy ở các
lần sửa bug trước (Tuần 7 generate_prefixes, Tuần 9 token_category_diversity):
con số thay đổi nhưng kết luận định tính ổn định.

## Ablation (E4 no-temporal, E5 no-motif, no-bridge-context)

Tất cả paired diff vs M1_full đều có 95% CI chứa 0 (no_temporal: +0.0265
[-0.0171,+0.0829] p=0.55; no_motif: +0.0135 [-0.0072,+0.0389] p=0.31;
no_bridge_context: +0.0068 [-0.0083,+0.0274] p=0.84) — **kết luận không đổi
so với Tuần 9**: chưa đủ bằng chứng cho đóng góp riêng của temporal/motif
semantics trên tập incident hiện tại.

## RQ2 (per-prefix-bucket, không pool)

Chạy thành công trên 12 incident, 8 prefix bucket (ratio_25/50/75/100,
k_2/3/5/7). Mean PR-AUC theo bucket dao động 0.66-0.91, pattern tương tự
trước (bucket dài hơn — ratio_100, k_7 — có PR-AUC cao hơn bucket ngắn ratio_25/k_2/k_3).
`radiant_capital_arbitrum_2024` cho `pr_auc=nan` ở nhiều bucket vì thiếu
hard-negative riêng (chỉ có 1 positive prefix, không có negative để tính
PR-AUC khi làm held-out fold).

## Hạn chế cần lưu ý: `radiant_capital_arbitrum_2024` CHƯA có hard-negative mined

Incident mới thêm trong phiên này CHƯA qua bước mining hard-negative bổ
sung (đây là công việc Bước 2 "revisit" của Giai đoạn B, dự kiến làm SAU khi
Bước 3 mở rộng đủ incident). Vì vậy fold held-out của nó không có mẫu âm để
tính PR-AUC (`nan`) — nó vẫn đóng góp vào bootstrap pooled (main_table.csv,
vì bootstrap resample tất cả 12 group rồi tính PR-AUC trên toàn bộ dữ liệu
pooled, không yêu cầu từng group phải có cả 2 lớp) nhưng KHÔNG xuất hiện
trong so sánh paired M1-vs-B3 (per-incident) hay bootstrap RQ2 theo bucket.
Đây là trạng thái tạm thời, trung thực — không che giấu, sẽ được giải quyết
khi mining hard-negative cho incident này.

## File đã cập nhật

- `data/processed/features_v2.parquet` (2726 dòng, trước 2681)
- `results/tables/main_table.csv`, `baseline_results_v2.csv`,
  `ablation_table.csv`, `rq2_prefix_evaluation_folds.csv`
- `results/reports/rq1_answer.md`, `ablation_e4_e5_v1.md`
- `data/processed/oof_predictions_v1.csv`, `rq2_oof_predictions.csv`

Backup bản trước khi sửa: hậu tố `_PRE_VALUESHAREFIX_backup` (cùng quy ước
đã dùng cho các lần sửa bug trước).

## Việc CÒN LẠI

- Viết lại `paraluni_2022_reinvestigation.md` (kết luận cũ dựa trên
  trajectory 38 action đã lỗi thời, nay có 511 action thật).
- Mining hard-negative cho `radiant_capital_arbitrum_2024` (Bước 2 revisit).
- Tiếp tục Giai đoạn B Bước 3 (mở rộng thêm incident, target 15), Bước 4-6.
