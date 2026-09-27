# RQ3 — Kiểm tra data gate (Tuần 8, Bước 1)

Tiêu chí (đúng `research_questions.md` mục RQ3): **≥1,000 action transition; mỗi next-action class ≥30 mẫu; majority class <60%.**

Định nghĩa: 1 transition = 1 cặp hành động liên tiếp `(action[i], action[i+1])` trong cùng 1 trajectory; next-action class = `event_type` của `action[i+1]`. Đếm trên **toàn bộ 525 trajectory** (11 positive + 5 control + 403 hard-negative + 106 hard-negative bổ sung độ phức tạp) — cùng tập trajectory mà RQ2 dùng (features_v2.parquet đã sửa bug prefix), vì next-event prediction là mô hình chuỗi hành động tổng quát, không gắn riêng nhãn positive/negative.

- Tổng trajectory: 525 (positive=11, negative=514)
- Trajectory có ≥2 action (đóng góp transition): 255
- Trajectory quá ngắn (<2 action, không có transition nào): 270

## Kết quả đếm

- **Tổng số action transition: 16617**
- Số next-action class: 7

| next_action_class | n_samples | ratio |
|---|---|---|
| transfer | 14999 | 90.26% |
| bridge_deposit | 1146 | 6.90% |
| swap | 366 | 2.20% |
| split | 91 | 0.55% |
| mixer_or_exit | 8 | 0.05% |
| merge | 5 | 0.03% |
| lending_deposit | 2 | 0.01% |

## Kiểm tra từng tiêu chí

| Tiêu chí | Ngưỡng | Giá trị thật | Đạt? |
|---|---|---|---|
| Tổng transition | ≥1000 | 16617 | ✅ ĐẠT |
| Mỗi class ≥30 mẫu | 0 class dưới ngưỡng | min=2, 3/7 class dưới ngưỡng | ❌ KHÔNG ĐẠT |
| Majority class | <60% | 'transfer' = 90.26% | ❌ KHÔNG ĐẠT |

## KẾT LUẬN: KHÔNG ĐẠT GATE — loại RQ3 khỏi paper chính thức
