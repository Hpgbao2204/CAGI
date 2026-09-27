# Fig. 2 — Phụ lục kỹ thuật đầy đủ
Tài liệu này chứa toàn bộ chi tiết kỹ thuật đã lược bỏ khỏi `fig2_simplified_for_slide.png` (nhãn địa chỉ, số liệu motif, danh sách action đầy đủ) để bản dùng cho slide không quá tải thông tin. Bản `fig2_technical_full.png` giữ lại các chi tiết này trực tiếp trên hình; tài liệu này bổ sung phần không thể hiện hết trên hình (bảng action đầy đủ).
## Lý do chọn case
- **Positive**: `deltaprime_arbitrum_2024` — 23 action (không đổi so với bản vẽ đầu tiên).
- **Hard-negative**: đổi từ `deltaprime_benign_control_2024` (1 action, control gốc theo incident) sang `deltaprime_arbitrum_2024__hn051` (15 action, **hard-negative đã MINE**, có trong `metadata/hard_negative_registry.csv`, cùng tiêu chí band-matched của Giai đoạn B).
- Lý do đổi: cặp gốc lệch độ dài quá lớn (23 vs 1 action) — có rủi ro vô tình minh họa đúng "shortcut về độ dài" mà dự án đã chứng minh và loại bỏ (tiêu chí fan_out band-matched, xem `results/reports/fanout_band_v3_mining_v1.md`). `deltaprime_arbitrum_2024__hn051` (15 action) gần hơn nhiều so với 23 của positive.
## Chú giải nhãn địa chỉ (áp dụng cho cả 2 trajectory)

| Mã | Địa chỉ đầy đủ | Vai trò |
|---|---|---|
| S | `0x56e7f67211683857ee31a1220827cac5cdaa634c` | seed / ví tấn công |
| A | `0xc3f3a07ae7d2a125ef81a5950c4d0dd54c740251` | hop trung gian 1 |
| B | `0x82af49447d8a07e3bd95bd0d56f35241523fbab1` | WETH contract (Arbitrum) |
| Z | `0x0000000000000000000000000000000000000000` | relay hub 1 (native ETH wrap/unwrap) |
| H | `0xea3123e9d9911199a6711321d1277285e6d4f3ec` | relay hub 2 |
| F | `0x6c411ad3e74de3e7bd422b94a27770f5b86c623b` | điểm gom cuối cùng |
| BR | `0xe35e9842fceaca96570b734083f4a58e8f7c5f2a` | Across Protocol SpokePool (bridge thật) |
| S2 | `0xd45bda83d11fda3eda0107ce9aa8856b753fc44e` | ví khác (hard-negative, không liên quan S) |

## Số liệu motif (features_v2.parquet, prefix_label=ratio_100)

| Motif feature | Positive (23 action) | Hard-negative hn051 (15 action) |
|---|---|---|
| motif_split | 3.0 | 1.0 |
| motif_merge | 3.0 | 1.0 |
| motif_bridge_then_swap | 0.0 | 0.0 |
| motif_swap_then_split | 0.0 | 0.0 |
| motif_peel_like_chain | 0.0 | 0.0 |
| motif_nested_bridge | 0.0 | 0.0 |
| motif_rapid_token_pivot | 6.0 | 0.0 |

**Lưu ý quan trọng**: `motif_split=1.0, motif_merge=1.0` của hard-negative là trường hợp **thoái hóa** (degenerate) — 1 địa chỉ lặp lại đúng 1 cạnh (seed → cùng 1 contract cầu nối) 15 lần, kỹ thuật thỏa mãn ngưỡng "≥2 cạnh" của định nghĩa `_motif_features()` nhưng KHÔNG phải mẫu "phân tán qua nhiều ví trung gian" thật như ở positive (nơi motif_split/merge=3.0 phản ánh 3 địa chỉ KHÁC NHAU mỗi địa chỉ có ≥2 cạnh, tạo thành chuỗi layering nhiều tầng thật sự). Đây là lý do bản `fig2_simplified_for_slide.png` KHÔNG tô nền vàng cho hàng hard-negative — tránh gây hiểu lầm rằng nó cũng có "mẫu đáng ngờ" như positive.

## Toàn bộ 23 action — Positive — deltaprime_arbitrum_2024

| # | Thời gian (UTC) | +Xh | Loại | Src | Dst | Token |
|---|---|---|---|---|---|---|
| 1 | 2024-11-11T08:20:58Z | +0.00h | transfer | S (`0x56e7f6...`) | A (`0xc3f3a0...`) | USDC |
| 2 | 2024-11-11T08:21:38Z | +0.01h | transfer | S (`0x56e7f6...`) | A (`0xc3f3a0...`) | USDC |
| 3 | 2024-11-11T08:25:29Z | +0.08h | transfer | S (`0x56e7f6...`) | A (`0xc3f3a0...`) | ARB |
| 4 | 2024-11-11T08:54:48Z | +0.56h | transfer | A (`0xc3f3a0...`) | B (`0x82af49...`) | ETH |
| 5 | 2024-11-11T09:01:30Z | +0.68h | swap | S (`0x56e7f6...`) | Z (`0x000000...`) | WETH |
| 6 | 2024-11-11T09:56:59Z | +1.60h | transfer | Z (`0x000000...`) | H (`0xea3123...`) | ETH |
| 7 | 2024-11-11T09:56:59Z | +1.60h | transfer | Z (`0x000000...`) | H (`0xea3123...`) | ETH |
| 8 | 2024-11-11T10:15:14Z | +1.90h | bridge_deposit | S (`0x56e7f6...`) | BR (`0xe35e98...`) | WBTC |
| 9 | 2024-11-11T13:28:01Z | +5.12h | transfer | Z (`0x000000...`) | H (`0xea3123...`) | ETH |
| 10 | 2024-11-11T13:28:01Z | +5.12h | transfer | Z (`0x000000...`) | H (`0xea3123...`) | ETH |
| 11 | 2024-11-11T13:28:01Z | +5.12h | transfer | H (`0xea3123...`) | F (`0x6c411a...`) | ETH |
| 12 | 2024-11-11T13:47:16Z | +5.44h | transfer | H (`0xea3123...`) | F (`0x6c411a...`) | ETH |
| 13 | 2024-11-11T13:47:16Z | +5.44h | transfer | Z (`0x000000...`) | H (`0xea3123...`) | ETH |
| 14 | 2024-11-11T13:47:16Z | +5.44h | transfer | Z (`0x000000...`) | H (`0xea3123...`) | ETH |
| 15 | 2024-11-11T18:22:34Z | +10.03h | transfer | Z (`0x000000...`) | H (`0xea3123...`) | ETH |
| 16 | 2024-11-11T18:22:34Z | +10.03h | transfer | Z (`0x000000...`) | H (`0xea3123...`) | ETH |
| 17 | 2024-11-11T18:22:34Z | +10.03h | transfer | H (`0xea3123...`) | F (`0x6c411a...`) | ETH |
| 18 | 2024-11-12T00:33:53Z | +16.22h | transfer | Z (`0x000000...`) | H (`0xea3123...`) | ETH |
| 19 | 2024-11-12T00:33:53Z | +16.22h | transfer | Z (`0x000000...`) | H (`0xea3123...`) | ETH |
| 20 | 2024-11-12T00:33:53Z | +16.22h | transfer | H (`0xea3123...`) | F (`0x6c411a...`) | ETH |
| 21 | 2024-11-12T02:22:40Z | +18.03h | transfer | H (`0xea3123...`) | F (`0x6c411a...`) | ETH |
| 22 | 2024-11-12T07:36:13Z | +23.25h | transfer | H (`0xea3123...`) | F (`0x6c411a...`) | ETH |
| 23 | 2024-11-12T07:36:13Z | +23.25h | transfer | Z (`0x000000...`) | H (`0xea3123...`) | ETH |

## Toàn bộ 15 action — Hard-negative — deltaprime_arbitrum_2024__hn051

| # | Thời gian (UTC) | +Xh | Loại | Src | Dst | Token |
|---|---|---|---|---|---|---|
| 1 | 2024-11-09T00:42:43+00:00 | +0.00h | bridge_deposit | S2 (`0xd45bda...`) | BR (`0xe35e98...`) | WETH |
| 2 | 2024-11-09T02:37:00+00:00 | +1.90h | bridge_deposit | S2 (`0xd45bda...`) | BR (`0xe35e98...`) | WETH |
| 3 | 2024-11-09T03:59:50+00:00 | +3.29h | bridge_deposit | S2 (`0xd45bda...`) | BR (`0xe35e98...`) | WETH |
| 4 | 2024-11-09T07:15:08+00:00 | +6.54h | bridge_deposit | S2 (`0xd45bda...`) | BR (`0xe35e98...`) | WETH |
| 5 | 2024-11-09T07:29:57+00:00 | +6.79h | bridge_deposit | S2 (`0xd45bda...`) | BR (`0xe35e98...`) | WETH |
| 6 | 2024-11-09T08:10:11+00:00 | +7.46h | bridge_deposit | S2 (`0xd45bda...`) | BR (`0xe35e98...`) | WETH |
| 7 | 2024-11-09T08:22:23+00:00 | +7.66h | bridge_deposit | S2 (`0xd45bda...`) | BR (`0xe35e98...`) | WETH |
| 8 | 2024-11-09T08:37:10+00:00 | +7.91h | bridge_deposit | S2 (`0xd45bda...`) | BR (`0xe35e98...`) | WETH |
| 9 | 2024-11-09T08:56:39+00:00 | +8.23h | bridge_deposit | S2 (`0xd45bda...`) | BR (`0xe35e98...`) | WETH |
| 10 | 2024-11-09T10:42:02+00:00 | +9.99h | bridge_deposit | S2 (`0xd45bda...`) | BR (`0xe35e98...`) | WETH |
| 11 | 2024-11-09T12:25:55+00:00 | +11.72h | bridge_deposit | S2 (`0xd45bda...`) | BR (`0xe35e98...`) | WETH |
| 12 | 2024-11-09T13:15:08+00:00 | +12.54h | bridge_deposit | S2 (`0xd45bda...`) | BR (`0xe35e98...`) | WETH |
| 13 | 2024-11-09T14:58:54+00:00 | +14.27h | bridge_deposit | S2 (`0xd45bda...`) | BR (`0xe35e98...`) | WETH |
| 14 | 2024-11-09T15:36:39+00:00 | +14.90h | bridge_deposit | S2 (`0xd45bda...`) | BR (`0xe35e98...`) | WETH |
| 15 | 2024-11-09T16:16:33+00:00 | +15.56h | bridge_deposit | S2 (`0xd45bda...`) | BR (`0xe35e98...`) | WETH |
