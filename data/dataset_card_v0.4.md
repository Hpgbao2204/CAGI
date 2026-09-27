# Dataset Card — CAGI-ED v0.4

**Ngày freeze:** 2026-08-13
**Trạng thái:** ✅ Đạt ngưỡng "≥200 hard-negative dùng được" (con số ĐÃ xác
minh bằng cách build lại từng trajectory, KHÔNG phải đếm dòng registry) —
**và** đã re-verify lại 2 positive trajectory BSC + toàn bộ hard-negative
BSC sau khi phát hiện 1 bug thứ 2 (xem Lịch sử sửa lỗi #8-#12).
**Bản trước:** `data/dataset_card_v0.1.md` (freeze đầu, 9 negative prefix,
KHÔNG đạt), `data/dataset_card_v0.2.md` (freeze thứ 2, ban đầu báo SAI là
"208 đạt ngưỡng" — thực ra usable chỉ 196, đã tự phát hiện và sửa),
`data/dataset_card_v0.3.md` (freeze thứ 3, 258 usable — sau đó phát hiện
1 bug thứ 2 làm sai nội dung 1 positive trajectory BSC, xem bên dưới; giữ
lại nguyên trạng các bản trước để đối chiếu/audit).

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
| Hard-negative mining (`hard_negative_registry.csv`) | 273 | 261 |
| Hard-negative control gốc (Bước D, 5 dòng trong `incident_registry.csv`) | 5 | 5 |
| **TỔNG** | **278** | **266** |

**266 ≥ 200 → ĐẠT ngưỡng.** Dư 66 (buffer an toàn cho các vòng QA/leakage
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
4. **Chẩn đoán nguyên nhân rỗng (bug #1)**: phát hiện bug thật trong
   `decode_bsctrace_transfer_row` — dùng `logIndex` (luôn =0 cho native
   BNB transfer trên BSCTrace) làm khoá dedup, khiến 2 leg khác nhau cùng
   `tx_hash` (vd 2 chân của 1 swap) bị coi trùng và mất 1 leg. Sửa bằng
   `traceIndex` (field phân biệt thật, commit `b588f41`) — xem
   `metadata/annotation_guide.md` mục 9 để biết chi tiết đầy đủ.
5. **Mining lại từ đầu** với decoder đã sửa (dùng cache cũ, không tốn
   quota mới cho bước validate) → tỷ lệ rỗng giảm từ 8.2% xuống ~4.2%,
   nhưng RAW accepted cũng giảm (qbridge/bsc_token_hub từng được accept
   SAI một số candidate do fan-out bị đếm thiếu bởi bug).
6. **Mining bổ sung có buffer** (Bước 3, KHÔNG dồn vào QBridge/FEG đã hết
   candidate ở 100 checked) cho `ronin_bridge_2022`,
   `deltaprime_arbitrum_2024`, `bsc_token_hub_2022` (target 70/incident,
   max_candidates_checked=150) → 268 raw mới.
7. **QA leakage round 2** phát hiện lại đúng 3 cặp address từng gặp ở
   v0.2 (cùng nguyên nhân: 1 địa chỉ counterparty phổ biến bị nhiều
   hard-negative khác nhau chạm tới) — loại 3 hard-negative liên quan →
   **265 raw, 0 leakage, 258 dùng được → freeze v0.3 (commit `3a83225`)**.
8. **Re-verify theo yêu cầu người dùng**: rebuild lại 2 positive
   trajectory BSC (`qbridge_qubit_2022`, `bsc_token_hub_2022`) từ
   `data/raw/` bằng decoder đã sửa (bug #1), đối chiếu với số liệu đã
   verify ban đầu. `qbridge_qubit_2022` không đổi (22/22 action giống
   hệt). **`bsc_token_hub_2022` giảm từ 14 xuống CHỈ CÒN 10 action, mất
   đúng 4 swap thật (PancakeSwap V2) vốn là bằng chứng "khớp chính xác"
   đã dùng để verify incident này ban đầu** — phát hiện nghiêm trọng,
   DỪNG LẠI để chẩn đoán, không tự sửa rồi âm thầm cập nhật (đúng yêu cầu
   người dùng).
9. **Chẩn đoán bug #2** (`merge_events_into_semantic_actions` chọn sai
   `representative` cho swap 2-leg bằng cách sort `log_index` thay vì
   xác định đúng leg outbound — bug ĐỘC LẬP với bug #1, có từ trước, chỉ
   tình cờ bị lộ ra khi bug #1 được sửa vì offset native làm đảo thứ tự
   sort). Sửa hàm để chọn representative theo địa chỉ "tự tham chiếu"
   (self-referencing: xuất hiện vừa là `src` 1 leg vừa là `dst` leg còn
   lại) thay vì `log_index`. Thêm test hồi quy
   `test_merge_events_swap_representative_uses_outbound_leg_not_log_index_order`.
   Xem `metadata/annotation_guide.md` mục 10.
10. **Rebuild lại toàn bộ BSC** với bug #2 đã sửa: `bsc_token_hub_2022`
    (positive) 10 → **63 action** (phục hồi cả swap của seed lẫn của địa
    chỉ trung gian `0x46ed8b4a...` trước đó bị ẩn hoàn toàn);
    `qbridge_benign_control_2022` (hard-negative control gốc) 3 → **134
    action** (hóa ra là 1 bot PancakeSwap tự động rất tích cực, không
    phải địa chỉ "ít giao dịch nhất" như tiêu chí chọn ban đầu tưởng —
    tiêu chí đó dựa trên dữ liệu decode sai). `ronin_bridge_2022` xác
    nhận KHÔNG đổi qua golden regression test; `feg_bridge_2024`/
    `deltaprime_arbitrum_2024` xác nhận không đổi qua so sánh action
    count trước/sau (không phải golden test có khóa cứng).
11. **Mine lại toàn bộ hard-negative BSC từ đầu** (không chỉ rebuild
    trajectory của tập cũ) vì `_passes_structural_filter` dùng chung
    hàm bị bug #2 ảnh hưởng → tập candidate đã accept trước đó cũng có
    thể sai. Dùng lại đúng `target_count`/`max_candidates_checked` đã
    dùng trước đó, `do_collect=False` (chỉ cache có sẵn, không cần gọi
    mạng mới): `qbridge_qubit_2022` 26 → **34** accepted,
    `bsc_token_hub_2022` 69 → **70** accepted.
12. **QA leakage round 3**: phát hiện lại 1 trong 3 địa chỉ leak quen
    thuộc (`0x58f876...`) trùng giữa `bsc_token_hub_2022` và
    `qbridge_qubit_2022` sau khi mine lại — loại `bsc_token_hub_2022__hn043`
    (1 action, ít giá trị hơn) → **273 raw cuối cùng, 0 leakage, 266
    dùng được → freeze v0.4**.

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
| Hard-negative mining — raw | 273 |
| Hard-negative mining — dùng được | 261 |
| Chain | eth, bsc, arbitrum |
| Bridge family đã verify | Ronin Bridge, BSC Token Hub, Across Protocol SpokePool (3) |
| DEX family đã verify | Uniswap V2, Uniswap V3, PancakeSwap V2, 1inch v4 (4) |
| Mixer đã verify | Tornado Cash Router (1) |
| Khoảng thời gian | 2022-03 đến 2024-11 |
| **Tổng prefix row toàn dataset** | **614** (positive: 31, negative: 583) |

Công thức prefix row/trajectory: `src/features/extractor.py::generate_prefixes`
— với trajectory `n` action, hợp 4 độ dài theo tỷ lệ (`ceil(n×0.25/0.5/0.75)`,
`n`) và 4 độ dài theo `k=2,3,5,7` (giữ nếu `k≤n`), khử trùng theo ĐỘ DÀI →
số phần tử = số prefix. `n=1` → 1 prefix; `n≥22` → tối đa 8 (trần công thức).

### Hard-negative mining theo incident positive (số liệu cuối, sau QA round 3)

| parent_incident_id | Raw | Rỗng | Dùng được | Checked (tổng qua các lần mining) |
|---|---|---|---|---|
| ronin_bridge_2022 | 69 | 4 | 65 | 88 (đã đạt target 70, -1 do QA) |
| qbridge_qubit_2022 | 34 | 0 | 34 | 100 (re-mine sau bug #2, hết candidate trong ±7 ngày) |
| feg_bridge_2024 | 31 | 0 | 31 | 100 (HẾT candidate trong ±7 ngày, không đổi qua bug #2) |
| deltaprime_arbitrum_2024 | 70 | 5 | 65 | 134 (không đổi qua bug #2) |
| bsc_token_hub_2022 | 69 | 3 | 66 | 102 (re-mine sau bug #2, đạt target 70, -1 do QA) |
| **TỔNG** | **273** | **12** | **261** | — |

`qbridge_qubit_2022` và `feg_bridge_2024` dừng ở 34/31 (thấp hơn các
incident khác) vì đã kiểm tra HẾT candidate khả dụng trong cửa sổ ±7 ngày
(`max_candidates_checked=100`, không còn candidate mới để check) —
**KHÔNG mở rộng cửa sổ thời gian cho 2 vụ này** trong lần sửa này vì tổng
đã đủ vượt ngưỡng 200 mà không cần; để dành làm hướng mở rộng nếu cần
thêm dữ liệu sau này (nới ±7 ngày thành ±14 ngày, xem
`metadata/annotation_guide.md` mục 9).

## Exclusions

- **XPEXE Bridge**: loại — không tìm được báo cáo công khai. Xem
  `experiments/logs/excluded_candidates.md`.
- **6 hard-negative bị loại qua 2 vòng QA leakage đầu** (2026-08-13):
  `ronin_bridge_2022__hn023` (×2 lần, cả 2 vòng mining),
  `deltaprime_arbitrum_2024__hn018`, `feg_bridge_2024__hn026` (×2 lần),
  `bsc_token_hub_2022__hn041` (×2 lần), `qbridge_qubit_2022__hn020`/tương
  đương — tất cả đều là hard-negative có trajectory chạm 1 trong 3 địa
  chỉ counterparty phổ biến bị nhiều nhóm khác nhau cùng chạm tới.
- **1 hard-negative bị loại qua QA leakage round 3** (sau khi mine lại
  BSC do bug #2): `bsc_token_hub_2022__hn043` (chạm cùng địa chỉ
  `0x58f876857a02d6762e0101bb5c46a8c1ed44dc16` với
  `qbridge_qubit_2022__hn027`, giữ lại bên có nhiều action hơn).
  Chi tiết đầy đủ trong git log các commit liên quan tới
  `metadata/hard_negative_registry.csv`.
- 26 candidate nhóm `CHECK_MANUALLY_non_eth_chain` phần lớn CHƯA rà soát.
- Candidate ngoài scope chain (`FTM`, `Optimism`, `Polygon`, `BASE`) loại
  hoàn toàn theo `configs/data.yaml`.

## Giới hạn đã biết

1. **`qbridge_qubit_2022`/`feg_bridge_2024` không tận dụng hết margin**
   (34/31 so với 65-66 của 3 incident khác) — đã hết candidate trong cửa
   sổ ±7 ngày hiện tại, chưa thử mở rộng cửa sổ (xem mục Coverage ở trên).
2. **12/273 hard-negative (4.4%) vẫn có trajectory rỗng** ngay cả sau khi
   sửa cả 2 bug — nguyên nhân còn lại là đặc tính hệ thống (miner check
   tương tác 2 chiều, builder chỉ trace forward), không phải bug. Xem
   `metadata/annotation_guide.md` mục 9 phần (B).
3. **`annotator_2` để trống cho TẤT CẢ 278 negative trajectory** (raw) —
   chưa qua review chéo độc lập, quy mô lớn hơn nhiều so với lúc viết
   `experiments/logs/cross_review_log.md` (viết cho 10 incident gốc).
4. **`endpoint_confirmed=False` cho 2/5 incident positive** (Ronin,
   QBridge).
5. **2 incident (FEG Bridge, QBridge) chấp nhận evidence thay thế** thay
   vì bridge+DEX sạch trong outbound trajectory — xem
   `metadata/annotation_guide.md` mục 5.
6. **[ĐÃ XỬ LÝ 2026-08-13, giữ lại để audit] Bug `traceIndex` vs
   `logIndex`** (Lịch sử sửa lỗi #4) từng bị nghi có thể ảnh hưởng âm
   thầm tới trajectory BSC build trước khi sửa — ĐÃ re-verify
   `qbridge_qubit_2022` (không đổi) và `bsc_token_hub_2022` (có đổi, do
   bug #2 mới phát hiện trong lúc re-verify, xem mục #7-#12).
7. **[MỚI] Bug `merge_events_into_semantic_actions` (Lịch sử sửa lỗi
   #9-#12)**: đã sửa cho toàn bộ mã nguồn (dùng chung mọi chain), đã
   re-mine lại toàn bộ hard-negative BSC. `ronin_bridge_2022` xác nhận
   KHÔNG đổi qua golden test (`tests/fixtures/golden/`).
   `feg_bridge_2024`/`deltaprime_arbitrum_2024` chỉ xác nhận qua so sánh
   1 lần (action count trước/sau khớp), KHÔNG có golden fixture khóa
   cứng nội dung — khuyến nghị thêm golden fixture cho các incident này
   trước khi dùng làm benchmark chính thức, để phát hiện sớm nếu 1 lần
   sửa decoder sau này vô tình đổi lại nội dung.
8. **[MỚI] `qbridge_benign_control_2022` không còn là ví dụ "cá nhân
   sạch"** — sau khi sửa bug #2, hóa ra là 1 bot PancakeSwap tự động rất
   tích cực (134 action, pattern swap liên tục rõ rệt), KHÔNG phải địa
   chỉ "ít giao dịch nhất" như lý do chọn ban đầu (dựa trên dữ liệu decode
   sai). Vẫn giữ `label=0` (không liên quan QBridge/Qubit qua bất kỳ
   nguồn nào, cấu trúc PancakeSwap swap vẫn hợp lệ làm hard-negative theo
   tiêu chí cấu trúc), nhưng người dùng downstream cần biết đây là hard-negative
   dạng "bot hoạt động mạnh", không phải "user cá nhân im lặng" như dự
   định ban đầu khi chọn.
9. **BSCTrace `fromBlock`/`toBlock`/`traceIndex` không có trong tài liệu
   công khai** dù đã xác nhận hoạt động/tồn tại thật — rủi ro thay đổi
   không báo trước từ nhà cung cấp.
10. **`data/raw/` cache phụ thuộc thời điểm crawl** (2026-08-13).

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
# xem scripts/run_hard_negative_mining.py, scripts/run_hard_negative_mining_expand.py,
# scripts/run_hard_negative_remine_bsc_after_merge_fix.py (re-mine BSC sau bug #2)

# Tính lại toàn bộ số liệu raw/usable/tổng prefix row + tỷ lệ rỗng theo incident
python scripts/compute_dataset_v0.4_stats.py

# Chạy tests xác nhận tính nhất quán + QA leakage + gate usable>=200
pytest tests/ -v
```
