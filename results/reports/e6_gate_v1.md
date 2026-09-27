# E6 (Tuần 9, Bước 0) — Xác nhận nguồn "unmatched negative"

**Câu hỏi:** dữ liệu candidate bị `_passes_structural_filter` loại có sẵn
trong cache (`data/raw/`) từ mining trước đây, hay cần fetch mới?

**Cách kiểm tra:** đọc lại toàn bộ candidate của 11 incident qua
`fetch_contract_counterparties(..., do_collect=False)` (chỉ đọc cache), trừ
đi các địa chỉ đã MATCHED (403+106 hard-negative hiện tại, 546 địa chỉ
distinct) và excluded (seed/malicious biết trước). Với phần còn lại, chỉ
những địa chỉ **có thư mục cache `data/raw/{chain}/{addr}/{incident_id}/`**
(bằng chứng đã từng được fetch khi checked trong 1 lần mining trước) mới
được đưa vào `_passes_structural_filter` (base filter, `min_candidate_events=1`
— không áp thêm tiêu chí độ phức tạp riêng của vòng mine bổ sung Tuần 5).

## Kết quả

| | Số lượng |
|---|---|
| Candidate đã MATCHED (hard-negative hiện tại) | 546 địa chỉ |
| Candidate **có cache, kiểm tra được ngay** | 527 |
| → PASS filter (không dùng — đã có trong matched hoặc trùng tiêu chí) | 22 |
| → **FAIL filter (= pool "unmatched negative" khả dụng cho E6)** | **505** |
| Candidate **CHƯA có cache** (cần fetch mới nếu muốn dùng) | 5,646 |

Breakdown lý do reject (505 candidate, tổng hợp `results/tables/e6_gate_check.csv`):
chủ yếu `fan_out_split_like_pattern` (~415), `no_direct_interaction_with_contract`
(~18), `zero_volume` (~19), `unexpected_mixer_followup`/`multiple_mixer_events_unusual`
(~83). **Không có candidate nào bị reject vì `no_events_in_window`** (rỗng) —
nghĩa là pool 505 này KHÔNG chứa trajectory rỗng/tầm thường một cách giả
tạo, mỗi candidate đều có hoạt động thật, chỉ không khớp tiêu chí cấu trúc
(fan-out, volume, mixer, tương tác trực tiếp).

Phân bố theo incident (candidate rejected, có cache — số ít nhất):
`xkingdom_2024`=2, `wooppv2_2024`=4 (khá mỏng), còn lại 18-91/incident.

## KẾT LUẬN

**KHÔNG CẦN gọi API mới** — 505 candidate rejected đã có sẵn cache, đủ
dùng làm pool "unmatched negative" cho E6 (so với 509 matched hard-negative
hiện tại, quy mô tương đương). `wooppv2_2024` (4) và `xkingdom_2024` (2)
hơi mỏng — sẽ dùng TOÀN BỘ candidate sẵn có của 2 incident này (không hạ
tiêu chí để "moi" thêm), báo cáo rõ số lượng nhỏ này trong bảng E6 thay vì
che giấu.

Chi tiết đầy đủ theo từng incident/contract: `results/tables/e6_gate_check.csv`
(tái tạo qua `scripts/check_e6_unmatched_negative_gate.py`, chỉ đọc cache
local, không gọi API on-chain).
