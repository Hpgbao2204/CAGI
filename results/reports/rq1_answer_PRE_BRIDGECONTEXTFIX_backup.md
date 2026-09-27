# RQ1: So sánh M1 (typed) vs B0-B3, đặc biệt B3 (untyped/flat)

## Phương pháp
- Leave-one-incident-out (11 fold), threshold chọn qua inner leave-one-group-out TRÊN TRAIN (không bao giờ dùng test fold) — xem src/evaluation/nested_eval.py.
- Bootstrap CI 95% ở MỨC INCIDENT (resample 11 incident có hoàn lại, 2000 lần) — không phải mức prefix row (các prefix cùng 1 incident không độc lập).
- So sánh paired M1 vs B3: PR-AUC riêng từng incident (11 giá trị), bootstrap CI trên hiệu số + Wilcoxon signed-rank.

## Bảng PR-AUC mean (95% CI) theo model

| Model | Mean PR-AUC | 95% CI |
|---|---|---|
| B0 | 0.0503 | [0.0435, 0.0652] |
| B1 | 0.4570 | [0.3670, 0.5645] |
| B2 | 0.0755 | [0.0554, 0.1224] |
| B3 | 0.6875 | [0.5557, 0.8601] |
| M1 | 0.6325 | [0.4808, 0.8724] |

## So sánh paired M1 vs B3 (per-incident PR-AUC)

| Incident | M1 | B3 | Diff (M1-B3) |
|---|---|---|---|
| bsc_token_hub_2022 | 1.0000 | 0.9417 | +0.0583 |
| chibi_finance_2023 | 1.0000 | 1.0000 | +0.0000 |
| deltaprime_arbitrum_2024 | 0.8420 | 0.9042 | -0.0622 |
| feg_bridge_2024 | 0.2120 | 0.9667 | -0.7547 |
| hackerdao_2022 | 0.4233 | 0.6041 | -0.1808 |
| magic_abracadabra_arbitrum_2025 | 0.9503 | 0.8854 | +0.0649 |
| new_free_dao_2022 | 0.9379 | 0.4263 | +0.5116 |
| paraluni_2022 | 0.5984 | 0.5465 | +0.0519 |
| qbridge_qubit_2022 | 0.8114 | 0.8534 | -0.0420 |
| radiant_capital_arbitrum_2024 | 1.0000 | 0.9861 | +0.0139 |
| ronin_bridge_2022 | 0.5694 | 0.6009 | -0.0315 |
| utopiasphere_2024 | 1.0000 | 1.0000 | +0.0000 |
| wault_finance_2021 | 0.9381 | 0.9306 | +0.0076 |
| wooppv2_2024 | 0.8581 | 0.9184 | -0.0603 |
| xkingdom_2024 | 1.0000 | 1.0000 | +0.0000 |

**Mean diff (M1 - B3) = -0.0282, 95% bootstrap CI (paired, mức incident) = [-0.1565, +0.0902]**

Wilcoxon signed-rank: statistic=34.0, p-value=0.6948866023724733

## KẾT LUẬN

KHÔNG ĐỦ BẰNG CHỨNG: 95% CI của hiệu số (M1 - B3) chứa 0 — không thể kết luận M1 vượt hay thua B3 có ý nghĩa thống kê với mẫu 11 incident hiện tại.
