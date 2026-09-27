# Mining bổ sung theo band `fan_out` mới (Giai đoạn B, Bước 2)

**Đã xác nhận TRƯỚC khi chạy** (không suy đoán, hỏi người dùng xác nhận cách tiến hành): với 11 incident hiện có, `positive_fan_out` cao nhất = 4 (`bsc_token_hub_2022`) — `compute_max_fan_out(4) = 3` (làm tròn) = **giống hệt ngưỡng cũ**. Kỳ vọng: 0 candidate mới pass. Script này CHẠY THẬT để xác nhận bằng code.

## fan_out của từng positive + max_fan_out mới tính được

| Incident | positive_fan_out | max_fan_out (mới) | Ngưỡng cũ |
|---|---|---|---|
| bsc_token_hub_2022 | 4 | 3 | 3 |
| qbridge_qubit_2022 | 3 | 3 | 3 |
| chibi_finance_2023 | 3 | 3 | 3 |
| utopiasphere_2024 | 3 | 3 | 3 |
| paraluni_2022 | 3 | 3 | 3 |
| ronin_bridge_2022 | 2 | 3 | 3 |
| deltaprime_arbitrum_2024 | 2 | 3 | 3 |
| wooppv2_2024 | 2 | 3 | 3 |
| xkingdom_2024 | 2 | 3 | 3 |
| wault_finance_2021 | 2 | 3 | 3 |
| feg_bridge_2024 | 1 | 3 | 3 |

## Kết quả kiểm tra lại 505 candidate đã cache (E6, Tuần 9)

| Incident | Chain | max_fan_out mới | Checkable | Pass ngưỡng cũ | Pass ngưỡng mới | Mới pass thêm |
|---|---|---|---|---|---|---|
| ronin_bridge_2022 | eth | 3 | 32 | 9 | 9 | 0 |
| ronin_bridge_2022 | eth | 3 | 0 | 0 | 0 | 0 |
| ronin_bridge_2022 | eth | 3 | 0 | 0 | 0 | 0 |
| qbridge_qubit_2022 | bsc | 3 | 87 | 1 | 1 | 0 |
| feg_bridge_2024 | eth | 3 | 92 | 1 | 1 | 0 |
| deltaprime_arbitrum_2024 | arbitrum | 3 | 56 | 0 | 0 | 0 |
| bsc_token_hub_2022 | bsc | 3 | 45 | 4 | 4 | 0 |
| chibi_finance_2023 | arbitrum | 3 | 10 | 0 | 0 | 0 |
| wooppv2_2024 | arbitrum | 3 | 9 | 5 | 5 | 0 |
| utopiasphere_2024 | bsc | 3 | 18 | 0 | 0 | 0 |
| xkingdom_2024 | arbitrum | 3 | 3 | 1 | 1 | 0 |
| wault_finance_2021 | bsc | 3 | 0 | 0 | 0 | 0 |
| wault_finance_2021 | bsc | 3 | 88 | 0 | 0 | 0 |
| paraluni_2022 | bsc | 3 | 87 | 1 | 1 | 0 |

**Tổng candidate mới pass nhờ tiêu chí fan_out đã nới: 0.**

**XÁC NHẬN ĐÚNG DỰ ĐOÁN: 0 candidate mới** — vì `max_fan_out` tính được cho CẢ 11/11 incident hiện có đều bằng 3 (giống hệt ngưỡng cũ, do `positive_fan_out` cao nhất chỉ là 4 và bị làm tròn về 3). Đây KHÔNG phải lỗi của công thức `compute_max_fan_out()` — công thức hoạt động đúng như thiết kế (band tương đối, không nới lỏng vô điều kiện) — chỉ là **tập 11 incident hiện tại chưa có incident nào với positive fan_out đủ cao** để band mới phát huy tác dụng. Payoff thật của tiêu chí này phụ thuộc vào Bước 3 (mở rộng incident mới) — nếu incident mới có positive fan_out cao hơn hẳn (vd >10), band sẽ nới đáng kể và supplemental mining lúc đó mới có ý nghĩa. **Không mine bổ sung gì thêm ở bước này (0 candidate hợp lệ) — chuyển sang Bước 3.**
