# Error analysis — M1 (Tuần 6)

## Xếp hạng per-incident (PR-AUC, TỆ → TỐT, theo M1)

| Incident | M1 | B3 | B2 | n_val | n_positive | Ghi chú |
|---|---|---|---|---|---|---|
| paraluni_2022 | 0.4123 | 0.4252 | 0.0443 | 154 | 8 | Giới hạn BSCTrace pagination (xem dataset_card.md) |
| deltaprime_arbitrum_2024 | 0.5016 | 0.6237 | 0.0469 | 155 | 4 |  |
| feg_bridge_2024 | 0.5432 | 0.8262 | 0.1064 | 50 | 5 |  |
| bsc_token_hub_2022 | 0.6508 | 0.5760 | 0.6581 | 170 | 8 |  |
| wault_finance_2021 | 0.7093 | 0.7698 | 0.0347 | 164 | 8 | Giới hạn BSCTrace pagination (xem dataset_card.md) |
| ronin_bridge_2022 | 0.8644 | 0.8420 | 0.4901 | 122 | 8 |  |
| chibi_finance_2023 | 1.0000 | 1.0000 | 0.7568 | 70 | 8 |  |
| qbridge_qubit_2022 | 1.0000 | 0.6899 | 0.0412 | 225 | 8 |  |
| utopiasphere_2024 | 1.0000 | 1.0000 | 0.2273 | 69 | 7 |  |
| wooppv2_2024 | 1.0000 | 1.0000 | 0.3715 | 57 | 4 |  |
| xkingdom_2024 | 1.0000 | 1.0000 | 0.9286 | 68 | 7 |  |

## 3 incident M1 dự đoán TỆ nhất

**['paraluni_2022', 'deltaprime_arbitrum_2024', 'feg_bridge_2024']**

- `paraluni_2022` (PR-AUC=0.4123) — TỆ NHẤT ở CẢ 3 model (B2=0.0443, B3=0.4252, M1=0.4123) — không cải thiện đáng kể khi chuyển sang feature/model phức tạp hơn. Đây là 1 trong 2 incident được flag từ Tuần 5 (địa chỉ gần trần phân trang BSCTrace, xem `data/dataset_card.md` mục Giới hạn) — khả năng cao độ khó này đến từ ĐẶC ĐIỂM DỮ LIỆU (hard-negative của group này có thể có cấu trúc gần giống positive hơn các group khác), không phải lỗi model.
- `deltaprime_arbitrum_2024` (PR-AUC=0.5016) — incident có positive trajectory NGẮN NHẤT (5 action) trong 11 incident — ít tín hiệu temporal/motif để phân biệt, hợp lý là khó nhất về mặt thống kê (không phải giới hạn dữ liệu đã biết, mà là đặc điểm THẬT của vụ này).
- `feg_bridge_2024` (PR-AUC=0.5432) — toàn bộ 9 action đều cùng loại `mixer_or_exit` (Tornado Cash) — motif đơn điệu (không có bridge->swap->split đa dạng), có thể khiến M1 khó tách biệt so với hard-negative cũng tương tác mixer.

## Trả lời câu hỏi cụ thể: wault_finance_2021/paraluni_2022 còn là 2 fold yếu nhất với M1 không?

**KHÔNG hoàn toàn — có cải thiện rõ rệt cho `wault_finance_2021`, nhưng `paraluni_2022` vẫn là fold TỆ NHẤT xuyên suốt cả 3 model:**

| Incident | Xếp hạng ở B2 (1=tệ nhất/11) | Xếp hạng ở M1 (1=tệ nhất/11) |
|---|---|---|
| wault_finance_2021 | 1/11 | 5/11 |
| paraluni_2022 | 3/11 | 1/11 |

- `wault_finance_2021`: TỆ NHẤT ở B2 (hạng 1/11, PR-AUC=0.0347) → cải thiện lên hạng 5/11 ở M1 (PR-AUC=0.7093, mid-range) — KHÔNG còn là điểm yếu nhất, giới hạn pagination BSCTrace không cản trở M1 học được tín hiệu hữu ích khi dùng đủ feature.
- `paraluni_2022`: hạng 3/11 ở B2 → hạng 1/11 ở M1 — **VẪN TỆ NHẤT**, không cải thiện thứ hạng dù PR-AUC tuyệt đối tăng (0.0443→0.4123). Đáng chú ý theo dõi thêm ở Tuần 7 — có thể phản ánh đặc điểm hard-negative của group này (gần giống positive hơn), không hẳn do giới hạn dữ liệu.

## Lưu ý về các fold đạt PR-AUC = 1.0 (5/11 incident, cả B3 lẫn M1)

['chibi_finance_2023', 'qbridge_qubit_2022', 'utopiasphere_2024', 'wooppv2_2024', 'xkingdom_2024']

**Không nên đọc là "model gần như hoàn hảo"** — các fold này có n_val nhỏ (57-70 dòng, 4-8 positive), PR-AUC=1.0 đạt được khi model xếp hạng ĐÚNG toàn bộ vài dòng positive lên trên toàn bộ negative trong 1 tập nhỏ — dễ đạt hơn nhiều so với PR-AUC=1.0 trên tập lớn. CẢ B3 (untyped) VÀ M1 (typed) đều đạt 1.0 ở CÙNG 4 incident (chibi_finance_2023, utopiasphere_2024, wooppv2_2024, xkingdom_2024) — càng củng cố kết luận RQ1 (không đủ bằng chứng phân biệt typed vs untyped): ở các fold "dễ", CẢ HAI cách tiếp cận đều đủ tốt; ở các fold "khó" (paraluni_2022, deltaprime_arbitrum_2024), CẢ HAI đều gặp khó khăn tương tự.

## Kết luận
M1 không có sai số hệ thống rõ ràng gắn với "loại incident" — điểm yếu nhất (`paraluni_2022`) nhất quán ở CẢ 3 model (B2/B3/M1), gợi ý đây là đặc điểm CỦA DỮ LIỆU incident đó (hard-negative khó phân biệt), không phải model cụ thể nào thất bại. Điều này phù hợp với kết luận RQ1 (`rq1_answer.md`): typed semantics (M1) không cho lợi thế rõ ràng so với untyped (B3) trên mẫu 11 incident hiện tại.
