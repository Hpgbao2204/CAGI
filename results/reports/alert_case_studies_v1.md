# Alert explanation — 2 case study cụ thể (Tuần 7, Bước 6)

> **Ghi chú 2026-08-27:** sau khi sửa bug `value_share` gộp-token (dataset
> 12-incident mới, xem `results/reports/value_share_unit_mix_fix_v1.md` và
> `results/reports/paraluni_2022_reinvestigation.md`), đã xác nhận LẠI
> `paraluni_2022__hn013` (Case 2 dưới đây) **VẪN LÀ** hard-negative gây
> nhiễu nhiều nhất trên fold `paraluni_2022` — case study này còn đúng.
> Các con số xác suất/SHAP cụ thể bên dưới là từ dataset CŨ, có thể lệch nhẹ
> so với dataset mới nhưng kết luận định tính không đổi.

Giải thích bằng XGBoost `pred_contribs` (SHAP-like, xấp xỉ chính xác Shapley value cho tree ensemble) — tính trên MODEL CỦA ĐÚNG FOLD đã sinh ra xác suất out-of-fold tương ứng (không dùng model cuối cùng train-trên-toàn-bộ, tránh leak).

## Case 1 — True Positive, phát hiện SỚM (qbridge_qubit_2022)

- **Incident/candidate:** `qbridge_qubit_2022` (group `qbridge_qubit_2022`, label thật = 1)
- **Prefix:** `ratio_25` — 13/52 action
- **Xác suất model (fold held-out=qbridge_qubit_2022):** 0.9981 (threshold fold này = 0.9594 → VƯỢT threshold, alert được kích hoạt)

**Top-3 motif đóng góp (|SHAP-like value|, XGBoost pred_contribs):**

| Motif feature | Giá trị feature | Đóng góp |
|---|---|---|
| motif_merge | 3.0000 | +2.3773 |
| motif_rapid_token_pivot | 10.0000 | +1.9670 |
| motif_split | 1.0000 | +0.0000 |

**Top-5 feature đóng góp (toàn bộ, không chỉ motif):**

| Feature | Giá trị feature | Đóng góp |
|---|---|---|
| motif_merge | 3.0000 | +2.3773 |
| motif_rapid_token_pivot | 10.0000 | +1.9670 |
| log_amount_mean | 2.5471 | +1.3838 |
| action_count_swap_ratio | 0.3077 | +0.4841 |
| burstiness | 0.0091 | -0.3264 |

(bias term = -0.0811)

**13 action trong prefix (tx_hash link):**

- `2022-01-28T20:42:29Z` transfer 0xd01ae1a7…→0x10ed43c7… BNB (amount_norm=7.873) — tx [`0x8fb8e297bd83ab…`](https://bscscan.com/tx/0x8fb8e297bd83ab982a3fc0228386556fee0ad69fefaca037880eb45f403d2684)
- `2022-01-28T20:51:11Z` transfer 0xd01ae1a7…→0x10ed43c7… BNB (amount_norm=9.261) — tx [`0x98f5bee2fdf521…`](https://bscscan.com/tx/0x98f5bee2fdf52185dc62088993d64dd9256431f097462bcbaea3ffd7af2eaf52)
- `2022-01-28T20:53:29Z` swap 0xd01ae1a7…→0x160caed0… BUSD (amount_norm=15.202) — tx [`0x5edda1efafa800…`](https://bscscan.com/tx/0x5edda1efafa800aef14af80316041fdebf505d95791df0e56fe94c8da1dffb02)
- `2022-01-28T20:56:41Z` transfer 0xd01ae1a7…→0xdd90e5e8… USDC (amount_norm=14.914) — tx [`0x327d8f6bcbc13f…`](https://bscscan.com/tx/0x327d8f6bcbc13f2e1f6d274f5f9b099313fdaf43e55ae493187e5e4f8d040775)
- `2022-01-28T21:13:50Z` transfer 0xd01ae1a7…→0x10ed43c7… BNB (amount_norm=8.973) — tx [`0xdf0d223773fdfd…`](https://bscscan.com/tx/0xdf0d223773fdfde1fa3d72c152ce93629e24328bc9069ff7e5890cb19aa3639b)
- `2022-01-28T21:14:53Z` swap 0xd01ae1a7…→0x160caed0… BUSD (amount_norm=14.914) — tx [`0x18dffce08e7bd5…`](https://bscscan.com/tx/0x18dffce08e7bd500b97112db812fa7916062ebc11f97f3936e04fc7a41a001ca)
- `2022-01-28T21:15:56Z` transfer 0xd01ae1a7…→0xdd90e5e8… USDC (amount_norm=14.914) — tx [`0x0744f03f5d8160…`](https://bscscan.com/tx/0x0744f03f5d816024ca3cc14013d7a9f2b3a332e94c402eddca476fdcdda5cf42)
- `2022-01-28T21:23:20Z` transfer 0xd01ae1a7…→0x10ed43c7… BNB (amount_norm=8.972) — tx [`0x403561921c815d…`](https://bscscan.com/tx/0x403561921c815da50cfc8cdc30442c84772f69fd215e6f704a4e5db43be590c6)
- `2022-01-28T21:24:17Z` swap 0xd01ae1a7…→0x160caed0… BUSD (amount_norm=14.914) — tx [`0xd747ccbb12ea36…`](https://bscscan.com/tx/0xd747ccbb12ea36ced45f3269c0d8019091d34786c4978097064c9f665c37dc12)
- `2022-01-28T21:28:56Z` swap 0xd01ae1a7…→0x160caed0… USDC (amount_norm=14.955) — tx [`0x254fcdffb3a838…`](https://bscscan.com/tx/0x254fcdffb3a838ffe01811438f915e528fb3b0ea0834e5066270cc88a13ebaa9)
- `2022-01-28T21:30:17Z` transfer 0xd01ae1a7…→0xdd90e5e8… USDT (amount_norm=14.954) — tx [`0x2501cbd3450582…`](https://bscscan.com/tx/0x2501cbd3450582829ba789b4fef06a5263d031dc161b04187c1aedf0d0bf6b03)
- `2022-01-28T21:45:26Z` transfer 0xd01ae1a7…→0x10ed43c7… BNB (amount_norm=9.009) — tx [`0xc620646dcc13d9…`](https://bscscan.com/tx/0xc620646dcc13d940dc9d086c9159e619fdcc0b17aecd835ad300fe31f51303f0)
- `2022-01-28T21:46:35Z` transfer 0xd01ae1a7…→0x10ed43c7… BNB (amount_norm=9.016) — tx [`0x46677ad8ad2a89…`](https://bscscan.com/tx/0x46677ad8ad2a89e39baa20c76db68cc6cf3fcd8ce235d3309edfde0bcb4b24c7)

---

## Case 2 — False Positive (paraluni_2022__hn013)

- **Incident/candidate:** `paraluni_2022__hn013` (group `paraluni_2022`, label thật = 0)
- **Prefix:** `ratio_50` — 5/9 action
- **Xác suất model (fold held-out=paraluni_2022):** 0.9700 (threshold fold này = 0.3517 → VƯỢT threshold, alert được kích hoạt)

> **Nguyên nhân đã điều tra kỹ (Tuần 10)**: candidate này chính là hard-negative gây nhiễu nhiều nhất trong toàn bộ đánh giá per-incident của `paraluni_2022` (incident khó nhất xuyên suốt B2/B3/M1) — xem `results/reports/paraluni_2022_reinvestigation.md`. Nguyên nhân KHÔNG phải đặc điểm tổng thể (độ dài/motif/volume band của toàn incident đều bình thường so với 10 incident khác), mà là `log_amount_mean` của CHÍNH candidate này ở prefix ngắn tương đối cao (đóng góp SHAP dương lớn, xem bảng dưới), khiến model tự tin nhầm ở giai đoạn quan sát sớm — trùng khớp với `log_amount_mean` thấp bất thường ở prefix ngắn của chính positive `paraluni_2022`, làm 2 tín hiệu "đối lập nhau" bị model xếp hạng sai.

**Top-3 motif đóng góp (|SHAP-like value|, XGBoost pred_contribs):**

| Motif feature | Giá trị feature | Đóng góp |
|---|---|---|
| motif_split | 1.0000 | +0.0000 |
| motif_merge | 1.0000 | +0.0000 |
| motif_peel_like_chain | 0.0000 | +0.0000 |

**Top-5 feature đóng góp (toàn bộ, không chỉ motif):**

| Feature | Giá trị feature | Đóng góp |
|---|---|---|
| num_distinct_trigrams | 1.0000 | +2.8801 |
| log_amount_mean | 2.7649 | +1.6330 |
| burstiness | -0.0655 | -1.3385 |
| unique_counterparties | 1.0000 | -1.1070 |
| active_duration_sec | 576.0000 | +0.5730 |

(bias term = -0.1003)

**5 action trong prefix (tx_hash link):**

- `2022-03-05T17:11:11Z` transfer 0xc50bbe06…→0xcba3a516… CATGIRL (amount_norm=15.173) — tx [`0x39f050b9a7d766…`](https://bscscan.com/tx/0x39f050b9a7d7667495a458e56779f54d3a7552891f075c3ed0e0c4dfb7059a84)
- `2022-03-05T17:11:29Z` transfer 0xc50bbe06…→0xcba3a516… CATGIRL (amount_norm=15.372) — tx [`0xa6bcc990476934…`](https://bscscan.com/tx/0xa6bcc99047693405008b24c3fe1455aaf67f20a44c2327d8af9b1ddd5266a668)
- `2022-03-05T17:15:47Z` transfer 0xcba3a516…→0xc50bbe06… CATGIRL (amount_norm=13.866) — tx [`0xd6765b1d2df54e…`](https://bscscan.com/tx/0xd6765b1d2df54eb03ce947f8b19e5c4ffa413919fb620432972454e4152b61d0)
- `2022-03-05T17:20:29Z` transfer 0xc50bbe06…→0xcba3a516… CATGIRL (amount_norm=15.104) — tx [`0x3df20e396322df…`](https://bscscan.com/tx/0x3df20e396322df43579ccdacd97205be95eb47ab751bfc0bd05c13275792e209)
- `2022-03-05T17:20:47Z` transfer 0xc50bbe06…→0xcba3a516… CATGIRL (amount_norm=14.916) — tx [`0xdf6d53284c8ff0…`](https://bscscan.com/tx/0xdf6d53284c8ff00ba5e070bcc0a965f91e356a591a029f214da41075477dee5b)
