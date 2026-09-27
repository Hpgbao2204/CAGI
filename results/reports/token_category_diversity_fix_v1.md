# Sửa bug `token_category_diversity` (feature chính thức) — Tuần 11, Bước 3

**Bug:** `token_category_diversity` (nhóm `economic`, `src/features/extractor.py::_economic_features`)
đếm **MỌI token phân biệt** (`len({a.token for a in actions if a.token})`),
**KHÔNG lọc theo value share** — bị dust/spam token thổi phồng diversity
giả tạo, đúng như tài liệu gốc mục 3.9 đã cảnh báo nhưng chưa được
implement đúng cho tới giờ (phát hiện lại khi làm feature ứng viên
`token_diversity_filtered` ở Giai đoạn A, xem
`configs/features_v3_candidate.yaml`).

**Sửa:** chỉ đếm token có value share ≥ 1% tổng inflow THẬT (dùng RAW
value qua `math.expm1`, không cộng dồn trực tiếp trên `amount_norm`
log-scale — quy ước toán học đã có trong dự án). Xem code + docstring tại
`_economic_features()`.

## Tác động lên dữ liệu

| | Trước | Sau |
|---|---|---|
| `token_category_diversity` mean | 1.176 | 1.080 |
| max | 7 | 6 |
| Số dòng thay đổi giá trị | — | 234/2681 (8.7%) |

## Tác động lên RQ1 (đã rerun đầy đủ: main_table.csv + ceiling sensitivity)

`token_category_diversity` là 1 trong 4 feature economic của **B3**
(`FLAT_UNTYPED_FEATURES`) — nên B3 chịu ảnh hưởng trực tiếp, rõ hơn M1
(dùng toàn bộ feature, pha loãng tác động của 1 cột).

| Model | Mean PR-AUC TRƯỚC | Mean PR-AUC SAU | Δ |
|---|---|---|---|
| B0 | 0.0444 | 0.0444 | 0 (không dùng feature) |
| B1 | 0.4094 | 0.4094 | 0 (không dùng token_category_diversity) |
| B2 | 0.0555 | 0.0555 | 0 (chỉ dùng action_count_*_ratio) |
| **B3** | 0.6890 | **0.7039** | **+0.0149** |
| **M1** | 0.7190 | **0.7130** | **-0.0060** |

**Paired M1 vs B3 (đúng phương pháp bootstrap CI mức incident):**

| | Mean diff (M1-B3) | 95% CI | Wilcoxon p | Kết luận |
|---|---|---|---|---|
| TRƯỚC (bug) | -0.0065 | [-0.0883, +0.0813] | 0.9453 | KHÔNG ĐỦ BẰNG CHỨNG |
| **SAU (đã sửa)** | **+0.0024** | **[-0.0734, +0.0772]** | **1.0000** | **KHÔNG ĐỦ BẰNG CHỨNG** |

Dấu của mean diff đổi (-0.0065 → +0.0024) nhưng **độ lớn không đáng kể**
so với độ rộng CI (~0.15) — **KHÔNG đổi kết luận RQ1**.

**Ceiling sensitivity (đã rerun lại):** vẫn 4/11 fold ceiling thật (không
đổi so với trước), paired comparison 11-fold vs 7-fold-loại-ceiling đều CI
chứa 0 cả trước và sau — **kết luận độ nhạy: ỔN ĐỊNH cả trước và sau khi
sửa bug này**, giống pattern đã thấy với các lần sửa bug trước (Tuần 7/9).

Per-incident đổi đáng chú ý nhất: `deltaprime_arbitrum_2024` B3 giảm mạnh
(0.6237→0.4306, do positive trajectory rất ngắn — 5 action — nên 1 cột
thay đổi ảnh hưởng tỷ trọng lớn), `qbridge_qubit_2022` B3 tăng
(0.6899→0.7086), `feg_bridge_2024` B3 tăng (0.8262→0.8583). Không có
incident nào đổi chiều kết luận (không incident nào chuyển từ "M1 thắng
rõ" sang "B3 thắng rõ" hay ngược lại).

## File đã cập nhật (chính thức)

- `data/processed/features_v2.parquet` (2681 dòng, không đổi — chỉ đổi
  giá trị `token_category_diversity`)
- `results/tables/main_table.csv`, `baseline_results_v2.csv`
- `results/reports/rq1_answer.md`, `rq1_ceiling_sensitivity.md`,
  `error_analysis_v1.md`
- `results/models/m1_final.joblib` + `model_card_m1.md` (train lại)
- `data/processed/oof_predictions_v1.csv`

Backup bản trước khi sửa: hậu tố `_PRE_TOKENDIVFIX_backup` (cùng quy ước
đã dùng cho các lần sửa bug trước — Tuần 9/10).

## Kết luận

Bug đã sửa gốc trong pipeline chính thức. **RQ1 vững trước và sau khi sửa
bug này** — đã kiểm tra độ nhạy đầy đủ (bootstrap CI + ceiling sensitivity),
giống tinh thần các lần sửa bug trước trong dự án.
