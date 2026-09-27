# RQ1: So sánh M1 (typed) vs B0-B3, đặc biệt B3 (untyped/flat)

## Phương pháp
- Leave-one-incident-out (11 fold), threshold chọn qua inner leave-one-group-out TRÊN TRAIN (không bao giờ dùng test fold) — xem src/evaluation/nested_eval.py.
- Bootstrap CI 95% ở MỨC INCIDENT (resample 11 incident có hoàn lại, 2000 lần) — không phải mức prefix row (các prefix cùng 1 incident không độc lập).
- So sánh paired M1 vs B3: PR-AUC riêng từng incident (11 giá trị), bootstrap CI trên hiệu số + Wilcoxon signed-rank.

## Bảng PR-AUC mean (95% CI) theo model

| Model | Mean PR-AUC | 95% CI |
|---|---|---|
| B0 | 0.0444 | [0.0377, 0.0632] |
| B1 | 0.4094 | [0.3221, 0.5383] |
| B2 | 0.0555 | [0.0387, 0.1113] |
| B3 | 0.6890 | [0.5254, 0.8581] |
| M1 | 0.7190 | [0.5319, 0.8834] |

## So sánh paired M1 vs B3 (per-incident PR-AUC)

| Incident | M1 | B3 | Diff (M1-B3) |
|---|---|---|---|
| bsc_token_hub_2022 | 0.6508 | 0.5760 | +0.0748 |
| chibi_finance_2023 | 1.0000 | 1.0000 | +0.0000 |
| deltaprime_arbitrum_2024 | 0.5016 | 0.6237 | -0.1221 |
| feg_bridge_2024 | 0.5432 | 0.8262 | -0.2830 |
| paraluni_2022 | 0.4123 | 0.4252 | -0.0129 |
| qbridge_qubit_2022 | 1.0000 | 0.6899 | +0.3101 |
| ronin_bridge_2022 | 0.8644 | 0.8420 | +0.0224 |
| utopiasphere_2024 | 1.0000 | 1.0000 | +0.0000 |
| wault_finance_2021 | 0.7093 | 0.7698 | -0.0605 |
| wooppv2_2024 | 1.0000 | 1.0000 | +0.0000 |
| xkingdom_2024 | 1.0000 | 1.0000 | +0.0000 |

**Mean diff (M1 - B3) = -0.0065, 95% bootstrap CI (paired, mức incident) = [-0.0883, +0.0813]**

Wilcoxon signed-rank: statistic=17.0, p-value=0.9453125

## KẾT LUẬN

KHÔNG ĐỦ BẰNG CHỨNG: 95% CI của hiệu số (M1 - B3) chứa 0 — không thể kết luận M1 vượt hay thua B3 có ý nghĩa thống kê với mẫu 11 incident hiện tại.
