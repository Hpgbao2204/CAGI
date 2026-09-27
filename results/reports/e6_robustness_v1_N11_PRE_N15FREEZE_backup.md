# E6 — Robustness: hard-negative đã match vs "unmatched negative"

**Gọi đúng tên "unmatched negative"** (không phải "random" tuyệt đối) — các candidate này vẫn đã tương tác với contract trong allowlist, chỉ không khớp tiêu chí cấu trúc/volume (`_passes_structural_filter`: fan_out≤3, không mixer bất thường, volume>0, tương tác trực tiếp). Nguồn: 505 candidate bị reject đã có sẵn cache (Bước 0, `e6_gate_v1.md`) — dùng được 460/485 (còn lại trajectory rỗng khi build lại).

- Số group có positive trong tập unmatched: 11/11

## Kết quả

| Eval set | Mean PR-AUC | 95% CI | n incident |
|---|---|---|---|
| matched_hard_negative | 0.7190 | [0.5319, 0.8834] | 11 |
| unmatched_negative | 0.5496 | [0.2962, 0.8350] | 11 |

**Paired diff (unmatched - matched) = -0.1343, 95% bootstrap CI = [-0.2535, -0.0270], Wilcoxon p=0.025390625**

## Diễn giải

**NGƯỢC kỳ vọng ban đầu (PR-AUC unmatched THẤP HƠN matched) — đã điều tra, KHÔNG phải bug:** lý do reject chiếm đa số trong pool unmatched-negative là `fan_out_split_like_pattern` (`unique_dst > 3`, xem `_passes_structural_filter`). Khi build lại trajectory đầy đủ, so sánh đặc trưng cấu trúc thật:

| | fan_out mean | fan_out median | fan_out max |
|---|---|---|---|
| Matched hard-negative (n=509) | 1.29 | 1 | 3 |
| Unmatched negative (n=460) | 2.66 | 2 | 144 |

Matched hard-negative bị chặn ở fan_out≤3 gần như tuyệt đối (đúng tiêu chí mining) — trong khi unmatched-negative có đuôi phân phối dài hơn hẳn. Đây **chính là** loại hành vi "phân tán/split" (fan-out cao) mà motif/structural feature của M1 được thiết kế để coi là dấu hiệu đáng ngờ (rửa tiền thường phân tán qua nhiều địa chỉ). Vì vậy pool "unmatched negative" — dù bị loại vì KHÔNG khớp tiêu chí mining — lại vô tình bị lệch về phía các địa chỉ CÓ hành vi cấu trúc GIỐNG dấu hiệu rửa tiền hơn matched hard-negative, khiến M1 khó phân biệt hơn (không phải dễ hơn như kỳ vọng ban đầu).

**Kết luận đã điều chỉnh:** kết quả này KHÔNG chứng minh "hard-negative mining là bước thừa", nhưng cũng KHÔNG phải bug — nó cho thấy tiêu chí `fan_out≤3` trong mining đang lọc bỏ đúng một nhóm địa chỉ có fan-out cao (có thể benign hoặc đáng ngờ chưa xác nhận) khỏi tập hard-negative, khiến tập hard-negative hiện tại "sạch"/đồng nhất hơn (fan-out thấp), còn tập bị loại lại KHÓ HƠN thực sự đối với M1. Đây là hạn chế đáng ghi nhận của tiêu chí mining hiện tại (chưa test được M1 trên entity fan-out cao NHƯNG benign) — xem thêm `results/reports/high_fanout_benign_probe.md` và `data/dataset_card.md` mục Giới hạn #12.
