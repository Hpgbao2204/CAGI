# Dataset Card — CAGI-ED v0.8

**Ngày freeze:** 2026-08-14
**Trạng thái:** ✅ Sửa 6 bug hệ thống trong tầng cache/pagination + allowlist
(phát hiện khi rà soát cache completeness cho 11 incident "primary" theo yêu
cầu người dùng), rebuild SẠCH toàn bộ 16 dòng registry (11 positive + 5
control gốc, chưa tính `circulate_2023` auxiliary), cập nhật 10 golden
fixture, hard-negative dùng được **430** (12 incident đầy đủ) / **408**
(11 incident RQ1 chính) — cả 2 đều ≥200.
**Bản trước:** `data/dataset_card_v0.1.md` … `data/dataset_card_v0.7.md`
(freeze v0.7, 12 incident, 431 usable) — giữ lại nguyên trạng các bản
trước để đối chiếu/audit.

---

## [MỚI] Rà soát cache/pagination hệ thống 2026-08-14 — 6 bug thật, đã sửa

Theo yêu cầu người dùng sau freeze v0.7 ("rà soát hệ thống cache/pagination
cho 11 incident primary còn lại, ngay bây giờ"), phát hiện phạm vi lớn hơn
nhiều so với 1 vụ lẻ (`qbridge_qubit_2022`, đã fix ở v0.7). **6/16 dòng
primary** ban đầu cho thấy thay đổi số lượng action khi re-fetch với cửa sổ
rộng hơn — điều tra sâu hơn phát hiện đây là **6 bug độc lập** trong tầng
cache/pagination + allowlist, không phải 1 bug đơn lẻ:

1. **`_load_cached_rows` (eth/arbitrum) thiếu dedup** theo `(hash,
   logIndex)` — khác với `_load_cached_bsctrace_rows` (BSC) đã dedup từ
   trước. Khi có ≥2 file cache cửa sổ chồng lấn cho cùng 1 địa chỉ, giao
   dịch trùng bị nạp 2 lần, làm sai `merge_events_into_semantic_actions`
   (vd amount_norm tính sai do nhân đôi leg). **Đã sửa**: thêm dedup.
2. **2 client (Etherscan + BSCTrace) không tự dọn cache cũ trước khi fetch
   lại** — cache tích luỹ nhiều "thế hệ" file chồng lấn qua các lần chạy
   khác nhau (vd audit script tạo file cửa sổ rộng cạnh file cũ). **Đã
   sửa**: cả 2 client giờ xoá sạch file cache cũ của (address, action)
   trước khi ghi file mới ("wipe-before-write") — đảm bảo chỉ có ĐÚNG 1
   thế hệ cache tại 1 thời điểm.
3. **Địa chỉ 1inch v4 AggregationRouter trong `protocol_map.yaml`/
   `configs/data.yaml` bị THIẾU 1 KÝ TỰ CUỐI** (`...097` thay vì `...097d`,
   39 hex thay vì 40) — so sánh chuỗi trong `known_protocol_allowlist`
   không bao giờ khớp, khiến trajectory builder coi 1inch là ví thường và
   mở rộng frontier VÀO router (hàng triệu giao dịch không liên quan) →
   nổ trajectory. Phát hiện qua `ronin_bridge_2022` (vụ pilot gốc): 7→25
   action khi rebuild sạch trước khi sửa. **Đã sửa** + xác nhận lại qua
   Etherscan (nhãn "Aggregation Router V4").
4. **Thiếu 2 địa chỉ hạ tầng DEX thật trong allowlist**, gây nổ trajectory
   tương tự bug #3: `0x88e6a0c2...` (nhãn công khai "Uniswap V3: USDC 3",
   pool thật, eth) và `0xdef171fe...` (nhãn công khai "Velora v5: Augustus
   Swapper" / ParaSwap, DEX aggregator ~1.7 triệu giao dịch, bsc). Cả 2 xác
   nhận qua WebSearch, **đã bổ sung** vào `protocol_map.yaml`/
   `configs/data.yaml`.
5. **`frontier` dùng set-comprehension** (`{a.dst for a in traj.actions}`)
   — thứ tự lặp của Python set phụ thuộc hash-seed ngẫu nhiên, KHÁC NHAU
   giữa các lần chạy process riêng biệt, khiến thứ tự xử lý địa chỉ không
   ổn định → có thể ảnh hưởng kết quả merge. **Đã sửa**: dùng
   `dict.fromkeys(...)` để khử trùng lặp NHƯNG giữ đúng thứ tự xuất hiện
   đầu tiên (ổn định, tái lập được).
6. **Cache theo (chain, address) không phân biệt incident/cửa sổ thời
   gian** (kiến trúc gốc, chưa sửa triệt để): khi 2 incident khác nhau
   dùng chung 1 địa chỉ (hạ tầng phổ biến, không phải leak thật — xem mục
   Exclusions) nhưng cần cửa sổ khác nhau, ai fetch SAU sẽ "thắng"/ghi đè
   cache của người trước. Ảnh hưởng `qbridge_qubit_2022` ↔ `paraluni_2022`
   (địa chỉ `0xdd90e5e8...`, xác nhận là CEX/OTC hot wallet phổ biến, 481
   gửi/789 nhận độc lập — không phải leak). **Xử lý thực dụng**: chốt 1 thứ
   tự fetch cuối cùng cố định (paraluni/utopiasphere trước, qbridge_qubit
   sau cùng), freeze kết quả ở trạng thái đó, KHÔNG fetch lại các địa chỉ
   này nữa. Giới hạn kiến trúc còn tồn tại — xem mục Giới hạn.

### Ngoài phạm vi cache: 2 nguồn phi-quyết-định (non-determinism) khác

Sau khi sửa 6 bug trên, `wault_finance_2021` và `paraluni_2022` vẫn cho số
action HƠI khác nhau (dao động vài action) giữa các lần fetch/rebuild riêng
biệt. Điều tra xác nhận nguyên nhân: 2 địa chỉ trong 2 incident này
(`0xc1e16013...`, `0xf2ce52e3...`) là địa chỉ RẤT nhiều giao dịch, chạm gần
tới giới hạn phân trang 100 trang của BSCTrace API — pagination cho địa chỉ
"hot" như vậy có sai số nhỏ tự nhiên giữa các lần gọi API thật (không phải
bug code, giới hạn của nguồn dữ liệu). **Đã chốt 1 kết quả ổn định** (xác
nhận lặp lại 2 lần liên tiếp không đổi) làm golden fixture chính thức, ghi
rõ giới hạn này trong mục Giới hạn.

### Kết quả cụ thể (before → after, sau khi sửa cả 6 bug)

| incident_id | action trước (v0.7) | action sau (v0.8) | Ghi chú |
|---|---|---|---|
| `ronin_bridge_2022` | 7 | **113** | Vụ pilot gốc — nổ lớn nhất, do bug #3 (1inch) + #4 (Uniswap V3 pool) |
| `ronin_benign_control_2022` | 1 | **18** | +2 provenance event thật (Ronin Bridge) bị bỏ sót trước đây |
| `qbridge_qubit_2022` | 25 (đã fix ở v0.7) | **52** | Bug #4 (Velora) + #6 (thứ tự fetch địa chỉ dùng chung) |
| `bsc_token_hub_2022` | 66 | **74** | Bug #1/#2/#4 |
| `chibi_finance_2023` | 6 | **16** | Bug #1/#2 |
| `utopiasphere_2024` | 13 | **17** | Bug #1/#2/#4 |
| `wault_finance_2021` | 6 | **15** | Bug #1/#2, xem thêm mục non-determinism |
| `paraluni_2022` | 16 | **23** | Bug #1/#2/#4/#6 |
| `wooppv2_2024`, `xkingdom_2024`, `feg_bridge_2024`, `deltaprime_arbitrum_2024` | không đổi | không đổi | Đã xác nhận SẠCH qua audit — không bị ảnh hưởng bởi 6 bug trên |

Toàn bộ thay đổi đã đối chiếu tx-level: các action mới đều là giao dịch
thật, nằm trong cửa sổ hợp lệ của incident (không phải nhiễu từ mở rộng cửa
sổ), xác nhận qua Etherscan/BscScan (nhãn contract) hoặc qua chính cấu trúc
dữ liệu on-chain (provenance bridge event cùng seed).

---

## Eval tier — RQ1 chính (11 incident) vs auxiliary (12 incident đầy đủ)

*(không đổi kể từ v0.7 — `circulate_2023` vẫn `eval_tier=auxiliary_low_evidence`,
không tính vào N chính của RQ1, xem lý do ở `data/dataset_card_v0.7.md`)*

| | 12 incident đầy đủ (toàn dataset) | **11 incident (RQ1 chính)** |
|---|---|---|
| Positive incident | 12 | **11** |
| Hard-negative — raw mining | 436 | 414 |
| Hard-negative — dùng được | 425 | 403 |
| + control gốc | 5 | 5 |
| **TỔNG dùng được** | 430 | **408** |
| Tổng prefix row | 1104 (positive: 79, negative: 1025) | **1002** (positive: 75, negative: 927) |

**408 ≥ 200 → RQ1 chính vẫn đạt ngưỡng dư dả** sau khi loại `circulate_2023`.

---

## QUY ƯỚC BẮT BUỘC — 2 con số riêng biệt, không gộp chung

- **"raw mining"**: số dòng có mặt trong `hard_negative_registry.csv` (đã
  pass tiêu chí lọc CỦA MINER ở mức giao dịch — `_passes_structural_filter`,
  không áp `min_tainted_share`/`time_horizon_hours`).
- **"dùng được"**: số dòng trong đó, khi build lại bằng
  `expand_and_build_trajectory` (áp `min_tainted_share`/`time_horizon_hours`
  chuẩn — bộ lọc CHẶT HƠN miner, dùng `max_iterations=None` tức
  `config.max_depth=6`, KHÔNG cap thủ công), sinh ra trajectory KHÔNG rỗng
  (≥1 action → ≥1 prefix row). **Đây là con số quyết định có đạt ngưỡng
  ≥200 hay không.**

| | raw mining | dùng được (≥1 prefix row) |
|---|---|---|
| Hard-negative mining (`hard_negative_registry.csv`) | 436 | 425 |
| Hard-negative control gốc (Bước D, 5 dòng trong `incident_registry.csv`) | 5 | 5 |
| **TỔNG** | **441** | **430** |

**430 ≥ 200 → ĐẠT ngưỡng.** Dư 230 (buffer rất lớn).

> **Lưu ý quan trọng so với v0.7**: số "dùng được" của hard-negative mining
> giảm nhẹ (426 → 425) vì trajectory build lại với dữ liệu/allowlist đúng
> hơn khiến 1 candidate trước đây "dùng được" (nhờ dữ liệu thiếu sót tình
> cờ tạo ra action) nay build lại đúng thành rỗng. Đây là kết quả CHÍNH
> XÁC HƠN, không phải hồi quy — luôn ưu tiên đúng hơn là số đẹp.

## Mở rộng 8 → 12 incident (2026-08-14) — nội dung gốc, không đổi

*(xem `data/dataset_card_v0.7.md` để biết chi tiết đầy đủ 4 candidate mới:
XKingdom, Wault.Finance, Paraluni, CirculateBUSD — không lặp lại ở đây)*

### Giới hạn kiến trúc đã biết từ trước, vẫn CHƯA sửa (không đổi so với v0.7)

1. **Giới hạn kiến trúc AnySwap burn-to-bridge (2021-2023)**: `wault_finance_2021`/
   `circulate_2023` không có `bridge_deposit` tự động — `decode_bsctrace_transfer_row`
   bỏ qua external call giá trị=0.
2. **Giới hạn cấu trúc `merge_events_into_semantic_actions`** cho swap có
   leg "hoàn trả nhỏ" từ router (`circulate_2023`, srcs>2).

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
  (>3 counterparty riêng biệt), volume > 0.
- **Bridge/DEX/mixer/lending protocol contracts**: xác nhận qua on-chain
  thật, ghi trong `metadata/protocol_map.yaml`. Không suy đoán từ
  tên/memory — xem `metadata/annotation_guide.md` mục 1.

## Coverage

| Thuộc tính | Giá trị |
|---|---|
| Số dòng `incident_registry.csv` | 17 (12 positive + 5 hard-negative control gốc) |
| Số dòng positive (`label=1`) | 12: ronin_bridge_2022, qbridge_qubit_2022, feg_bridge_2024, deltaprime_arbitrum_2024, bsc_token_hub_2022, chibi_finance_2023, wooppv2_2024, utopiasphere_2024, xkingdom_2024, wault_finance_2021, paraluni_2022, circulate_2023 |
| Hard-negative mining — raw | 436 |
| Hard-negative mining — dùng được | 425 |
| Chain | eth, bsc, arbitrum |
| Bridge family đã verify | 9: Ronin Bridge, Wormhole, Stargate, Multichain V4/V6/anyETH-legacy, BSC Token Hub, LI.FI Diamond, Across Protocol SpokePool |
| DEX family đã verify | 6: Uniswap V2, Uniswap V3 (SwapRouter + USDC 3 pool), PancakeSwap V2, 1inch v4, Velora v5/ParaSwap Augustus Swapper |
| Mixer đã verify | Tornado Cash Router (1) |
| Lending protocol đã verify | Venus Protocol (1) |
| Khoảng thời gian | 2021-08 đến 2024-11 |
| **Tổng prefix row toàn dataset** | **1104** (positive: 79, negative: 1025) |

Công thức prefix row/trajectory: `src/features/extractor.py::generate_prefixes`
— với trajectory `n` action, hợp 4 độ dài theo tỷ lệ (`ceil(n×0.25/0.5/0.75)`,
`n`) và 4 độ dài theo `k=2,3,5,7` (giữ nếu `k≤n`), khử trùng theo ĐỘ DÀI →
số phần tử = số prefix. `n=1` → 1 prefix; `n≥22` → tối đa 8 (trần công thức).

## Exclusions

- **XPEXE Bridge, Redruby DAO**: loại — không tìm được báo cáo công khai.
- **Whale Loans**: loại — CertiK xác nhận exploit thật nhưng tiền vẫn nằm
  nguyên trong ví attacker, không có bridge/DEX/mixer tiếp theo.
- **LianGo**: loại — địa chỉ Heist trong CSV không có hoạt động on-chain
  khớp ngày báo cáo, không xác nhận độc lập được. Thay bằng
  CirculateBUSD-CirculateWBNB.
- **Radiant Capital (Jan 2024), Magic/Treasure DAO (2025-03-25)**: loại từ
  vòng mở rộng trước (5→8) — vẫn giữ nguyên, không xét lại.
- **`0x0000000000000000000000000000000000000000` (null/burn), `0xdd90e5e8...`
  (CEX/OTC hot wallet dùng chung, 481 gửi/789 nhận độc lập), `0x88e6a0c2...`
  (Uniswap V3 pool), `0xdef171fe...` (Velora/ParaSwap router)**: loại khỏi
  QA leakage check — hạ tầng dùng chung xác nhận qua on-chain/WebSearch,
  không phải 1 thực thể/counterparty phân biệt được cho leave-one-group-out.
- 7 candidate ngoài scope chain (`FTM`, `Optimism`, `Polygon`, `BASE`)
  loại hoàn toàn theo `configs/data.yaml`.

## Giới hạn đã biết

1. **`circulate_2023` có gate YẾU NHẤT trong 12 incident** — đã tách
   `eval_tier=auxiliary_low_evidence`, không tính vào RQ1 chính.
2. **`wault_finance_2021`/`circulate_2023` không có `bridge_deposit`
   chính thức** do giới hạn kiến trúc AnySwap burn-to-bridge đời đầu —
   CHƯA sửa (phạm vi hẹp).
3. **[MỚI v0.8] Kiến trúc cache theo (chain, address) không phân biệt
   incident/cửa sổ thời gian** — khi 2 incident dùng chung 1 địa chỉ hạ
   tầng phổ biến với cửa sổ khác nhau, kết quả phụ thuộc THỨ TỰ fetch gần
   nhất (đã chốt cố định cho `qbridge_qubit_2022`/`paraluni_2022`, xem mục
   rà soát cache ở trên). Sửa triệt để cần cache scoped theo
   (incident_id, address, window) — để lại cho công việc sau, phạm vi lớn
   (yêu cầu re-mine phần lớn hard-negative BSC).
4. **[MỚI v0.8] `wault_finance_2021`/`paraluni_2022` có 1-2 địa chỉ rất
   nhiều giao dịch, chạm gần giới hạn phân trang BSCTrace (100 trang)** —
   số action có sai số nhỏ tự nhiên giữa các lần gọi API thật khác nhau
   (giới hạn nguồn dữ liệu, không phải bug). Đã chốt 1 kết quả ổn định
   (xác nhận lặp lại) làm golden fixture.
5. **`annotator_2` để trống cho TẤT CẢ 441 negative trajectory** (raw).
6. **`endpoint_confirmed=False` cho 2/12 incident positive** (Ronin,
   QBridge).
7. **5 incident chấp nhận evidence thay thế** (không có bridge+DEX sạch
   trong outbound trajectory): FEG Bridge, QBridge, XKingdom, Wault.Finance,
   CirculateBUSD — xem `metadata/annotation_guide.md` mục 5, 13.
8. **[ĐÃ XỬ LÝ v0.8] Rà soát cache/pagination hệ thống cho 15/16 dòng
   primary** (trừ `qbridge_qubit_2022` đã fix riêng ở v0.7) — phát hiện +
   sửa 6 bug (xem mục đầu dataset card). `circulate_2023` (auxiliary,
   BSC) CHƯA được rà soát trong đợt này (ưu tiên thấp, không tính vào RQ1
   chính).
9. **BSCTrace `fromBlock`/`toBlock`/`traceIndex` không có trong tài liệu
   công khai** dù đã xác nhận hoạt động/tồn tại thật.
10. **`data/raw/` cache phụ thuộc thời điểm crawl** (2026-08-13/14).
11. **Multichain (AnySwap) — cả 3 phiên bản đã gặp (anyETH Token 2021,
    Router V4 2023, Router V6 2023) đều thuộc protocol ĐÃ NGỪNG HOẠT ĐỘNG**
    từ giữa 2023 (sau vụ bắt giữ CEO) — chỉ dùng để đối chiếu lịch sử.

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

# Chạy lại mining hard-negative (do_collect=False dùng cache, hoặc
# do_collect=True cần BSCTRACE_API_KEY/ETHERSCAN_API_KEY trong .env)

# Tính lại toàn bộ số liệu raw/usable/tổng prefix row + tỷ lệ rỗng theo incident
python scripts/compute_dataset_v0.8_stats.py

# Chạy tests xác nhận tính nhất quán + QA leakage + gate usable>=200 + golden fixtures
pytest tests/ -v
```
