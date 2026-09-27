# Sửa bug `value_share` gộp-token trong `build_trajectory()` — Giai đoạn B

**Bối cảnh phát hiện:** trong lúc thêm incident mới `radiant_capital_arbitrum_2024`
(Giai đoạn B, Bước 3), seed address đã xác minh đúng (dòng tiền khớp báo cáo
công khai 100%) vẫn cho trajectory RỖNG. Debug trực tiếp `build_trajectory()`
(`CAGI_ED_DEBUG_BUILDER=1`) cho thấy giao dịch outbound 11,977 ETH thật (khớp
chính xác báo cáo công khai) bị tính `value_share = 0.24%` — dưới ngưỡng
`min_tainted_share = 0.05` — nên bị loại.

## Bug

`outflow_by_src` (mẫu số của `value_share`, `src/trajectories/builder.py`)
cộng dồn `math.expm1(abs(amount_norm))` — **RAW value** — của **MỌI token
khác nhau** mà 1 địa chỉ gửi đi (ETH + ARB + WBTC + USDC...) vào **1 mẫu số
chung**, dùng đơn vị token thô không quy đổi USD. Đây là phép cộng vô nghĩa
về mặt toán học: 11,977 "ETH" cộng với hàng trăm nghìn "ARB"/"WBTC" ở đơn vị
token thô hoàn toàn không tương thích. Vì seed của Radiant Capital có nhiều
swap ARB/WBTC/USDC nhỏ trước đó, tổng mẫu số bị đội lên ~4.98 triệu đơn vị
hỗn hợp, khiến giao dịch ETH thật — chiếm gần 100% giá trị outbound thật
theo đúng đơn vị ETH — bị pha loãng xuống 0.24%.

Đây là root cause SÂU HƠN của cùng vấn đề đã phát hiện một phần ở DeltaPrime
2026-08-13 (xem `TrajectoryConfig.allowlist` docstring) — lúc đó chỉ vá bằng
cách cho counterparty thuộc allowlist (bridge/DEX/mixer đã verify) LUÔN được
giữ bất kể `value_share`. Cách vá đó chỉ hoạt động khi counterparty là
protocol đã verify — KHÔNG giúp được trường hợp EOA-to-EOA (như chuyển ETH
giữa 2 ví attacker) vì phía nhận không nằm trong allowlist.

## Fix

`outflow_by_src` đổi thành `outflow_by_src_token: Dict[(src, token), float]`
— mẫu số tính RIÊNG theo từng `(địa chỉ, token)`, không cộng dồn qua nhiều
token khác nhau. `value_share` của 1 event giờ so với tổng outflow CÙNG
TOKEN của địa chỉ đó, không so với tổng gộp mọi token.

Xem `src/trajectories/builder.py::build_trajectory` (đoạn `outflow_by_src_token`)
và test hồi quy `tests/test_builder.py::test_value_share_computed_per_token_not_pooled_across_tokens`.

## Kiểm tra ảnh hưởng lên 17 incident/control cũ (dữ liệu cache sẵn có, KHÔNG gọi API mới)

Trước khi sửa gốc, đã dựng lại thử trên cache hiện có (không fetch thêm) để
đo phạm vi ảnh hưởng: **12/17** incident/control có thay đổi (tăng action từ
+9 đến +437), **0/17** có action nào bị MẤT (fix đơn điệu một chiều — mẫu số
per-token luôn ≤ mẫu số gộp-token cho cùng 1 event, nên value_share per-token
luôn ≥ giá trị cũ). Điều này cho thấy đây không phải rủi ro đánh đổi mà là
sửa đúng để lộ ra bằng chứng thật vốn bị che khuất.

## Rebuild đầy đủ (fetch thêm dữ liệu thật cho địa chỉ mới reachable)

Vì nhiều địa chỉ ở hop sâu hơn (trước đây không reachable do bug) chưa từng
có cache riêng, cần fetch API thật để tiếp tục truy vết đúng kiến trúc
frontier-expansion. Ước lượng ban đầu (~600-900 call) **thấp hơn thực tế
rất nhiều** — `ronin_bridge_2022` một mình đã cần ~920 call/28 phút cho 3
round đầu mà CHƯA hội tụ, do hiệu ứng cascade (địa chỉ mới lại mở ra thêm
địa chỉ mới ở hop kế). Quyết định (đã hỏi & xác nhận với người dùng):
fetch tăng dần tới `max_depth=2` cho 12 incident/control (đủ dùng vì hầu hết
evidence mới nằm gần seed), riêng `ronin_bridge_2022` (bị giảm mạnh dưới
depth=2 vì phần lớn evidence thật của nó nằm ở hop 3-6) fetch riêng tới hội
tụ đầy đủ `max_depth=6` chính thức (~517 giây, 58 địa chỉ mới cho vòng cuối).

Kết quả **số action cuối cùng, dùng pipeline chính thức `run_incident_pipeline`
(khai thác thêm cache sẵn có ngoài phạm vi depth=2 đã fetch chủ đích — không
tốn API call thêm)**:

| Incident | Trước fix | Sau fix (chính thức) | Δ |
|---|---|---|---|
| ronin_bridge_2022 | 113 | 1,625 | +1,512 |
| ronin_benign_control_2022 | 18 | 103 | +85 |
| qbridge_qubit_2022 | 52 | 698 | +646 |
| bsc_token_hub_2022 | 74 | 362 | +288 |
| chibi_finance_2023 | 16 | 40 | +24 |
| wooppv2_2024 | 6 | 16 | +10 |
| utopiasphere_2024 | 17 | 37 | +20 |
| xkingdom_2024 | 13 | 73 | +60 |
| wault_finance_2021 | 35 | 190 | +155 |
| paraluni_2022 | 38 | 511 | +473 |
| circulate_2023 | 5 | 25 | +20 |
| deltaprime_arbitrum_2024 | 5 | 23 | +18 |
| **radiant_capital_arbitrum_2024** | 0 (rỗng — chặn bởi bug) | **248** | **incident mới hoạt động** |

## QA leakage sau rebuild

Trajectory lớn hơn nhiều → chạm nhiều địa chỉ hạ tầng dùng chung hơn (PancakePair
pool, DODOV2Proxy, WETH, FlashWallet của 0x Protocol...). Đã xác nhận TỪNG địa
chỉ mới trùng giữa 2+ group qua `eth_getCode` (đều là CONTRACT, không EOA) +
`getsourcecode` thật trước khi thêm vào danh sách loại trừ của
`test_real_full_dataset_no_group_leakage_across_all_groups` (22 địa chỉ tổng
cộng, xem chi tiết trong docstring/comment của test). Không phát hiện EOA
nào bị trùng thật giữa các group — leakage test PASS sau khi loại trừ hạ tầng
dùng chung.

## Golden fixture & test

Regen 12 golden fixture cũ + tạo mới `radiant_capital_arbitrum_2024_events.golden.json`
qua `run_incident_pipeline(..., do_collect=False, write_output=False)`. Cập
nhật 3 assertion cứng lỗi thời (`utopiasphere_2024`: 11→20 bridge_deposit,
`xkingdom_2024`: 1→20 bridge_deposit, `paraluni_2022`: 3→76 swap). Thêm
`test_regression_radiant_capital_arbitrum_2024_matches_golden` (khóa 248
action + xác nhận 2 chặng chuyển ETH lớn khớp báo cáo công khai). **194/194
test PASS.**

## Việc CÒN LẠI (chưa làm trong bước này)

- Rebuild `features_v2.parquet` + rerun RQ1/RQ2/ablation trên dataset mới
  (12 incident cũ với trajectory lớn hơn nhiều + `radiant_capital_arbitrum_2024`
  mới) — trajectory thay đổi RẤT LỚN ở nhiều incident (vd paraluni_2022
  38→511) nên gần như chắc chắn ảnh hưởng đáng kể tới feature/kết quả.
- Viết lại `paraluni_2022_reinvestigation.md` — kết luận cũ dựa trên
  trajectory 38 action nay đã lỗi thời (511 action thật).
- Hoàn tất Giai đoạn B Bước 3 (mở rộng thêm incident, target 15) và Bước
  4-6 (probe benign fan-out, QA leakage cuối, freeze version, retrain).
