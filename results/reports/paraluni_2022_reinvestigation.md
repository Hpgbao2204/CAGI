# Điều tra lại `paraluni_2022` (Tuần 10, cập nhật 2026-08-27)

**Bối cảnh gốc (Tuần 10):** lời giải thích ban đầu (Tuần 6: "hard-negative median length ≈ positive length") đã LỖI THỜI sau khi sửa bug `generate_prefixes` (Tuần 7) — con số median=25 trước đó bị thổi phồng giả tạo do chỉ 10/31 hard-negative có dòng `ratio_100`. Điều tra Tuần 10 tìm nguyên nhân THẬT trên dữ liệu đã sửa 2 bug (prefix + dedupe), xác nhận `paraluni_2022` vẫn là ca tệ nhất (PR-AUC M1 = 0.4123) do hành vi `log_amount_mean` bất thường ở mốc prefix sớm.

**CẬP NHẬT 2026-08-27 (Giai đoạn B):** sau khi sửa bug `value_share` gộp-token trong `build_trajectory()` (xem `results/reports/value_share_unit_mix_fix_v1.md`), trajectory thật của `paraluni_2022` tăng từ 38 → **511 action** (nhiều bằng chứng bridge/swap thật trước đây bị loại oan). Kết quả: **`paraluni_2022` KHÔNG CÒN LÀ CA TỆ NHẤT** — báo cáo này viết lại Bước 1-2 trên dữ liệu mới, xác nhận và giải thích sự thay đổi này thay vì tiếp tục giả định nó vẫn là ca khó nhất.

## Bước 1 — Xác nhận thứ hạng hiện tại (đã đổi)

`paraluni_2022` xếp hạng **2/12** (PR-AUC M1 = 0.5112) trên `main_table.csv` hiện tại (12 incident, sau fix value_share) — **KHÔNG CÒN tệ nhất**. Ca tệ nhất mới là **`feg_bridge_2024`** (PR-AUC = 0.2979), trajectory của nó chỉ có 9 action và KHÔNG bị ảnh hưởng bởi bug value_share (không có hoạt động đa token) — nguyên nhân vì sao nó tệ là câu hỏi KHÁC, ngoài phạm vi báo cáo này (chưa điều tra).

| Incident (xếp từ tệ→tốt) | PR-AUC M1 |
|---|---|
| feg_bridge_2024 | 0.2979 |
| paraluni_2022 | 0.5112 |
| ronin_bridge_2022 | 0.5226 |
| qbridge_qubit_2022 | 0.7267 |
| deltaprime_arbitrum_2024 | 0.8356 |
| utopiasphere_2024 | 0.8830 |
| wooppv2_2024 | 0.8850 |
| radiant_capital_arbitrum_2024 | 0.9705 |
| chibi_finance_2023 | 1.0000 |
| bsc_token_hub_2022 | 1.0000 |
| wault_finance_2021 | 1.0000 |
| xkingdom_2024 | 1.0000 |

## Bước 2a — So sánh feature: positive `paraluni_2022` vs 11 incident khác

Số motif = 0 (không xuất hiện) ở positive `paraluni_2022`: **2/7** — so với 11 incident khác: median=3.0, min=2, max=5.

| Nhóm | Feature | paraluni_2022 | Median 11 incident khác | Min-Max 11 incident khác | Outlier? |
|---|---|---|---|---|---|
| economic | log_amount_mean | 1.6888 | 1.7849 | [1.0100, 2.4056] | không |
| economic | value_retention | 4290.4307 | 0.6742 | [0.0019, 142.2192] | **CÓ** |
| economic | outgoing_incoming_ratio | 0.9924 | 1.0000 | [0.8154, 1.0000] | không |
| economic | token_category_diversity | 2.0000 | 3.0000 | [1.0000, 15.0000] | không |
| structural | fan_out | 7.0000 | 3.0000 | [1.0000, 13.0000] | không |
| structural | fan_in | 3.0000 | 1.0000 | [0.0000, 3.0000] | không |
| structural | path_depth | 4.0000 | 3.0000 | [1.0000, 6.0000] | không |
| structural | branch_count | 36.0000 | 6.0000 | [1.0000, 52.0000] | không |
| structural | unique_counterparties | 106.0000 | 16.0000 | [1.0000, 177.0000] | không |
| structural | local_ego_density | 0.0152 | 0.0877 | [0.0102, 0.5000] | không |
| motif | motif_split | 36.0000 | 6.0000 | [1.0000, 52.0000] | không |
| motif | motif_merge | 58.0000 | 8.0000 | [1.0000, 118.0000] | không |
| motif | motif_peel_like_chain | 1.0000 | 0.0000 | [0.0000, 1.0000] | không |
| motif | motif_bridge_then_swap | 0.0000 | 0.0000 | [0.0000, 4.0000] | không |
| motif | motif_swap_then_split | 2.0000 | 0.0000 | [0.0000, 4.0000] | không |
| motif | motif_nested_bridge | 0.0000 | 0.0000 | [0.0000, 1.0000] | không |
| motif | motif_rapid_token_pivot | 328.0000 | 21.0000 | [0.0000, 1331.0000] | không |
| action_ratio | action_count_transfer_ratio | 0.8023 | 0.7000 | [0.0000, 0.9130] | không |
| action_ratio | action_count_swap_ratio | 0.1487 | 0.1032 | [0.0000, 0.2928] | không |
| action_ratio | action_count_split_ratio | 0.0411 | 0.0000 | [0.0000, 0.0716] | không |
| action_ratio | action_count_merge_ratio | 0.0078 | 0.0000 | [0.0000, 0.0548] | không |
| action_ratio | action_count_bridge_deposit_ratio | 0.0000 | 0.0435 | [0.0000, 0.5405] | không |
| action_ratio | action_count_bridge_withdraw_ratio | 0.0000 | 0.0000 | [0.0000, 0.0000] | không |
| action_ratio | action_count_mixer_or_exit_ratio | 0.0000 | 0.0000 | [0.0000, 1.0000] | không |
| action_ratio | action_count_lending_deposit_ratio | 0.0000 | 0.0000 | [0.0000, 0.0083] | không |

## Bước 2b — Volume band: positive vs hard-negative (log_amount_mean)

`paraluni_2022` xếp hạng **12/12** về độ lệch volume band (1 = lệch nhiều nhất giữa positive và median hard-negative) — lệch tuyệt đối = 0.4687 (positive=1.6888, hard-negative median=1.2201, n=32).

| Incident | positive log_amount_mean | hard-negative median | \|lệch\| | n hard-negative |
|---|---|---|---|---|
| bsc_token_hub_2022 | 2.4056 | 0.5557 | 1.8499 | 78 |
| utopiasphere_2024 | 2.0663 | 0.2623 | 1.8040 | 33 |
| ronin_bridge_2022 | 1.8551 | 0.0620 | 1.7931 | 75 |
| wooppv2_2024 | 1.9516 | 0.2541 | 1.6975 | 35 |
| deltaprime_arbitrum_2024 | 1.7849 | 0.1601 | 1.6247 | 75 |
| wault_finance_2021 | 2.0845 | 0.4818 | 1.6028 | 32 |
| chibi_finance_2023 | 1.3509 | 0.0336 | 1.3173 | 35 |
| radiant_capital_arbitrum_2024 | 1.0896 | 0.0402 | 1.0494 | 25 |
| xkingdom_2024 | 1.0100 | 0.0580 | 0.9520 | 32 |
| qbridge_qubit_2022 | 1.5496 | 0.6030 | 0.9466 | 46 |
| feg_bridge_2024 | 1.1242 | 0.5266 | 0.5976 | 42 |
| paraluni_2022 **← paraluni_2022** | 1.6888 | 1.2201 | 0.4687 | 32 |

## Bước 2c — Feature importance/contribution trên fold `paraluni_2022`

Model M1 fit trên 11 incident khác (chính xác fold dùng trong nested eval khi `paraluni_2022` là outer test) — dự đoán trên **TOÀN BỘ tập test thật** của group này (161 dòng, mọi prefix bucket — khớp `n_val` trong nested eval, KHÔNG chỉ lọc `ratio_100`, vì RQ1 pool cả 8 bucket).

**Xác nhận PR-AUC tính lại trên 161 dòng = 0.5112** — khớp so với `main_table.csv` (0.5112), xác nhận fold tái tạo ở đây đúng với fold thật đã dùng.

**8 dòng positive** (các mốc prefix của chính trajectory `paraluni_2022`), prob dao động **[0.0005, 0.9990]** — dòng positive khó nhất là `paraluni_2022` ở mốc `k_3` (prefix_len=3), prob chỉ 0.0005.

**107/153 dòng hard-negative (mọi prefix) được model chấm điểm CAO HƠN dòng positive thấp nhất** — đây là nguyên nhân TRỰC TIẾP khiến PR-AUC còn lại ở mức 0.5112 (không phải toàn bộ hard-negative, mà là 1 số dòng CỤ THỂ ở 1 vài mốc prefix ngắn của positive + 1 số hard-negative điểm cao).

### Top 3 hard-negative (mọi prefix) chấm điểm cao nhất, vượt cả positive khó nhất

| source_id | prefix | prefix_len | M1 prob |
|---|---|---|---|
| paraluni_2022__hn013 | k_3 | 3 | 0.9701 |
| paraluni_2022__hn013 | ratio_25 | 4 | 0.9151 |
| paraluni_2022__hn002 | k_5 | 5 | 0.8895 |

### Top-5 feature đóng góp (XGBoost `pred_contribs`) — positive khó nhất vs top hard-negative điểm cao

**`paraluni_2022`** (k_3, label=1, prob=0.0005):

| Feature | Đóng góp |
|---|---|
| log_amount_mean | -3.8701 |
| prefix_ratio | +1.5580 |
| action_count_transfer_ratio | -0.9475 |
| fan_out | -0.8335 |
| inter_action_gap_mean | -0.7647 |

**`paraluni_2022__hn013`** (k_3, label=0, prob=0.9701):

| Feature | Đóng góp |
|---|---|
| log_amount_mean | +3.1891 |
| prefix_ratio | +1.5272 |
| action_count_swap_ratio | +0.5885 |
| inter_action_gap_mean | +0.5158 |
| fan_out | -0.5090 |

**`paraluni_2022__hn013`** (ratio_25, label=0, prob=0.9151):

| Feature | Đóng góp |
|---|---|
| log_amount_mean | +3.1133 |
| action_count_transfer_ratio | -0.5477 |
| active_duration_sec | +0.4865 |
| unique_counterparties | -0.4863 |
| fan_out | -0.4457 |

**`paraluni_2022__hn002`** (k_5, label=0, prob=0.8895):

| Feature | Đóng góp |
|---|---|
| prefix_ratio | +2.3232 |
| log_amount_mean | +2.1535 |
| inter_action_gap_std | -1.0122 |
| path_depth | -0.8514 |
| fan_out | +0.7682 |

## Kết luận

**Phát hiện chính (thay thế hoàn toàn kết luận Tuần 10):** `paraluni_2022` KHÔNG CÒN là ca tệ nhất — xếp hạng 2/12, PR-AUC M1 tăng từ 0.4123 (dữ liệu cũ, trajectory 38 action) lên 0.5112 (dữ liệu mới, trajectory **511 action** — tăng 13 lần). Nguyên nhân của sự cải thiện: bug `value_share` gộp-token (đã sửa 2026-08-27) trước đây loại oan phần lớn evidence swap/bridge thật của incident này — khi trajectory đầy đủ hơn, model có nhiều tín hiệu phân biệt hơn với hard-negative, PR-AUC cải thiện đáng kể mà KHÔNG cần thay đổi gì về model/feature.

**Vẫn còn khó tương đối (hạng 2/12), nguyên nhân RESIDUAL tương tự phát hiện Tuần 10** — không còn là đặc điểm TOÀN CỤC (độ dài, motif, volume band tổng thể đều KHÔNG phải outlier rõ rệt so với 11 incident khác — xem Bước 2a/2b) mà vẫn là **hành vi ở MỐC PREFIX SỚM cụ thể**: dòng positive khó nhất là `k_3` (prefix_len=3/511) có `log_amount_mean` khác biệt rõ so với các mốc dài hơn của chính nó (đóng góp SHAP -3.8701) — trong khi đúng lúc đó, hard-negative `paraluni_2022__hn013` (ở mốc `k_3`) lại có `log_amount_mean` khác dấu, khiến model xếp hạng nhầm ở giai đoạn sớm. Cùng bản chất **early-detection cụ thể** đã xác định ở Tuần 10 (mô hình phụ thuộc `log_amount_mean` ở mốc quan sát ngắn), nhưng mức độ ảnh hưởng đã giảm đáng kể (không còn khiến incident này rớt xuống hạng cuối).

**2 feature ngoại lệ đáng chú ý nhưng KHÔNG phải nguyên nhân chính** (không nằm trong top-5 SHAP của bất kỳ dòng nào phân tích ở trên): `value_retention` (4290.4 so với median 0.6742 của 11 incident khác — vẫn cao bất thường, có thể là tỷ lệ toán học phóng đại khi mẫu số gần 0) và `fan_in` (không nằm trong top-5 contribution).

**Motif vẫn KHÔNG phải nguyên nhân** — số motif=0 ở `paraluni_2022` (2/7) so với median 11 incident khác (3.0/7) — không phải outlier rõ rệt.

**Case study RQ2 (`paraluni_2022__hn013`) cần rà soát lại**: hard-negative gây nhiễu nhiều nhất trên dữ liệu MỚI có thể KHÁC với candidate đang dùng trong `results/reports/alert_case_studies_v1.md` (Tuần 7, `paraluni_2022__hn013`, dựa trên dữ liệu cũ) — nếu khác, case study đó cần cập nhật lại thành candidate mới; nếu giống, kết luận Tuần 7 vẫn còn đúng. Xem `error_analysis_v1.md`/`alert_case_studies_v1.md` đã được cập nhật ghi chú tương ứng trong cùng đợt sửa này.
