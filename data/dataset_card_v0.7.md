# Dataset Card — CAGI-ED v0.7

**Ngày freeze:** 2026-08-14
**Trạng thái:** ✅ Mở rộng từ 8 → **12 positive incident** (đạt target dưới
10-15 theo tài liệu gốc mục 6.1) và hard-negative dùng được **431**
(≥200, đã verify thật).
**Bản trước:** `data/dataset_card_v0.1.md` … `data/dataset_card_v0.6.md`
(freeze thứ 6, 8 incident, 343 usable) — giữ lại nguyên trạng các bản
trước để đối chiếu/audit.

---

## Eval tier — RQ1 chính (11 incident) vs auxiliary (12 incident đầy đủ)

Sau khi freeze v0.7, rà lại chất lượng gate của `circulate_2023` (gate
YẾU NHẤT trong 12 incident — 0 action được gán nhãn chính thức
swap/bridge_deposit/mixer_or_exit trong outbound trajectory, chỉ có
evidence thay thế qua báo cáo CertiK). Quyết định (2026-08-14): **tách
`circulate_2023` khỏi vòng leave-one-incident-out CHÍNH của RQ1**, đánh
dấu `eval_tier=auxiliary_low_evidence` trong `incident_registry.csv` và
`role=auxiliary_low_evidence` trong `metadata/split_manifest.json` — giữ
nguyên dữ liệu (không xoá), dùng cho robustness/sensitivity check phụ
(VD: kiểm tra mô hình có generalize sang case "toàn transfer, không motif
rõ ràng" hay không), KHÔNG tính vào số liệu N chính thức của RQ1.

| | 12 incident đầy đủ (toàn dataset) | **11 incident (RQ1 chính)** |
|---|---|---|
| Positive incident | 12 | **11** |
| Hard-negative — raw mining | 436 | 414 |
| Hard-negative — dùng được | 426 | 404 |
| + control gốc | 5 | 5 |
| **TỔNG dùng được** | 431 | **409** |
| Tổng prefix row | 1090 | **988** |

**409 ≥ 200 → RQ1 chính vẫn đạt ngưỡng dư dả** sau khi loại `circulate_2023`.
22 hard-negative đã mine cho `circulate_2023` vẫn giữ trong
`hard_negative_registry.csv` (negative không phụ thuộc gate-strength của
positive tương ứng) nhưng KHÔNG tính vào N chính ở bảng trên (đã trừ ra
theo `parent_incident_id`).

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
| Hard-negative mining (`hard_negative_registry.csv`) | 436 | 426 |
| Hard-negative control gốc (Bước D, 5 dòng trong `incident_registry.csv`) | 5 | 5 |
| **TỔNG** | **441** | **431** |

**431 ≥ 200 → ĐẠT ngưỡng.** Dư 231 (buffer rất lớn).

## Mở rộng 8 → 12 incident (2026-08-14)

Vòng mở rộng thứ 2 (sau 5→8). Đã rà hết 19 candidate `CHECK_MANUALLY_
non_eth_chain` còn lại trong `incident_candidates_amlguard.csv`, lọc scope
chain (bsc/arbitrum) → 12 candidate khả thi. WebSearch từng vụ, chốt 4:

1. **XKingdom** (Arbitrum, 2024-01-06) — CertiK official report, exit
   scam $1.2M. 1 bridge_deposit thật qua Stargate (~100 ETH). Bằng chứng
   bổ sung ĐỘC LẬP trên chain Ethereum (cùng địa chỉ seed, EOA dùng chung
   nhiều chain): xác nhận 99.56 ETH chuyển tiếp tới địa chỉ trung gian
   CertiK nêu, deposit 453 ETH vào Tornado Cash — khớp chính xác báo cáo.
2. **Wault.Finance** (BSC, 2021-08-04) — SlowMist official report, flash
   loan arbitrage $888k. 3 swap thật (ETH→anyETH), tổng 370.65 ETH log-scale
   — khớp CHÍNH XÁC "370 BEP_ETH" SlowMist báo cáo.
3. **Paraluni** (BSC, 2022-03-13) — CertiK + SlowMist official report,
   reentrancy $1.7M. 3 swap thật qua PancakeSwap V2 (đã verify protocol
   name), tổng 1187 BNB log-scale.
4. **CirculateBUSD-CirculateWBNB** (BSC, 2023-01-12) — CertiK official
   report, exit scam $2.5M. Địa chỉ seed khớp chính xác báo cáo, nhưng
   trajectory KHÔNG có swap/bridge_deposit CHÍNH THỨC (giới hạn cấu trúc
   merge — xem bên dưới) — chấp nhận theo dạng evidence thay thế.

Loại (evidence không đủ mạnh, xem `experiments/logs/excluded_candidates.md`):
Redruby DAO (không tìm được nguồn công khai), Whale Loans (tiền vẫn nằm
nguyên trong ví attacker, không bridge/DEX/mixer tiếp theo), LianGo (địa
chỉ Heist CSV không có hoạt động on-chain nào khớp ngày báo cáo — thay
bằng CirculateBUSD-CirculateWBNB).

### Bug/giới hạn thật phát hiện khi mở rộng vòng này

1. **Data completeness gap ở `qbridge_qubit_2022`** (phát hiện tình cờ
   khi điều tra QA leak cho Paraluni): cache gốc thiếu 3 giao dịch thật
   nằm HOÀN TOÀN trong cửa sổ 72h chính thức — đã sửa, rebuild
   `qbridge_qubit_2022` 22 → **25 action**, cập nhật golden fixture. Xem
   `metadata/annotation_guide.md` mục 13.
2. **Giới hạn kiến trúc AnySwap burn-to-bridge (2021-2023)**: cơ chế bridge
   đời đầu chuyển token VỀ ĐỊA CHỈ NULL kèm external call giá trị=0 tới
   contract bridge thật — `decode_bsctrace_transfer_row` bỏ qua hoàn toàn
   external call giá trị=0, nên KHÔNG gán được `bridge_deposit` tự động
   cho `wault_finance_2021`/`circulate_2023` dù cơ chế bridge THẬT đã xác
   nhận qua on-chain (Multichain Router V4/anyETH Token, verify độc lập).
   CHƯA sửa (phạm vi hẹp, chỉ ảnh hưởng pattern burn cũ, không ảnh hưởng
   Stargate/Multichain-V6/LiFi).
3. **Giới hạn cấu trúc `merge_events_into_semantic_actions` cho swap có
   leg "hoàn trả nhỏ" từ router** (`circulate_2023`): tx PancakeSwap V2
   thật có 3 địa chỉ tham gia (seed, router, LP pool) do router hoàn trả
   dust riêng — vượt giới hạn `srcs<=2` của điều kiện 'swap', không được
   gộp thành 1 action swap dù là swap thật. CHƯA sửa.

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
| Hard-negative mining — dùng được | 426 |
| Chain | eth, bsc, arbitrum |
| Bridge family đã verify | 9: Ronin Bridge, Wormhole, Stargate, Multichain V4/V6/anyETH-legacy, BSC Token Hub, LI.FI Diamond, Across Protocol SpokePool |
| DEX family đã verify | 4: Uniswap V2, Uniswap V3, PancakeSwap V2, 1inch v4 |
| Mixer đã verify | Tornado Cash Router (1) |
| Lending protocol đã verify | Venus Protocol (1) |
| Khoảng thời gian | 2021-08 đến 2024-11 |
| **Tổng prefix row toàn dataset** | **1090** (positive: 66, negative: 1024) |

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
| xkingdom_2024 | 22 | 0 | 22 | 23 |
| wault_finance_2021 | 22 | 0 | 22 | 85 (fallback PancakeSwap V2) |
| paraluni_2022 | 22 | 0 | 22 | 79 |
| circulate_2023 | 22 | 0 | 22 | 91 (fallback PancakeSwap V2) |
| **TỔNG** | **436** | **10** | **426** | — |

`wault_finance_2021`/`circulate_2023` ban đầu KHÔNG mine được ứng viên nào
(contract mining gốc — anyETH Token legacy 2021 / Multichain Router V4
legacy 2023 — quá ít giao dịch còn lại tính đến 2026) — đã thêm PancakeSwap
V2 làm nguồn fallback, đạt target 22/22 sau đó. Trong quá trình mining
gặp lỗi rate-limit từ BSCTrace API (key cũ hết quota giữa chừng) — đã thay
key mới, mining lại thành công, không mất dữ liệu (script ghi kết quả
ngay sau mỗi incident, không đợi đến cuối).

## Exclusions

- **XPEXE Bridge, Redruby DAO**: loại — không tìm được báo cáo công khai.
- **Whale Loans**: loại — CertiK xác nhận exploit thật nhưng tiền vẫn nằm
  nguyên trong ví attacker, không có bridge/DEX/mixer tiếp theo.
- **LianGo**: loại — địa chỉ Heist trong CSV không có hoạt động on-chain
  khớp ngày báo cáo, không xác nhận độc lập được. Thay bằng
  CirculateBUSD-CirculateWBNB.
- **Radiant Capital (Jan 2024), Magic/Treasure DAO (2025-03-25)**: loại từ
  vòng mở rộng trước (5→8) — vẫn giữ nguyên, không xét lại.
- **10 hard-negative bị loại qua các vòng QA leakage trước** (2026-08-13):
  cùng nhóm địa chỉ counterparty phổ biến tái diễn (`0x74de5d4f...`,
  `0xb4a8d456...`, `0x58f876...`, `0xe37e799d...`). **Vòng QA leakage lần
  này (12 group, 436 hard-negative mới) — SẠCH, không phát hiện leak mới,
  không cần loại thêm.**
- 7 candidate ngoài scope chain (`FTM`, `Optimism`, `Polygon`, `BASE`)
  loại hoàn toàn theo `configs/data.yaml`.

## Giới hạn đã biết

1. **`circulate_2023` có gate YẾU NHẤT trong 12 incident** — không có
   swap/bridge_deposit chính thức trong trajectory (chỉ evidence thay
   thế qua báo cáo CertiK + dữ liệu on-chain thật nhưng bị giới hạn cấu
   trúc merge bỏ lỡ). Xem mục "Bug/giới hạn thật" ở trên.
2. **`wault_finance_2021`/`circulate_2023` không có `bridge_deposit`
   chính thức** do giới hạn kiến trúc AnySwap burn-to-bridge đời đầu —
   CHƯA sửa (phạm vi hẹp).
3. **26/348 hard-negative (7.4%, tính cả 8 incident cũ) vẫn có trajectory
   rỗng** — đặc tính hệ thống, không phải bug. 10/436 tính riêng vòng mở
   rộng này (2.3%).
4. **`annotator_2` để trống cho TẤT CẢ 441 negative trajectory** (raw).
5. **`endpoint_confirmed=False` cho 2/12 incident positive** (Ronin,
   QBridge).
6. **5 incident chấp nhận evidence thay thế** (không có bridge+DEX sạch
   trong outbound trajectory): FEG Bridge, QBridge (từ vòng trước),
   XKingdom, Wault.Finance, CirculateBUSD (mới) — xem
   `metadata/annotation_guide.md` mục 5, 13.
7. **[ĐÃ XỬ LÝ, giữ lại để audit] 4 bug liên tiếp trong tầng decode/merge
   cho 8 incident đầu** — đã sửa cả 4, golden fixture cho 7/12 incident
   (`ronin_bridge_2022`, `qbridge_qubit_2022`, `bsc_token_hub_2022`,
   `chibi_finance_2023`, `wooppv2_2024`, `utopiasphere_2024`, và 4 incident
   mới nhất). `feg_bridge_2024`/`deltaprime_arbitrum_2024` vẫn chưa có
   golden fixture khóa cứng (chỉ so sánh action count 1 lần).
8. **[MỚI] Data completeness gap đã phát hiện 1 lần ở `qbridge_qubit_2022`**
   — không loại trừ khả năng CÁC địa chỉ dùng chung khác (ở incident khác)
   cũng có cache gốc thiếu tương tự, chưa rà soát toàn bộ.
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
# xem scripts/run_hard_negative_mining_v07_new_incidents.py,
# scripts/run_hard_negative_mining_v07_retry.py (4 incident mới nhất)

# Tính lại toàn bộ số liệu raw/usable/tổng prefix row + tỷ lệ rỗng theo incident
python scripts/compute_dataset_v0.7_stats.py

# Chạy tests xác nhận tính nhất quán + QA leakage + gate usable>=200 + golden fixtures
pytest tests/ -v
```
