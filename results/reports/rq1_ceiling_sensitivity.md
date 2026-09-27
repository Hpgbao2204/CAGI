# RQ1 — Kiểm tra độ nhạy với ceiling effect (Tuần 6, bổ sung)

## Đính chính số liệu
`error_analysis_v1.md` (viết trước đó) liệt kê 5 incident có M1=1.0, nhưng CHỈ **4/11** incident có CẢ B3 VÀ M1 cùng đạt PR-AUC≥0.999 ("ceiling thật sự" — 2 model không còn phân biệt được). `qbridge_qubit_2022` có M1=1.0 nhưng B3 chỉ 0.6899 — đây KHÔNG phải ceiling che mất khác biệt, mà chính là 1 trong những bằng chứng M1 > B3 rõ nhất, nên được GIỮ LẠI trong so sánh loại trừ.

## Bước 1 — Bảng n_val / PR-AUC từng fold

| Incident | n_val | n_positive | n_negative | B3 PR-AUC | M1 PR-AUC | Ceiling cả 2? |
|---|---|---|---|---|---|---|
| paraluni_2022 | 154 | 8 | 146 | 0.4324 | 0.4165 |  |
| feg_bridge_2024 | 50 | 5 | 45 | 0.8583 | 0.5997 |  |
| deltaprime_arbitrum_2024 | 155 | 4 | 151 | 0.4306 | 0.6083 |  |
| bsc_token_hub_2022 | 170 | 8 | 162 | 0.6202 | 0.6600 |  |
| wault_finance_2021 | 164 | 8 | 156 | 0.7594 | 0.6752 |  |
| ronin_bridge_2022 | 122 | 8 | 114 | 0.8832 | 0.7886 |  |
| qbridge_qubit_2022 | 225 | 8 | 217 | 0.7086 | 0.9705 |  |
| chibi_finance_2023 | 70 | 8 | 62 | 1.0000 | 1.0000 | CÓ |
| utopiasphere_2024 | 69 | 7 | 62 | 1.0000 | 1.0000 | CÓ |
| wooppv2_2024 | 57 | 4 | 53 | 1.0000 | 1.0000 | CÓ |
| xkingdom_2024 | 68 | 7 | 61 | 1.0000 | 1.0000 | CÓ |

Quan sát: 4 fold ceiling có n_val tương đối nhỏ (57-70 dòng) nhưng KHÔNG phải nhỏ nhất tuyệt đối (`feg_bridge_2024` n_val=50 — nhỏ nhất — lại KHÔNG ceiling, M1=0.5432). n_positive của fold ceiling (4,7,7,8) cũng không khác biệt hệ thống so với fold không-ceiling. → **n_val nhỏ có tương quan lỏng với ceiling nhưng không phải yếu tố quyết định duy nhất** — nhiều khả năng còn do đặc điểm hard-negative của từng incident cụ thể (dễ/khó phân biệt) hơn là thuần túy kích thước mẫu.

## Bước 2 — So sánh paired M1 vs B3: 11 fold đầy đủ vs loại 4 fold ceiling

| | n incident | Mean diff (M1-B3) | 95% CI | Wilcoxon p | CI chứa 0? |
|---|---|---|---|---|---|
| 11 fold DAY DU | 11 | +0.0024 | [-0.0734, +0.0772] | 1.0000 | Có |
| 7 fold SAU KHI LOAI ceiling | 7 | +0.0037 | [-0.1150, +0.1238] | 1.0000 | Có |

**Kết luận độ nhạy: ỔN ĐỊNH** — loại bỏ 4 fold ceiling KHÔNG làm đổi kết luận RQ1 (CI vẫn chứa 0).

## Bước 3 — Điều tra nhanh `paraluni_2022` (tệ nhất xuyên suốt B2/B3/M1)

`paraluni_2022` KHÔNG thuộc nhóm `neg_median_len ≥ pos_traj_len` — không có dấu hiệu đặc biệt về độ dài hard-negative so với positive. Không tìm thấy nguyên nhân cụ thể qua kiểm tra độ dài — cần điều tra hướng khác nếu muốn giải thích thêm (ngoài phạm vi kiểm tra nhanh này).
