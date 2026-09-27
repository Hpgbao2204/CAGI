# Mining hard-negative cho `radiant_capital_arbitrum_2024` (Giai đoạn B, Bước 2 revisit)

## Tiêu chí sử dụng

Dùng ĐÚNG tiêu chí đã sửa ở Bước 1 (band `fan_out` tương đối qua
`compute_max_fan_out()`, xem `src/trajectories/builder.py` và
`results/reports/value_share_unit_mix_fix_v1.md`) + tiêu chí độ phức tạp có
sẵn (`compute_min_candidate_events`). Giữ nguyên mọi tiêu chí khác (contract
nguồn, mixer, khối lượng) y hệt 11 incident cũ.

- `positive_len(actions) = 248` → `min_candidate_events = 6`
- `positive_fan_out = 19` (số dst phân biệt trong toàn bộ trajectory) →
  `max_fan_out = 12` (band mới) — **so với ngưỡng cố định cũ = 3**

**Đây là incident ĐẦU TIÊN band fan_out mới thực sự phát huy tác dụng** (ở
11 incident cũ, `positive_fan_out` cao nhất chỉ là 4 → band vẫn = 3, không
đổi gì — xem `results/reports/fanout_band_v3_mining_v1.md`).

## Nguồn mining

Contract dùng để mining: **LI.FI Diamond** (`0x1231deb6f5749ef6ce6943a275a1d3e7486f4eae`,
Arbitrum) — CHÍNH LÀ contract thật xuất hiện trong outbound trajectory của
incident này (56 action `bridge_deposit` thật). Đã xác nhận verify độc lập
trên Arbiscan (`ContractName=LiFiDiamond`) trước khi thêm vào
`metadata/protocol_map.yaml` (mở rộng `chains` từ chỉ `["bsc"]` sang
`["bsc", "arbitrum"]` — cùng địa chỉ qua CREATE2, đã xác nhận thật, không
suy đoán).

## Kết quả

| | Số lượng |
|---|---|
| Candidate checked | 51 |
| Accepted | **25** (đạt `target_count`) |
| Rejected (độ phức tạp không đủ) | 15 |
| Rejected (fan_out vượt band) | 11 |
| **API call thực tế** | ~150 (1 bulk fetch contract + 51×3 candidate check) |

**Xác nhận payoff thật của band fan_out mới** (so sánh trên đúng 51
candidate đã check, không suy đoán): với ngưỡng cũ cố định = 3, chỉ **16/51**
candidate pass; với band mới = 12, **27/51** pass — **+11 hard-negative nhờ
fix Bước 1**.

## Sự cố phát hiện & xử lý giữa chừng: mất dữ liệu tạm thời cho 1 địa chỉ frontier

Sau khi mine xong, golden fixture của chính `radiant_capital_arbitrum_2024`
đổi từ 248 xuống 153 action (mất toàn bộ 56 `bridge_deposit`). Chẩn đoán:
địa chỉ `0x111111125421...` (1inch v5 AggregationRouter, 1 node frontier
hợp lệ trong trajectory chính) không còn cache theo đúng cửa sổ CHÍNH THỨC
của incident (chỉ còn cache theo cửa sổ MINING, rộng hơn/khác — nguyên nhân
kỹ thuật chính xác chưa truy hết nhưng dữ liệu bị thiếu cụ thể đã xác định
rõ). Đã fetch lại trực tiếp dữ liệu 1inch router theo đúng cửa sổ chính thức
(3 call bổ sung) — khôi phục đúng 248 action, xác nhận khớp golden gốc, sau
đó phát hiện thêm dữ liệu 1inch giờ đầy đủ hơn (nhiều bridge_deposit thật
hơn qua 1inch → LI.FI). Golden fixture đã cập nhật lần cuối, ổn định qua
2 lần chạy pytest liên tiếp.

## QA leakage

Phát hiện 5 địa chỉ trùng giữa `radiant_capital_arbitrum_2024` và
`deltaprime_arbitrum_2024`/`wooppv2_2024` (cả 3 đều Arbitrum, cùng hệ sinh
thái bridge). Đã xác nhận TỪNG địa chỉ qua `eth_getCode` + `getsourcecode`
thật: 4/5 là CONTRACT (Diamond proxy, ERC1967Proxy, StargateComposer —
hạ tầng DEX/bridge dùng chung xác nhận rõ ràng qua tên contract), 1/5 là EOA
nhưng xác nhận qua on-chain thật có **692 địa chỉ gửi độc lập, chỉ 2 địa chỉ
nhận** — mẫu hình dịch vụ dùng chung (gas refund/relayer), không phải liên
hệ riêng giữa 2 vụ. Đã loại trừ cả 5 khỏi leakage test với bằng chứng đầy đủ
(xem `tests/test_hard_negative_miner.py`).

## Rebuild dataset + RQ1/RQ2/ablation

- `features_v2.parquet`: 2726 → **2876 dòng** (12 positive, 540 negative,
  trong đó 428/439 hard-negative mined chính khả dụng — bao gồm 25 mới của
  radiant).
- **RQ1**: `radiant_capital_arbitrum_2024` giờ có `pr_auc` hợp lệ (M1=0.9705,
  B3=0.9750) — tham gia đầy đủ vào so sánh paired 12 incident (trước đó
  `nan` vì thiếu hard-negative). Mean diff (M1-B3) = -0.0465, 95% CI
  [-0.1181, +0.0085], Wilcoxon p=0.32 — **KẾT LUẬN VẪN KHÔNG ĐỔI** (KHÔNG ĐỦ
  BẰNG CHỨNG).
- **Ablation E4/E5**: kết luận không đổi (mọi CI vẫn chứa 0).
- **RQ2**: chạy thành công, `radiant_capital_arbitrum_2024` giờ có giá trị
  hợp lệ ở mọi prefix bucket.
- **194/194 test PASS** (ổn định qua 2 lần chạy liên tiếp).

## File đã cập nhật

- `metadata/hard_negative_registry.csv` (+25 dòng cho radiant)
- `metadata/split_manifest.json` (group radiant có `mined_hard_negative_ids`)
- `metadata/protocol_map.yaml` (LI.FI Diamond thêm chain arbitrum)
- `src/collect/hard_negative_miner.py` (thêm entry `INCIDENT_MINING_CONTRACTS`)
- `tests/fixtures/golden/radiant_capital_arbitrum_2024_events.golden.json`
- `tests/test_hard_negative_miner.py` (5 địa chỉ loại trừ mới)
- `data/processed/features_v2.parquet`, `results/tables/main_table.csv`,
  `baseline_results_v2.csv`, `ablation_table.csv`,
  `rq2_prefix_evaluation_folds.csv`, `results/reports/rq1_answer.md`,
  `ablation_e4_e5_v1.md`

Backup: hậu tố `_PRE_RADIANT_MINING_backup`.
