# Dataset Card — CAGI-ED v0.6

**Ngày freeze:** 2026-08-14
**Trạng thái:** ✅ Mở rộng từ 5 → **8 positive incident** (vượt minimum gate
chính thức 6, xem `configs/data.yaml`/tài liệu gốc mục 6.1) và vẫn giữ
hard-negative dùng được **343** (≥200, đã verify thật).
**Bản trước:** `data/dataset_card_v0.1.md` … `data/dataset_card_v0.5.md`
(freeze thứ 5, 5 incident, 269 usable) — giữ lại nguyên trạng các bản
trước để đối chiếu/audit.

---

## QUY ƯỚC BẮT BUỘC — 2 con số riêng biệt, không gộp chung

- **"raw mining"**: số dòng có mặt trong `hard_negative_registry.csv` (đã
  pass tiêu chí lọc CỦA MINER ở mức giao dịch — `_passes_structural_filter`,
  không áp `min_tainted_share`/`time_horizon_hours`).
- **"dùng được"**: số dòng trong đó, khi build lại bằng
  `expand_and_build_trajectory` (áp `min_tainted_share`/`time_horizon_hours`
  chuẩn — bộ lọc CHẶT HƠN miner), sinh ra trajectory KHÔNG rỗng (≥1 action
  → ≥1 prefix row). **Đây là con số quyết định có đạt ngưỡng ≥200 hay
  không.**

| | raw mining | dùng được (≥1 prefix row) |
|---|---|---|
| Hard-negative mining (`hard_negative_registry.csv`) | 348 | 338 |
| Hard-negative control gốc (Bước D, 5 dòng trong `incident_registry.csv`) | 5 | 5 |
| **TỔNG** | **353** | **343** |

**343 ≥ 200 → ĐẠT ngưỡng.** Dư 143 (buffer lớn, đủ chỗ cho các vòng
QA/leakage tiếp theo nếu phát sinh khi mở rộng thêm).

## Mở rộng 5 → 8 incident (2026-08-14)

Mục tiêu dự án: minimum gate ≥6 incident, target 10-15. Trước freeze này,
dataset chỉ có 5 (dưới minimum gate). Đã rà lại `experiments/logs/
excluded_candidates.md` (chỉ có XPEXE Bridge, vẫn không tìm được nguồn
công khai) và 26 dòng `CHECK_MANUALLY_non_eth_chain` trong
`incident_candidates_amlguard.csv` (2 dòng đã dùng: DeltaPrime, BSC Token
Hub) — lọc theo scope chain (bsc/arbitrum, loại FTM/Optimism/Polygon/BASE
vì `configs/data.yaml` không có collector), WebSearch từng candidate còn
lại tìm nguồn công khai + bằng chứng bridge/DEX. Chốt được **3/3** candidate
đạt chuẩn evidence (không phải hạ chuẩn để ép đủ):

1. **Chibi Finance** (Arbitrum, 2023-06-27) — CertiK official report, exit
   scam $1M+. Outbound trajectory (6 action): 2 bridge_deposit thật qua
   Multichain (400.015 ETH) + Stargate (156.417 ETH), tổng khớp CHÍNH XÁC
   báo cáo CertiK ("400 ETH via Multichain", "156 ETH via Stargate
   Bridge"). 1 swap thật.
2. **WooPPV2/WOOFi** (Arbitrum, 2024-03-05) — Beosin/CUBE3.AI/PeckShield/
   Cyfrin, $8.5M price manipulation. Outbound trajectory (6 action): 2
   bridge_deposit qua Stargate (200.117 ETH). 4 swap thật (WOO token flash
   loan). Bằng chứng bổ sung: ~2023.6 ETH chuyển tới địa chỉ cụ thể khớp
   CHÍNH XÁC "~2K ETH" PeckShield báo cáo.
3. **UtopiaSphere** (BSC, 2024-07-21) — CertiK official report, $521k flash
   loan. Outbound trajectory (13 action): **11** bridge_deposit thật qua LI.FI
   Diamond, tổng ~1071.53 BNB — khớp pattern báo cáo CertiK "swapped for
   147.6 ETH and bridged to Ethereum wallet [địa chỉ cụ thể]". 1 swap thật.

Loại (evidence không đủ mạnh): Radiant Capital Jan 2024 — exploit thật xác
nhận độc lập nhưng không tìm được báo cáo mô tả hành động bridge/DEX cụ thể
sau exploit. Magic/Treasure DAO 2025-03-25 — search chỉ tìm ra sự kiện khác
ngày (3/2023), không xác nhận được sự kiện CSV mô tả.

**Bug thật phát hiện khi tích hợp Chibi Finance**: `decode_normal_tx_row`/
`decode_internal_tx_row` (đường ETH/Arbitrum, native ETH tx) CHƯA BAO GIỜ
check `bridge_address_index` — chỉ `decode_bsctrace_transfer_row` (BSC) có
check này cho mọi category. Cả 2 bridge_deposit thật của Chibi Finance
(400+156 ETH) ban đầu bị decode thành `transfer` chung chung, mất nhãn
bridge. Đã sửa cả 2 hàm, đồng bộ với BSC. Rebuild lại 5 incident cũ — golden
test xác nhận KHÔNG đổi (không incident nào trước đó có bridge deposit qua
native ETH tx thuần). Xem `metadata/annotation_guide.md` mục 12.

**Xác định `start_block` thật cho Chibi Finance**: `BlockNumber` trong
`incident_candidates_amlguard.csv` (104090264) chỉ là thời điểm chuẩn bị
(4 ngày TRƯỚC drain thật, 2023-06-27) — nếu dùng nguyên, cửa sổ 72h mặc
định không phủ tới drain thật (block-rate Arbitrum thực tế giai đoạn này
~14,400 block/giờ, gấp 3 lần ước lượng `APPROX_BLOCKS_PER_HOUR`). Xác định
đúng bằng cách fetch cửa sổ rộng hơn thủ công, tìm đúng block drain
(105366596) rồi dùng làm `start_block`.

Cả 2 địa chỉ bridge mới (Multichain Router V6, Stargate ETH Router
Arbitrum, LI.FI Diamond) xác nhận qua **kép**: WebSearch độc lập TÌM địa
chỉ + đối chiếu lại với dữ liệu on-chain thật của chính seed (function
selector gọi thật khớp đúng chữ ký chuẩn của từng bridge — `anySwapOutNative`,
`swapETH`) — không suy đoán từ tên/memory.

## Lịch sử sửa lỗi số liệu trước đó (tóm tắt — chi tiết xem các bản trước)

v0.1→v0.2 (208 báo sai → 196 sửa đúng) → v0.3 (bug traceIndex/logIndex,
265 raw/258 usable) → v0.4 (bug representative-selection, 273 raw/266
usable) → v0.5 (bug dedup+tokentx-logIndex+swap-vs-merge, đối chiếu Venus
Protocol + re-validate hard-negative control, 274 raw/269 usable, 5
incident) → **v0.6 (mở rộng 5→8 incident, 348 raw/338 usable mining, 343
usable tổng)**. Toàn bộ lịch sử đầy đủ xem `data/dataset_card_v0.1.md`
đến `data/dataset_card_v0.5.md`.

## Nguồn dữ liệu

- **Danh sách seed ứng viên**: `metadata/incident_candidates_amlguard.csv`
  (82 dòng công khai) — **CHỈ dùng để tra cứu**, KHÔNG dùng ground truth
  AMLGuard (chưa công khai).
- **Ground truth**: `self_annotated` — mọi trajectory/nhãn tự dựng từ dữ
  liệu on-chain thật (Etherscan API V2, BSCTrace/MegaNode) + đối chiếu báo
  cáo công khai độc lập. Xem `source_url` trong `metadata/incident_registry.csv`.
- **Hard-negative mining**: `metadata/hard_negative_registry.csv` — mỗi
  dòng map tới `parent_incident_id`. Tiêu chí lọc (không đổi qua các lần
  mining): cùng chain, cùng protocol (đã verify), trong khung ±7 ngày
  quanh incident, không mixer_or_exit bất thường, không fan-out kiểu split
  (>3 counterparty riêng biệt), volume > 0. Loại trừ: seed address của mọi
  incident, địa chỉ AMLGuard candidates, địa chỉ đã dùng cho
  incident/hard-negative khác, địa chỉ gây leakage đã phát hiện qua QA.
- **Bridge/DEX/mixer/lending protocol contracts**: xác nhận qua on-chain
  thật, ghi trong `metadata/protocol_map.yaml`. Không suy đoán từ
  tên/memory — xem `metadata/annotation_guide.md` mục 1.

## Coverage

| Thuộc tính | Giá trị |
|---|---|
| Số dòng `incident_registry.csv` | 13 (8 positive + 5 hard-negative control gốc) |
| Số dòng positive (`label=1`) | 8: ronin_bridge_2022, qbridge_qubit_2022, feg_bridge_2024, deltaprime_arbitrum_2024, bsc_token_hub_2022, chibi_finance_2023, wooppv2_2024, utopiasphere_2024 |
| Hard-negative mining — raw | 348 |
| Hard-negative mining — dùng được | 338 |
| Chain | eth, bsc, arbitrum |
| Bridge family đã verify | Ronin Bridge, BSC Token Hub, Across Protocol SpokePool, Stargate, Multichain (AnySwap) Router V6, LI.FI Diamond, Wormhole Token Bridge (7) |
| DEX family đã verify | Uniswap V2, Uniswap V3, PancakeSwap V2, 1inch v4 (4) |
| Mixer đã verify | Tornado Cash Router (1) |
| Lending protocol đã verify | Venus Protocol (vBNB, bsc) (1) |
| Khoảng thời gian | 2022-01 đến 2024-11 |
| **Tổng prefix row toàn dataset** | **724** (positive: 46, negative: 678) |

Công thức prefix row/trajectory: `src/features/extractor.py::generate_prefixes`
— với trajectory `n` action, hợp 4 độ dài theo tỷ lệ (`ceil(n×0.25/0.5/0.75)`,
`n`) và 4 độ dài theo `k=2,3,5,7` (giữ nếu `k≤n`), khử trùng theo ĐỘ DÀI →
số phần tử = số prefix. `n=1` → 1 prefix; `n≥22` → tối đa 8 (trần công thức).

### Hard-negative mining theo incident positive (số liệu cuối, sau QA)

| parent_incident_id | Raw | Rỗng | Dùng được | Checked |
|---|---|---|---|---|
| ronin_bridge_2022 | 69 | 4 | 65 | 88 |
| qbridge_qubit_2022 | 35 | 0 | 35 | 100 (hết candidate ±7 ngày) |
| feg_bridge_2024 | 31 | 0 | 31 | 100 (hết candidate ±7 ngày) |
| deltaprime_arbitrum_2024 | 70 | 3 | 67 | 129 |
| bsc_token_hub_2022 | 69 | 2 | 67 | 104 |
| chibi_finance_2023 | 25 | 0 | 25 | 32 |
| wooppv2_2024 | 25 | 0 | 25 | 29 |
| utopiasphere_2024 | 24 | 1 | 23 | 43 |
| **TỔNG** | **348** | **10** | **338** | — |

3 incident mới (chibi/wooppv2/utopiasphere) đạt target 25/incident dễ dàng
(checked ≤43, không cần mở rộng cửa sổ ±7 ngày) — quần thể candidate tại
Stargate/LI.FI Diamond (bridge phổ biến, nhiều user thật) dồi dào hơn hẳn
so với các contract "hẹp" hơn (PancakeSwap V2 window riêng của QBridge/FEG).

## Exclusions

- **XPEXE Bridge**: loại — không tìm được báo cáo công khai.
- **Radiant Capital (Jan 2024), Magic/Treasure DAO (2025-03-25)**: loại
  khỏi 3 candidate mở rộng — evidence không đủ mạnh (xem mục "Mở rộng 5→8
  incident" ở trên).
- **10 hard-negative bị loại qua các vòng QA leakage** (2026-08-13/14):
  cùng nhóm địa chỉ counterparty phổ biến tái diễn qua nhiều vòng mining
  (`0x74de5d4f...`, `0xb4a8d456...`, `0x58f876...`) + 1 địa chỉ mới
  (`0xe37e799d...`, dùng chung giữa `deltaprime_arbitrum_2024` và
  `utopiasphere_2024`, loại `utopiasphere_2024__hn023`). Chi tiết đầy đủ
  trong git log các commit liên quan tới `metadata/hard_negative_registry.csv`.
- 3 incident mới KHÔNG có "hard-negative control gốc" riêng (chỉ dựa vào
  mined hard-negative) — khác 5 incident đầu (mỗi incident có đúng 1
  control gốc từ Bước D thời điểm dataset còn nhỏ).
- 26 candidate nhóm `CHECK_MANUALLY_non_eth_chain`: 5 đã dùng (DeltaPrime,
  BSC Token Hub, Chibi Finance*, WooPPV2*, UtopiaSphere* — *thêm 2026-08-14),
  2 loại (Radiant Capital, Magic), 19 còn lại CHƯA rà soát (dư địa mở rộng
  tiếp lên target 10-15 nếu cần sau này).
- Candidate ngoài scope chain (`FTM`, `Optimism`, `Polygon`, `BASE`) loại
  hoàn toàn theo `configs/data.yaml`.

## Giới hạn đã biết

1. **19/26 candidate `CHECK_MANUALLY_non_eth_chain` chưa rà soát** — dư
   địa mở rộng tiếp lên target 10-15 incident nếu 12 tuần cho phép.
2. **10/348 hard-negative (2.9%) vẫn có trajectory rỗng** — đặc tính hệ
   thống (miner check tương tác 2 chiều, builder chỉ trace forward), không
   phải bug. Xem `metadata/annotation_guide.md` mục 9 phần (B).
3. **`annotator_2` để trống cho TẤT CẢ 353 negative trajectory** (raw) —
   chưa qua review chéo độc lập.
4. **`endpoint_confirmed=False` cho 2/8 incident positive** (Ronin,
   QBridge).
5. **2 incident cũ (FEG Bridge, QBridge) chấp nhận evidence thay thế**
   thay vì bridge+DEX sạch trong outbound trajectory. 3 incident mới đều
   đạt gate HOÀN TOÀN trong outbound trajectory, không cần evidence phụ.
6. **[ĐÃ XỬ LÝ, giữ lại để audit] 4 bug liên tiếp trong tầng decode/merge
   cho 5 incident đầu** (traceIndex/logIndex, representative-selection,
   thiếu dedup trước merge + tokentx null logIndex, swap-vs-merge
   ambiguous) — đã sửa cả 4, golden fixture đầy đủ cho `ronin_bridge_2022`,
   `qbridge_qubit_2022`, `bsc_token_hub_2022`. `feg_bridge_2024`/
   `deltaprime_arbitrum_2024` chỉ xác nhận qua so sánh action count 1 lần
   (không phải golden fixture khóa cứng) — khuyến nghị thêm sau.
7. **[MỚI] Bug thiếu `bridge_address_index` cho native ETH tx** (đã sửa,
   commit `3398f03`) — golden fixture mới thêm cho cả 3 incident mới nên
   sẽ bắt được ngay nếu tái phát.
8. **`bsc_token_hub_2022` trajectory (66 action) vẫn có `value_share` dao
   động nhẹ (82-88%) giữa các lần build** — hạn chế kiến trúc đã biết
   (`outflow_by_src` cộng dồn raw value across nhiều token khác nhau),
   không đổi kết quả accept/reject trong trường hợp đã kiểm tra.
9. **BSCTrace `fromBlock`/`toBlock`/`traceIndex` không có trong tài liệu
   công khai** dù đã xác nhận hoạt động/tồn tại thật.
10. **`data/raw/` cache phụ thuộc thời điểm crawl** (2026-08-13/14).
11. **Multichain (AnySwap) Router V6** — protocol đã NGỪNG HOẠT ĐỘNG từ
    giữa 2023 (sau vụ bắt giữ CEO), contract vẫn tồn tại on-chain nhưng
    không còn đáng tin cậy — chỉ dùng để đối chiếu lịch sử (Chibi Finance
    2023), KHÔNG dùng làm route cho dữ liệu mới.

## License / sử dụng

- Dữ liệu on-chain: công khai theo bản chất (public blockchain).
- Báo cáo công khai được trích dẫn: chỉ dùng để đối chiếu số liệu, luôn
  dẫn nguồn qua `source_url`, không sao chép nội dung.
- KHÔNG chứa dữ liệu ground truth độc quyền của AMLGuard.
- Repo này dùng cho mục đích nghiên cứu KLTN, không phải sản phẩm thương mại.

## Tái tạo lại dataset

```bash
# Chạy lại pipeline cho 1 incident gốc (dùng cache đã có)
python scripts/run_incident_pipeline.py --incident-id <incident_id> --no-collect

# Chạy lại mining hard-negative (do_collect=False dùng cache)
# xem scripts/run_hard_negative_mining_new_incidents.py (3 incident mới),
# scripts/run_hard_negative_remine_all_after_bug34_fix.py (5 incident cũ)

# Tính lại toàn bộ số liệu raw/usable/tổng prefix row + tỷ lệ rỗng theo incident
python scripts/compute_dataset_v0.6_stats.py

# Chạy tests xác nhận tính nhất quán + QA leakage + gate usable>=200 + golden fixtures
pytest tests/ -v
```
