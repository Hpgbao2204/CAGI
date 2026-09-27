# RQ1: So sánh M1 (typed) vs B0-B3, đặc biệt B3 (untyped/flat)

## Phương pháp
- Leave-one-incident-out (11 fold), threshold chọn qua inner leave-one-group-out TRÊN TRAIN (không bao giờ dùng test fold) — xem src/evaluation/nested_eval.py.
- Bootstrap CI 95% ở MỨC INCIDENT (resample 11 incident có hoàn lại, 2000 lần) — không phải mức prefix row (các prefix cùng 1 incident không độc lập).
- So sánh paired M1 vs B3: PR-AUC riêng từng incident (11 giá trị), bootstrap CI trên hiệu số + Wilcoxon signed-rank.

## Bảng PR-AUC mean (95% CI) theo model

| Model | Mean PR-AUC | 95% CI |
|---|---|---|
| B0 | 0.0498 | [0.0420, 0.0729] |
| B1 | 0.5019 | [0.4131, 0.6332] |
| B2 | 0.0651 | [0.0467, 0.1241] |
| B3 | 0.6837 | [0.5369, 0.8825] |
| M1 | 0.6231 | [0.4741, 0.8617] |

## So sánh paired M1 vs B3 (per-incident PR-AUC)

| Incident | M1 | B3 | Diff (M1-B3) |
|---|---|---|---|
| bsc_token_hub_2022 | 1.0000 | 0.9417 | +0.0583 |
| chibi_finance_2023 | 1.0000 | 1.0000 | +0.0000 |
| deltaprime_arbitrum_2024 | 0.8195 | 0.9167 | -0.0972 |
| feg_bridge_2024 | 0.2986 | 0.6726 | -0.3740 |
| paraluni_2022 | 0.5007 | 0.5436 | -0.0429 |
| qbridge_qubit_2022 | 0.7291 | 0.7265 | +0.0026 |
| ronin_bridge_2022 | 0.5677 | 0.6137 | -0.0460 |
| utopiasphere_2024 | 0.8590 | 0.8273 | +0.0317 |
| wault_finance_2021 | 0.9861 | 0.9594 | +0.0267 |
| wooppv2_2024 | 0.9006 | 0.9861 | -0.0855 |
| xkingdom_2024 | 1.0000 | 1.0000 | +0.0000 |

**Mean diff (M1 - B3) = -0.0478, 95% bootstrap CI (paired, mức incident) = [-0.1268, +0.0076]**

Wilcoxon signed-rank: statistic=12.0, p-value=0.25

## KẾT LUẬN

KHÔNG ĐỦ BẰNG CHỨNG: 95% CI của hiệu số (M1 - B3) chứa 0 — không thể kết luận M1 vượt hay thua B3 có ý nghĩa thống kê với mẫu 11 incident hiện tại.
