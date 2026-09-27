# Dataset Card — CAGI-ED v0.3

**Ngày freeze:** 2026-08-13
**Trạng thái:** ✅ Đạt ngưỡng "≥200 hard-negative dùng được" (con số ĐÃ xác
minh bằng cách build lại từng trajectory, KHÔNG phải đếm dòng registry).
**Bản trước:** `data/dataset_card_v0.1.md` (freeze đầu, 9 negative prefix,
KHÔNG đạt), `data/dataset_card_v0.2.md` (freeze thứ 2, ban đầu báo SAI là
"208 đạt ngưỡng" — thực ra usable chỉ 196, đã tự phát hiện và sửa; giữ lại
nguyên trạng để đối chiếu/audit).

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
| Hard-negative mining (`hard_negative_registry.csv`) | 265 | 253 |
| Hard-negative control gốc (Bước D, 5 dòng trong `incident_registry.csv`) | 5 | 5 |
| **TỔNG** | **270** | **258** |

**258 ≥ 200 → ĐẠT ngưỡng.** Dư 58 (buffer an toàn cho các vòng QA/leakage
tiếp theo nếu phát sinh).

## Lịch sử sửa lỗi số liệu (minh bạch — không xoá dấu vết)

1. **v0.2 lần 1** (commit `85529b3`): báo cáo "208 đạt ngưỡng 200" — SAI,
   đếm cả 208 dòng raw mà không kiểm tra trajectory có rỗng hay không.
2. **Phát hiện lỗi** (người dùng đặt câu hỏi cụ thể bằng số): kiểm lại
   bằng `expand_and_build_trajectory` cho từng dòng → 17/208 trajectory
   rỗng → usable thật = 196 < 200.
3. **Sửa số liệu ngay** (commit `df53bec`): cập nhật `dataset_card.md` +
   `experiments/registry.csv` về đúng 196, đổi status thành
   `not_frozen_pending_more_mining`, KHÔNG chờ mining xong mới sửa.
4. **Chẩn đoán nguyên nhân rỗng**: phát hiện bug thật trong
   `decode_bsctrace_transfer_row` — dùng `logIndex` (luôn =0 cho native
   BNB transfer trên BSCTrace) làm khoá dedup, khiến 2 leg khác nhau cùng
   `tx_hash` (vd 2 chân của 1 swap) bị coi trùng và mất 1 leg. Sửa bằng
   `traceIndex` (field phân biệt thật) — xem
   `metadata/annotation_guide.md` mục 9 để biết chi tiết đầy đủ.
5. **Mining lại từ đầu** với decoder đã sửa (dùng cache cũ, không tốn
   quota mới cho bước validate) → tỷ lệ rỗng giảm từ 8.2% xuống ~4.2%,
   nhưng RAW accepted cũng giảm (qbridge/bsc_token_hub từng được accept
   SAI một số candidate do fan-out bị đếm thiếu bởi bug).
6. **Mining bổ sung có buffer** (Bước 3, KHÔNG dồn vào QBridge/FEG đã hết
   candidate ở 100 checked) cho `ronin_bridge_2022`,
   `deltaprime_arbitrum_2024`, `bsc_token_hub_2022` (target 70/incident,
   max_candidates_checked=150) → 268 raw mới.
7. **QA leakage** phát hiện lại đúng 3 cặp address từng gặp ở v0.2 (cùng
   nguyên nhân: 1 địa chỉ counterparty phổ biến bị nhiều hard-negative
   khác nhau chạm tới) — loại 3 hard-negative liên quan → **265 raw cuối
   cùng, 0 leakage, 258 dùng được**.

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
- **Bridge/DEX/mixer protocol contracts**: xác nhận qua on-chain thật, ghi
  trong `metadata/protocol_map.yaml`. Không suy đoán từ tên/memory — xem
  `metadata/annotation_guide.md` mục 1.

## Coverage

| Thuộc tính | Giá trị |
|---|---|
| Số dòng `incident_registry.csv` | 10 (5 positive + 5 hard-negative control gốc) — **KHÔNG phải 10 positive** |
| Số dòng positive (`label=1`) | 5: ronin_bridge_2022, qbridge_qubit_2022, feg_bridge_2024, deltaprime_arbitrum_2024, bsc_token_hub_2022 |
| Hard-negative mining — raw | 265 |
| Hard-negative mining — dùng được | 253 |
| Chain | eth, bsc, arbitrum |
| Bridge family đã verify | Ronin Bridge, BSC Token Hub, Across Protocol SpokePool (3) |
| DEX family đã verify | Uniswap V2, Uniswap V3, PancakeSwap V2, 1inch v4 (4) |
| Mixer đã verify | Tornado Cash Router (1) |
| Khoảng thời gian | 2022-03 đến 2024-11 |
| **Tổng prefix row toàn dataset** | **572** |

Công thức prefix row/trajectory: `src/features/extractor.py::generate_prefixes`
— với trajectory `n` action, hợp 4 độ dài theo tỷ lệ (`ceil(n×0.25/0.5/0.75)`,
`n`) và 4 độ dài theo `k=2,3,5,7` (giữ nếu `k≤n`), khử trùng theo ĐỘ DÀI →
số phần tử = số prefix. `n=1` → 1 prefix; `n≥22` → tối đa 8 (trần công thức).

### Hard-negative mining theo incident positive (số liệu cuối, sau QA)

| parent_incident_id | Raw | Rỗng | Dùng được | Checked (tổng qua các lần mining) |
|---|---|---|---|---|
| ronin_bridge_2022 | 69 | 4 | 65 | 88 (đã đạt target 70, -1 do QA) |
| qbridge_qubit_2022 | 26 | 0 | 26 | 100 (HẾT candidate trong ±7 ngày) |
| feg_bridge_2024 | 31 | 0 | 31 | 100 (HẾT candidate trong ±7 ngày) |
| deltaprime_arbitrum_2024 | 70 | 4 | 66 | 134 |
| bsc_token_hub_2022 | 69 | 4 | 65 | 107 (đã đạt target 70, -1 do QA) |
| **TỔNG** | **265** | **12** | **253** | — |

`qbridge_qubit_2022` và `feg_bridge_2024` dừng ở 26/31 (thấp hơn các
incident khác) vì đã kiểm tra HẾT candidate khả dụng trong cửa sổ ±7 ngày
(`max_candidates_checked=100`, không còn candidate mới để check) —
**KHÔNG mở rộng cửa sổ thời gian cho 2 vụ này** trong lần sửa này vì tổng
đã đủ vượt ngưỡng 200 mà không cần; để dành làm hướng mở rộng nếu cần
thêm dữ liệu sau này (nới ±7 ngày thành ±14 ngày, xem
`metadata/annotation_guide.md` mục 9).

## Exclusions

- **XPEXE Bridge**: loại — không tìm được báo cáo công khai. Xem
  `experiments/logs/excluded_candidates.md`.
- **6 hard-negative bị loại qua 2 vòng QA leakage** (2026-08-13):
  `ronin_bridge_2022__hn023` (×2 lần, cả 2 vòng mining), `deltaprime_arbitrum_2024__hn018`,
  `feg_bridge_2024__hn026` (×2 lần), `bsc_token_hub_2022__hn041` (×2 lần),
  `qbridge_qubit_2022__hn020`/tương đương — tất cả đều là hard-negative có
  trajectory chạm 1 trong 3 địa chỉ counterparty phổ biến bị nhiều nhóm
  khác nhau cùng chạm tới. Chi tiết đầy đủ trong git log các commit liên
  quan tới `metadata/hard_negative_registry.csv`.
- 26 candidate nhóm `CHECK_MANUALLY_non_eth_chain` phần lớn CHƯA rà soát.
- Candidate ngoài scope chain (`FTM`, `Optimism`, `Polygon`, `BASE`) loại
  hoàn toàn theo `configs/data.yaml`.

## Giới hạn đã biết

1. **`qbridge_qubit_2022`/`feg_bridge_2024` không tận dụng hết margin**
   (26/31 so với 65-66 của 3 incident khác) — đã hết candidate trong cửa
   sổ ±7 ngày hiện tại, chưa thử mở rộng cửa sổ (xem mục Coverage ở trên).
2. **12/265 hard-negative (4.5%) vẫn có trajectory rỗng** ngay cả sau khi
   sửa bug traceIndex — nguyên nhân còn lại là đặc tính hệ thống (miner
   check tương tác 2 chiều, builder chỉ trace forward), không phải bug.
   Xem `metadata/annotation_guide.md` mục 9 phần (B).
3. **`annotator_2` để trống cho TẤT CẢ 270 negative trajectory** (raw) —
   chưa qua review chéo độc lập, quy mô lớn hơn nhiều so với lúc viết
   `experiments/logs/cross_review_log.md` (viết cho 10 incident gốc).
4. **`endpoint_confirmed=False` cho 2/5 incident positive** (Ronin,
   QBridge).
5. **2 incident (FEG Bridge, QBridge) chấp nhận evidence thay thế** thay
   vì bridge+DEX sạch trong outbound trajectory — xem
   `metadata/annotation_guide.md` mục 5.
6. **Bug `traceIndex` vs `logIndex`** (mục "Lịch sử sửa lỗi" #4) có thể đã
   ảnh hưởng ÂM THẦM tới các trajectory BSC đã build TRƯỚC lần sửa này
   (không chỉ 17 hard-negative rỗng ban đầu) — `qbridge_qubit_2022` và
   `bsc_token_hub_2022` (2 incident positive gốc, chain=bsc) nên được
   build lại và đối chiếu số liệu nếu dùng cho kết quả benchmark chính
   thức. Golden fixtures hiện tại (`tests/fixtures/golden/`) chỉ có cho
   Ronin (chain=eth, không bị ảnh hưởng bởi bug này).
7. **BSCTrace `fromBlock`/`toBlock`/`traceIndex` không có trong tài liệu
   công khai** dù đã xác nhận hoạt động/tồn tại thật — rủi ro thay đổi
   không báo trước từ nhà cung cấp.
8. **`data/raw/` cache phụ thuộc thời điểm crawl** (2026-08-13).

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

# Chạy lại mining hard-negative (script gốc, do_collect=False dùng cache)
# xem scripts/run_hard_negative_mining.py và scripts/run_hard_negative_mining_expand.py

# Chạy tests xác nhận tính nhất quán + QA leakage + gate usable>=200
pytest tests/ -v
```
