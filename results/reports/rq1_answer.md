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
| M1 | 0.6624 | [0.5234, 0.8864] |

## So sánh paired M1 vs B3 (per-incident PR-AUC)

| Incident | M1 | B3 | Diff (M1-B3) |
|---|---|---|---|
| bsc_token_hub_2022 | 1.0000 | 0.9417 | +0.0583 |
| chibi_finance_2023 | 1.0000 | 1.0000 | +0.0000 |
| deltaprime_arbitrum_2024 | 0.8618 | 0.9042 | -0.0424 |
| feg_bridge_2024 | 0.8303 | 0.9667 | -0.1364 |
| hackerdao_2022 | 0.5053 | 0.6041 | -0.0988 |
| magic_abracadabra_arbitrum_2025 | 0.9503 | 0.8854 | +0.0649 |
| new_free_dao_2022 | 1.0000 | 0.4263 | +0.5737 |
| paraluni_2022 | 0.5894 | 0.5465 | +0.0429 |
| qbridge_qubit_2022 | 0.8943 | 0.8534 | +0.0410 |
| radiant_capital_arbitrum_2024 | 1.0000 | 0.9861 | +0.0139 |
| ronin_bridge_2022 | 0.6793 | 0.6009 | +0.0784 |
| utopiasphere_2024 | 1.0000 | 1.0000 | +0.0000 |
| wault_finance_2021 | 0.9284 | 0.9306 | -0.0021 |
| wooppv2_2024 | 0.8581 | 0.9184 | -0.0603 |
| xkingdom_2024 | 1.0000 | 1.0000 | +0.0000 |

**Mean diff (M1 - B3) = +0.0355, 95% bootstrap CI (paired, mức incident) = [-0.0286, +0.1288]**

Wilcoxon signed-rank: statistic=33.0, p-value=0.6378701798979456

## KẾT LUẬN

KHÔNG ĐỦ BẰNG CHỨNG: 95% CI của hiệu số (M1 - B3) chứa 0 — không thể kết luận M1 vượt hay thua B3 có ý nghĩa thống kê với mẫu 11 incident hiện tại.
