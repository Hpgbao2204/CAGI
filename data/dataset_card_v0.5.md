# Dataset Card — CAGI-ED v0.5

**Ngày freeze:** 2026-08-14
**Trạng thái:** ✅ Đạt ngưỡng "≥200 hard-negative dùng được" (con số ĐÃ xác
minh bằng cách build lại từng trajectory, KHÔNG phải đếm dòng registry) —
**và** đã đối chiếu 2 positive trajectory BSC với báo cáo công khai +
re-validate hard-negative control gốc theo đúng tiêu chí matching (xem
Lịch sử sửa lỗi #13-#18).
**Bản trước:** `data/dataset_card_v0.1.md` (freeze đầu, 9 negative prefix,
KHÔNG đạt), `data/dataset_card_v0.2.md` (freeze thứ 2, ban đầu báo SAI là
"208 đạt ngưỡng"), `data/dataset_card_v0.3.md` (freeze thứ 3, 258 usable),
`data/dataset_card_v0.4.md` (freeze thứ 4, 266 usable — sau đó phát hiện
thêm 2 bug + 1 vấn đề đối chiếu báo cáo công khai khi verify sâu hơn theo
yêu cầu người dùng, xem bên dưới; giữ lại nguyên trạng các bản trước để
đối chiếu/audit).

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
| Hard-negative mining (`hard_negative_registry.csv`) | 274 | 264 |
| Hard-negative control gốc (Bước D, 5 dòng trong `incident_registry.csv`) | 5 | 5 |
| **TỔNG** | **279** | **269** |

**269 ≥ 200 → ĐẠT ngưỡng.** Dư 69 (buffer an toàn cho các vòng QA/leakage
tiếp theo nếu phát sinh).

## Lịch sử sửa lỗi số liệu (minh bạch — không xoá dấu vết)

1. **v0.2 lần 1** (commit `85529b3`): báo cáo "208 đạt ngưỡng 200" — SAI,
   đếm cả 208 dòng raw mà không kiểm tra trajectory có rỗng hay không.
2. **Phát hiện lỗi**: kiểm lại bằng `expand_and_build_trajectory` → 17/208
   trajectory rỗng → usable thật = 196 < 200.
3. **Sửa số liệu ngay** (commit `df53bec`): cập nhật `dataset_card.md` +
   `experiments/registry.csv` về đúng 196, KHÔNG chờ mining xong mới sửa.
4. **Chẩn đoán bug #1** (`decode_bsctrace_transfer_row` dùng `logIndex`
   luôn=0 cho native BNB làm khoá dedup, mất leg) — sửa bằng `traceIndex`
   (commit `b588f41`). Xem `metadata/annotation_guide.md` mục 9.
5-7. Mining bổ sung + QA leakage round 2 → **265 raw, 258 dùng được →
   freeze v0.3 (commit `3a83225`)**.
8. **Re-verify theo yêu cầu người dùng**: rebuild 2 positive trajectory
   BSC. `bsc_token_hub_2022` giảm 14→10 action, mất 4 swap thật — phát
   hiện nghiêm trọng, DỪNG LẠI để chẩn đoán.
9-12. **Chẩn đoán + sửa bug #2** (`merge_events_into_semantic_actions`
   chọn sai representative cho swap 2-leg khi sort theo `log_index`) →
   rebuild toàn bộ BSC + re-mine → **273 raw, 266 dùng được → freeze v0.4
   (commit `d4fd4e2`)**.
13. **Re-verify tiếp theo yêu cầu người dùng** ("không coi 'không rỗng'
   đồng nghĩa 'đúng'"): phát hiện thêm **2 bug nữa** khi xác nhận 66-action
   `bsc_token_hub_2022` ổn định/tái lập được:
   - **Bug #3**: `_load_events_bsctrace`/`_load_events_etherscan` thiếu
     dedup trước khi gộp theo `tx_hash` — 1 giao dịch giữa 2 địa chỉ đang
     trace bị decode 2 lần (1 lần/địa chỉ), làm sai `total_amount` ở
     nhánh 'swap'. Đồng thời phát hiện Etherscan API V2 `tokentx` KHÔNG
     trả `logIndex` thật cho BẤT KỲ dòng nào (100% dòng đã cache, eth lẫn
     arbitrum) — sửa bằng dedup trước merge + hash nội dung leg làm
     `log_index` giả ổn định.
   - **Bug #4**: điều kiện 'swap' cũ vẫn đúng khi 2 nguồn KHÔNG liên quan
     gửi 2 token khác nhau hội tụ vào 1 đích (đúng ra là 'merge') — sửa
     bằng cách yêu cầu địa chỉ tự-tham-chiếu (round-trip thật).
   Rebuild toàn bộ + re-mine cả 5 incident (không chỉ BSC) → **274 raw,
   268 dùng được** (commit `6008264`, `60d7e02`).
14. **Bước 1 — đối chiếu `bsc_token_hub_2022` (66 action lúc đó, thực ra
   vẫn 63) với báo cáo công khai**: Elliptic báo cáo attacker "deposited
   900,000 newly-minted BNB... as collateral on Venus Protocol" — trajectory
   lúc đó HOÀN TOÀN THIẾU Venus Protocol (chỉ có PancakeSwap). Dữ liệu
   Venus THẬT có trong raw cache (vBNB `0xa07c5b74...`) nhưng chưa được
   nhận diện. **KHÔNG khớp báo cáo công khai — dừng lại, báo cáo.**
15. **Thêm Venus Protocol vào `protocol_map.yaml`** (xác nhận qua BscScan
   token label + đối chiếu độc lập Blockscan/Bitquery, KHÔNG từ memory).
   Phát hiện thêm **2 bug** khi tích hợp: (a) representative-selection sai
   cho trường hợp đối xứng (seed<->Venus contract đều tự tham chiếu) —
   chọn nhầm leg ERC-20 phản hồi thay vì leg native thật; (b) nhánh 'swap'
   ghi đè `event_type`/`amount_norm` của representative dù đã gắn nhãn
   protocol-specific đúng trước đó (amount_norm bị trung bình sai ~7 lần
   với leg vBNB khác decimals). Sửa cả 2 (commit `4594af7`). Kết quả:
   `bsc_token_hub_2022` 63 → **66 action**, 3 action `lending_deposit` mới
   tổng **899,995.8-900,000.1 BNB** — khớp CHÍNH XÁC "900,000 BNB" Elliptic
   báo cáo. Verify riêng `0x46ed8b4a...`: `value_share=82-88%`, vượt xa
   ngưỡng 5%, giữ đúng luật `min_tainted_share`.
16. **Bước 2 — re-validate `qbridge_benign_control_2022` (134 action) theo
   tiêu chí matching gốc**: chạy lại `_passes_structural_filter` thật →
   **FAIL** (`fan_out_split_like_pattern` — 275 địa chỉ đích khác nhau
   trong cửa sổ mining ±7 ngày, rõ ràng bot/MEV quy mô lớn). **Loại khỏi
   vai trò control gốc.** Mine 1 candidate thay thế qua ĐÚNG pipeline
   `mine_hard_negatives_for_incident` (do_collect=True, mạng thật, cache
   không còn candidate mới): `0xfb152235...` — chỉ 1 event outbound DUY
   NHẤT trong toàn bộ cửa sổ ±7 ngày (0.0019 BNB tới PancakeSwap V2
   Router), pass tiêu chí (không fan-out, không mixer, volume>0). Cập
   nhật `metadata/incident_registry.csv`.
17. **Bước 3 — thêm golden fixture**: `qbridge_qubit_2022` (22 action,
   xác nhận không đổi) và `bsc_token_hub_2022` (66 action, sau khi verify
   xong Venus Protocol) — khóa cứng nội dung, test fail ngay nếu có thay
   đổi không review sau này (commit `e5bb079`).
18. **Rebuild + re-mine lại lần cuối** sau khi thay `qbridge_benign_control_2022`:
   QA leakage round 5 phát hiện lại đúng 3 địa chỉ leak quen thuộc (cùng
   pattern mọi lần trước) — loại 3 hard-negative liên quan → **274 raw
   cuối cùng, 0 leakage, 269 dùng được → freeze v0.5**.

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
  quanh incident (BSC Token Hub: chỉ "trước" incident do chain bị dừng sau
  hack), không mixer_or_exit bất thường, không fan-out kiểu split (>3
  counterparty riêng biệt), volume > 0. Loại trừ: seed address của mọi
  incident, địa chỉ AMLGuard candidates, địa chỉ đã dùng cho
  incident/hard-negative khác, địa chỉ gây leakage đã phát hiện qua QA.
- **Bridge/DEX/mixer/lending protocol contracts**: xác nhận qua on-chain
  thật, ghi trong `metadata/protocol_map.yaml`. Không suy đoán từ
  tên/memory — xem `metadata/annotation_guide.md` mục 1.

## Coverage

| Thuộc tính | Giá trị |
|---|---|
| Số dòng `incident_registry.csv` | 10 (5 positive + 5 hard-negative control gốc) — **KHÔNG phải 10 positive** |
| Số dòng positive (`label=1`) | 5: ronin_bridge_2022, qbridge_qubit_2022, feg_bridge_2024, deltaprime_arbitrum_2024, bsc_token_hub_2022 |
| Hard-negative mining — raw | 274 |
| Hard-negative mining — dùng được | 264 |
| Chain | eth, bsc, arbitrum |
| Bridge family đã verify | Ronin Bridge, BSC Token Hub, Across Protocol SpokePool (3) |
| DEX family đã verify | Uniswap V2, Uniswap V3, PancakeSwap V2, 1inch v4 (4) |
| Mixer đã verify | Tornado Cash Router (1) |
| Lending protocol đã verify | Venus Protocol (vBNB, bsc) (1) |
| Khoảng thời gian | 2022-01 đến 2024-11 |
| **Tổng prefix row toàn dataset** | **608** (positive: 31, negative: 577) |

Công thức prefix row/trajectory: `src/features/extractor.py::generate_prefixes`
— với trajectory `n` action, hợp 4 độ dài theo tỷ lệ (`ceil(n×0.25/0.5/0.75)`,
`n`) và 4 độ dài theo `k=2,3,5,7` (giữ nếu `k≤n`), khử trùng theo ĐỘ DÀI →
số phần tử = số prefix. `n=1` → 1 prefix; `n≥22` → tối đa 8 (trần công thức).

### Hard-negative mining theo incident positive (số liệu cuối, sau QA round 5)

| parent_incident_id | Raw | Rỗng | Dùng được | Checked (tổng qua các lần mining) |
|---|---|---|---|---|
| ronin_bridge_2022 | 69 | 4 | 65 | 88 |
| qbridge_qubit_2022 | 35 | 0 | 35 | 100 (HẾT candidate trong ±7 ngày) |
| feg_bridge_2024 | 31 | 0 | 31 | 100 (HẾT candidate trong ±7 ngày) |
| deltaprime_arbitrum_2024 | 70 | 4 | 66 | 129 |
| bsc_token_hub_2022 | 69 | 2 | 67 | 104 |
| **TỔNG** | **274** | **10** | **264** | — |

`qbridge_qubit_2022` và `feg_bridge_2024` dừng ở 35/31 (thấp hơn các
incident khác) vì đã kiểm tra HẾT candidate khả dụng trong cửa sổ ±7 ngày
— **KHÔNG mở rộng cửa sổ thời gian** vì tổng đã đủ vượt ngưỡng 200 mà
không cần; để dành làm hướng mở rộng nếu cần thêm dữ liệu sau này (nới ±7
ngày thành ±14 ngày, xem `metadata/annotation_guide.md` mục 9).

## Exclusions

- **XPEXE Bridge**: loại — không tìm được báo cáo công khai.
- **9 hard-negative bị loại qua 5 vòng QA leakage** (2026-08-13/14): cùng
  3 địa chỉ counterparty phổ biến tái diễn qua nhiều vòng mining
  (`0x74de5d4f...`, `0xb4a8d456...`, `0x58f876...`) — mỗi vòng loại lại
  đúng 3 hard-negative liên quan khi chúng xuất hiện lại. Chi tiết đầy đủ
  trong git log các commit liên quan tới `metadata/hard_negative_registry.csv`.
- **1 hard-negative control gốc bị THAY THẾ** (không phải loại khỏi
  dataset — vẫn giữ 5 control gốc): `qbridge_benign_control_2022` cũ
  (`0xd76a7c3828...`) không pass tiêu chí matching gốc khi verify lại
  (fan-out 275 địa chỉ, bot/MEV) — thay bằng `0xfb152235...` (1 event
  outbound duy nhất trong cửa sổ mining, pass tiêu chí). Xem Lịch sử sửa
  lỗi #16.
- 26 candidate nhóm `CHECK_MANUALLY_non_eth_chain` phần lớn CHƯA rà soát.
- Candidate ngoài scope chain (`FTM`, `Optimism`, `Polygon`, `BASE`) loại
  hoàn toàn theo `configs/data.yaml`.

## Giới hạn đã biết

1. **`qbridge_qubit_2022`/`feg_bridge_2024` không tận dụng hết margin**
   (35/31 so với 65-67 của 3 incident khác) — đã hết candidate trong cửa
   sổ ±7 ngày hiện tại, chưa thử mở rộng cửa sổ.
2. **10/274 hard-negative (3.6%) vẫn có trajectory rỗng** — đặc tính hệ
   thống (miner check tương tác 2 chiều, builder chỉ trace forward),
   không phải bug. Xem `metadata/annotation_guide.md` mục 9 phần (B).
3. **`annotator_2` để trống cho TẤT CẢ 279 negative trajectory** (raw) —
   chưa qua review chéo độc lập.
4. **`endpoint_confirmed=False` cho 2/5 incident positive** (Ronin,
   QBridge).
5. **2 incident (FEG Bridge, QBridge) chấp nhận evidence thay thế** thay
   vì bridge+DEX sạch trong outbound trajectory — xem
   `metadata/annotation_guide.md` mục 5.
6. **[ĐÃ XỬ LÝ, giữ lại để audit] 4 bug liên tiếp trong tầng decode/merge**
   (traceIndex/logIndex, representative-selection, thiếu dedup trước
   merge + tokentx null logIndex, swap-vs-merge ambiguous) — đã sửa cả 4,
   golden fixture đã thêm cho `ronin_bridge_2022` (từ trước),
   `qbridge_qubit_2022`, `bsc_token_hub_2022` (mới). `feg_bridge_2024`/
   `deltaprime_arbitrum_2024` CHỈ xác nhận qua so sánh action count 1 lần
   (không phải golden fixture khóa cứng) — khuyến nghị thêm sau.
7. **`bsc_token_hub_2022` trajectory (66 action) vẫn có `value_share`
   dao động nhẹ (82-88%) giữa các lần build** cho 1 action cụ thể — do
   `outflow_by_src` cộng dồn raw value across nhiều token khác nhau
   không có ý nghĩa toán học đầy đủ (chưa có dữ liệu giá quy đổi USD,
   xem comment `TrajectoryConfig.allowlist`). KHÔNG đổi kết quả accept/
   reject trong trường hợp đã kiểm tra (cả 2 giá trị đều vượt xa ngưỡng
   5%), nhưng là hạn chế kiến trúc chưa xử lý triệt để.
8. **BSCTrace `fromBlock`/`toBlock`/`traceIndex` không có trong tài liệu
   công khai** dù đã xác nhận hoạt động/tồn tại thật.
9. **`data/raw/` cache phụ thuộc thời điểm crawl** (2026-08-13/14).

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
# xem scripts/run_hard_negative_mining.py, scripts/run_hard_negative_mining_expand.py,
# scripts/run_hard_negative_remine_bsc_after_merge_fix.py,
# scripts/run_hard_negative_remine_all_after_bug34_fix.py

# Tính lại toàn bộ số liệu raw/usable/tổng prefix row + tỷ lệ rỗng theo incident
python scripts/compute_dataset_v0.4_stats.py

# Chạy tests xác nhận tính nhất quán + QA leakage + gate usable>=200 + golden fixtures
pytest tests/ -v
```
