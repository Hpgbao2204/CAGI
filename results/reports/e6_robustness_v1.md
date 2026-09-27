# E6 — Robustness: hard-negative đã match vs "unmatched negative"

**Cập nhật 2026-09-04 (rerun N=15, M1 không bridge_context)** — xem mục
"⚠️ Thay đổi kết luận so với N=11" ở cuối file. Bản N=11 gốc (2026-08-19)
được giữ nguyên tại
`results/reports/e6_robustness_v1_N11_PRE_N15FREEZE_backup.md` để đối chiếu.

**Gọi đúng tên "unmatched negative"** (không phải "random" tuyệt đối) — các candidate này vẫn đã tương tác với contract trong allowlist, chỉ không khớp tiêu chí cấu trúc/volume (`_passes_structural_filter`: fan_out≤3, không mixer bất thường, volume>0, tương tác trực tiếp). Nguồn: 505 candidate bị reject đã có sẵn cache (Bước 0, `e6_gate_v1.md`) — dùng được 591/616 (còn lại trajectory rỗng khi build lại).

- Số group có positive trong tập unmatched: 15/15

## Kết quả

| Eval set | Mean PR-AUC | 95% CI | n incident |
|---|---|---|---|
| matched_hard_negative | 0.6624 | [0.5234, 0.8864] | 15 |
| unmatched_negative | 0.5363 | [0.3428, 0.7902] | 15 |

**Paired diff (unmatched - matched) = -0.1147, 95% bootstrap CI = [-0.2983, +0.0633], Wilcoxon p=0.2860033840207056**

## Diễn giải

**NGƯỢC kỳ vọng ban đầu (PR-AUC unmatched THẤP HƠN matched) — đã điều tra, KHÔNG phải bug:** lý do reject chiếm đa số trong pool unmatched-negative là `fan_out_split_like_pattern` (`unique_dst > 3`, xem `_passes_structural_filter`). Khi build lại trajectory đầy đủ, so sánh đặc trưng cấu trúc thật:

| | fan_out mean | fan_out median | fan_out max |
|---|---|---|---|
| Matched hard-negative (n=607) | 1.42 | 1 | 5 |
| Unmatched negative (n=591) | 6.54 | 3 | 247 |

Matched hard-negative bị chặn ở fan_out≤3 gần như tuyệt đối (đúng tiêu chí mining) — trong khi unmatched-negative có đuôi phân phối dài hơn hẳn. Đây **chính là** loại hành vi "phân tán/split" (fan-out cao) mà motif/structural feature của M1 được thiết kế để coi là dấu hiệu đáng ngờ (rửa tiền thường phân tán qua nhiều địa chỉ). Vì vậy pool "unmatched negative" — dù bị loại vì KHÔNG khớp tiêu chí mining — lại vô tình bị lệch về phía các địa chỉ CÓ hành vi cấu trúc GIỐNG dấu hiệu rửa tiền hơn matched hard-negative, khiến M1 khó phân biệt hơn (không phải dễ hơn như kỳ vọng ban đầu).

**Kết luận đã điều chỉnh:** kết quả này KHÔNG chứng minh "hard-negative mining là bước thừa", nhưng cũng KHÔNG phải bug — nó cho thấy tiêu chí `fan_out≤3` trong mining đang lọc bỏ đúng một nhóm địa chỉ có fan-out cao (có thể benign hoặc đáng ngờ chưa xác nhận) khỏi tập hard-negative, khiến tập hard-negative hiện tại "sạch"/đồng nhất hơn (fan-out thấp), còn tập bị loại lại KHÓ HƠN thực sự đối với M1. Đây là hạn chế đáng ghi nhận của tiêu chí mining hiện tại (chưa test được M1 trên entity fan-out cao NHƯNG benign) — xem thêm `results/reports/high_fanout_benign_probe.md` và `data/dataset_card.md` mục Giới hạn #12.

## ⚠️ Thay đổi kết luận so với N=11 (2026-08-19)

| | N=11 (2026-08-19) | N=15 (2026-09-04, hiện tại) |
|---|---|---|
| Mean PR-AUC matched | 0.7190 [0.5319, 0.8834] | 0.6624 [0.5234, 0.8864] |
| Mean PR-AUC unmatched | 0.5496 [0.2962, 0.8350] | 0.5363 [0.3428, 0.7902] |
| Paired diff (unmatched−matched) | −0.1343 | −0.1147 |
| 95% CI hiệu số | [−0.2535, −0.0270] (KHÔNG chứa 0) | [−0.2983, +0.0633] (**CHỨA 0**) |
| Wilcoxon p | 0.0254 | 0.2860 |
| Ý nghĩa thống kê | **CÓ** (unmatched khó hơn matched, có ý nghĩa) | **KHÔNG ĐỦ BẰNG CHỨNG** |

**Kết luận ĐỊNH TÍNH không đổi** (chiều hiệu số vẫn âm — unmatched-negative
vẫn khó hơn matched hard-negative đối với M1, cùng cơ chế fan_out cao đã
diễn giải ở trên), nhưng **Ý NGHĨA THỐNG KÊ đã đổi**: từ "có ý nghĩa" (N=11)
sang "không đủ bằng chứng" (N=15). Nguyên nhân nhiều khả năng là biến động
CI tự nhiên khi mẫu tăng (15 incident, phân phối per-incident PR-AUC rộng
hơn — CI unmatched nới ra cả 2 phía) kết hợp với M1 bản mới (không
bridge_context) có PR-AUC matched thấp hơn bản cũ (0.6624 vs 0.7190) khiến
khoảng cách giữa 2 tập thu hẹp lại. Đây KHÔNG làm thay đổi kết luận diễn
giải cốt lõi (hạn chế kiến trúc mining `fan_out≤3` chưa test được M1 trên
entity fan-out cao benign) — chỉ làm giảm độ chắc chắn thống kê của bằng
chứng, cần ghi rõ trong Discussion nếu dùng con số này.
