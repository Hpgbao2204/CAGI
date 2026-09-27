# RQ3 — Kiểm tra data gate (Tuần 8, Bước 1)

Tiêu chí (đúng `research_questions.md` mục RQ3): **≥1,000 action transition; mỗi next-action class ≥30 mẫu; majority class <60%.**

Định nghĩa: 1 transition = 1 cặp hành động liên tiếp `(action[i], action[i+1])` trong cùng 1 trajectory; next-action class = `event_type` của `action[i+1]`. Đếm trên **toàn bộ 627 trajectory** (15 positive + 612 negative — control gốc + hard-negative mining + hard-negative bổ sung độ phức tạp) — cùng tập trajectory mà RQ2 dùng (features_v2.parquet đã sửa bug prefix), vì next-event prediction là mô hình chuỗi hành động tổng quát, không gắn riêng nhãn positive/negative.

- Tổng trajectory: 627 (positive=15, negative=612)
- Trajectory có ≥2 action (đóng góp transition): 350
- Trajectory quá ngắn (<2 action, không có transition nào): 277

## Kết quả đếm

- **Tổng số action transition: 26723**
- Số next-action class: 7

| next_action_class | n_samples | ratio |
|---|---|---|
| transfer | 23337 | 87.33% |
| bridge_deposit | 2144 | 8.02% |
| swap | 917 | 3.43% |
| split | 250 | 0.94% |
| merge | 48 | 0.18% |
| mixer_or_exit | 23 | 0.09% |
| lending_deposit | 4 | 0.01% |

## Kiểm tra từng tiêu chí

| Tiêu chí | Ngưỡng | Giá trị thật | Đạt? |
|---|---|---|---|
| Tổng transition | ≥1000 | 26723 | ✅ ĐẠT |
| Mỗi class ≥30 mẫu | 0 class dưới ngưỡng | min=4, 2/7 class dưới ngưỡng | ❌ KHÔNG ĐẠT |
| Majority class | <60% | 'transfer' = 87.33% | ❌ KHÔNG ĐẠT |

## KẾT LUẬN: KHÔNG ĐẠT GATE — loại RQ3 khỏi paper chính thức

## So sánh với N=11 (2026-08-19)

| | N=11 (cũ) | N=15 (2026-09-04, hiện tại) |
|---|---|---|
| Tổng trajectory | 525 | 627 |
| Tổng transition | 16.617 | 26.723 |
| min class count | 2 | 4 |
| Số class dưới 30 mẫu | 3/7 | 2/7 |
| Majority class ratio | 90.26% | 87.33% |
| Kết luận gate | ❌ KHÔNG ĐẠT | ❌ KHÔNG ĐẠT |

**Kết luận KHÔNG đổi** — vẫn KHÔNG ĐẠT GATE, cả 2 tiêu chí còn lại (min
class, majority class) đều cải thiện nhẹ theo hướng tốt hơn (majority
giảm từ 90.26%→87.33%, số class dưới ngưỡng giảm 3→2/7) nhưng còn cách xa
ngưỡng đạt — bản chất phân phối lệch nặng về `transfer` không đổi khi mở
rộng dataset. Bản N=11 gốc giữ nguyên tại
`results/reports/rq3_data_gate_v1_N11_PRE_N15FREEZE_backup.md`.
