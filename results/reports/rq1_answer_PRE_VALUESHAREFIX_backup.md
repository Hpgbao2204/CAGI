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
| B3 | 0.7039 | [0.5443, 0.8696] |
| M1 | 0.7130 | [0.5315, 0.8742] |

## So sánh paired M1 vs B3 (per-incident PR-AUC)

| Incident | M1 | B3 | Diff (M1-B3) |
|---|---|---|---|
| bsc_token_hub_2022 | 0.6600 | 0.6202 | +0.0397 |
| chibi_finance_2023 | 1.0000 | 1.0000 | +0.0000 |
| deltaprime_arbitrum_2024 | 0.6083 | 0.4306 | +0.1778 |
| feg_bridge_2024 | 0.5997 | 0.8583 | -0.2586 |
| paraluni_2022 | 0.4165 | 0.4324 | -0.0159 |
| qbridge_qubit_2022 | 0.9705 | 0.7086 | +0.2619 |
| ronin_bridge_2022 | 0.7886 | 0.8832 | -0.0946 |
| utopiasphere_2024 | 1.0000 | 1.0000 | +0.0000 |
| wault_finance_2021 | 0.6752 | 0.7594 | -0.0842 |
| wooppv2_2024 | 1.0000 | 1.0000 | +0.0000 |
| xkingdom_2024 | 1.0000 | 1.0000 | +0.0000 |

**Mean diff (M1 - B3) = +0.0024, 95% bootstrap CI (paired, mức incident) = [-0.0734, +0.0772]**

Wilcoxon signed-rank: statistic=18.0, p-value=1.0

## KẾT LUẬN

KHÔNG ĐỦ BẰNG CHỨNG: 95% CI của hiệu số (M1 - B3) chứa 0 — không thể kết luận M1 vượt hay thua B3 có ý nghĩa thống kê với mẫu 11 incident hiện tại.
