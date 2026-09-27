# RQ1 — Kiểm tra độ nhạy với ceiling effect (Tuần 6, bổ sung)

## Đính chính số liệu
`error_analysis_v1.md` (viết trước đó) liệt kê 5 incident có M1=1.0, nhưng CHỈ **4/11** incident có CẢ B3 VÀ M1 cùng đạt PR-AUC≥0.999 ("ceiling thật sự" — 2 model không còn phân biệt được). `qbridge_qubit_2022` có M1=1.0 nhưng B3 chỉ 0.6899 — đây KHÔNG phải ceiling che mất khác biệt, mà chính là 1 trong những bằng chứng M1 > B3 rõ nhất, nên được GIỮ LẠI trong so sánh loại trừ.

## Bước 1 — Bảng n_val / PR-AUC từng fold

| Incident | n_val | n_positive | n_negative | B3 PR-AUC | M1 PR-AUC | Ceiling cả 2? |
|---|---|---|---|---|---|---|
| paraluni_2022 | 154 | 8 | 146 | 0.4252 | 0.4123 |  |
| deltaprime_arbitrum_2024 | 155 | 4 | 151 | 0.6237 | 0.5016 |  |
| feg_bridge_2024 | 50 | 5 | 45 | 0.8262 | 0.5432 |  |
| bsc_token_hub_2022 | 170 | 8 | 162 | 0.5760 | 0.6508 |  |
| wault_finance_2021 | 164 | 8 | 156 | 0.7698 | 0.7093 |  |
| ronin_bridge_2022 | 122 | 8 | 114 | 0.8420 | 0.8644 |  |
| qbridge_qubit_2022 | 225 | 8 | 217 | 0.6899 | 1.0000 |  |
| chibi_finance_2023 | 70 | 8 | 62 | 1.0000 | 1.0000 | CÓ |
| utopiasphere_2024 | 69 | 7 | 62 | 1.0000 | 1.0000 | CÓ |
| wooppv2_2024 | 57 | 4 | 53 | 1.0000 | 1.0000 | CÓ |
| xkingdom_2024 | 68 | 7 | 61 | 1.0000 | 1.0000 | CÓ |

Quan sát: 4 fold ceiling có n_val tương đối nhỏ (57-70 dòng) nhưng KHÔNG phải nhỏ nhất tuyệt đối (`feg_bridge_2024` n_val=50 — nhỏ nhất — lại KHÔNG ceiling, M1=0.5432). n_positive của fold ceiling (4,7,7,8) cũng không khác biệt hệ thống so với fold không-ceiling. → **n_val nhỏ có tương quan lỏng với ceiling nhưng không phải yếu tố quyết định duy nhất** — nhiều khả năng còn do đặc điểm hard-negative của từng incident cụ thể (dễ/khó phân biệt) hơn là thuần túy kích thước mẫu.

## Bước 2 — So sánh paired M1 vs B3: 11 fold đầy đủ vs loại 4 fold ceiling

| | n incident | Mean diff (M1-B3) | 95% CI | Wilcoxon p | CI chứa 0? |
|---|---|---|---|---|---|
| 11 fold DAY DU | 11 | -0.0065 | [-0.0883, +0.0813] | 0.9453 | Có |
| 7 fold SAU KHI LOAI ceiling | 7 | -0.0102 | [-0.1349, +0.1245] | 0.9375 | Có |

**Kết luận độ nhạy: ỔN ĐỊNH** — loại bỏ 4 fold ceiling KHÔNG làm đổi kết luận RQ1 (CI vẫn chứa 0).

## Bước 3 — Điều tra nhanh `paraluni_2022` (tệ nhất xuyên suốt B2/B3/M1)

**Phát hiện chính:** hard-negative của `paraluni_2022` có **median độ dài trajectory = 25 action**,
**dài hơn cả positive (24 action)** — đây là **trường hợp DUY NHẤT trong 11 incident** mà
`neg_median_len ≥ pos_len` (10 incident còn lại: hard-negative median chỉ 1-3 action, ngắn hơn
positive rất nhiều — xem bảng dưới).

| Incident | pos_traj_len | neg_median_len | neg_max_len |
|---|---|---|---|
| paraluni_2022 | 24 | **25.0** | 1000 |
| wault_finance_2021 | 15 | 17.5 | 1000 |
| qbridge_qubit_2022 | 52 | 76.0 | 858 |
| 8 incident còn lại | 5–113 | 1.0–3.0 | 2–229 |

**Cấu trúc hành động:** positive `paraluni_2022` gồm 21 `transfer` + 3 `swap` (87.5% transfer,
không có bridge/mixer/lending) — hard-negative cũng chủ yếu `transfer` (median 12, mean 230.7 do
đuôi phân phối dài). Không phát hiện đặc trưng `swap_after_bridge`/`num_bridge_families` nào phân
biệt rõ 2 lớp.

**Kiểm tra nhanh dấu hiệu bug:** xác nhận địa chỉ seed của positive KHÔNG trùng với bất kỳ
hard-negative nào (`False`), toàn bộ 10 hard-negative "khó" của group này dùng đúng contract
PancakeSwap V2 theo tiêu chí mining đã định — không có dấu hiệu lỗi dữ liệu/mining.

**Kết luận: đây là ĐẶC TÍNH THẬT của incident, không phải bug.** `paraluni_2022`'s positive
trajectory tương đối "đơn điệu" (gần như toàn `transfer`, không có motif bridge/mixer đặc trưng)
— đúng như thiết kế sửa shortcut ở Tuần 5 (mine hard-negative "khó" theo độ phức tạp tương đương),
group này vô tình có nhiều hard-negative PancakeSwap V2 hợp pháp với chuỗi transfer dài tương đương
hoặc dài hơn — khiến tín hiệu độ dài/số lượng hành động (vốn hữu ích ở 10 incident khác) mất tác
dụng phân biệt ở đây. Ghi nhận, không đào sâu thêm.
