# Dataset Card — CAGI-ED v0.2 (ĐANG BỔ SUNG — CHƯA ĐẠT NGƯỠNG)

**Ngày cập nhật:** 2026-08-13
**Trạng thái:** ⚠️ **KHÔNG đạt ngưỡng "≥200 hard-negative dùng được"**. Đây
là bản v0.2 giữa chừng, đang trong quá trình mining bổ sung — CHƯA phải bản
freeze cuối. Số liệu trước đó (208 "đạt ngưỡng") **SAI** vì đếm cả 17 hard-
negative có trajectory rỗng (0 action, 0 prefix row) — đã phát hiện và sửa
2026-08-13.

**QUY ƯỚC BẮT BUỘC từ đây trở đi — 2 con số riêng biệt, không gộp chung:**
- **"raw mining"**: số dòng có mặt trong `hard_negative_registry.csv` (đã
  pass tiêu chí lọc của miner ở mức giao dịch).
- **"dùng được"**: số dòng trong đó, khi build lại bằng
  `expand_and_build_trajectory` (áp `min_tainted_share`/`time_horizon_hours`
  chuẩn), sinh ra trajectory **KHÔNG rỗng** (≥1 action → ≥1 prefix row).
  Đây là con số quyết định có đạt ngưỡng ≥200 hay không, KHÔNG phải raw
  mining.

| | raw mining | dùng được (≥1 prefix row) |
|---|---|---|
| Hard-negative mining (208 dòng trong registry) | 208 | 191 |
| Hard-negative control gốc (Bước D, 5 dòng) | 5 | 5 |
| **TỔNG** | **213** | **196** |

**196 < 200 → CHƯA đạt ngưỡng.** Thiếu 4.

**Bản trước:** `data/dataset_card_v0.1.md` (giữ nguyên để đối chiếu/audit —
v0.1 chỉ có 9 negative prefix row, KHÔNG đạt ngưỡng 200).

---

## Thay đổi so với v0.1

v0.1 mining theo tỷ lệ 1 hard-negative/1 incident (5 incident positive → 5
hard-negative). v0.2 mở rộng: khai thác **quần thể benign user** đã tương
tác với cùng contract bridge/DEX/mixer đã verify liên quan tới mỗi incident
positive, trong khung ±7 ngày quanh incident — xem
`src/collect/hard_negative_miner.py` và `metadata/annotation_guide.md`.

## Nguồn dữ liệu

- **Danh sách seed ứng viên**: `metadata/incident_candidates_amlguard.csv`
  (82 dòng công khai: thời gian, chain, tên vụ, địa chỉ, block) — **CHỈ
  dùng để tra cứu**, KHÔNG dùng ground truth AMLGuard (chưa công khai).
- **Ground truth**: `self_annotated` — mọi trajectory/nhãn tự dựng từ dữ
  liệu on-chain thật (Etherscan API V2, BSCTrace/MegaNode) + đối chiếu báo
  cáo công khai độc lập (CertiK, SlowMist, Halborn, Merkle Science, Elliptic,
  Nansen, crypto.news, và các nguồn tin tức uy tín khác — xem `source_url`
  trong `metadata/incident_registry.csv`).
- **Hard-negative mining**: `metadata/hard_negative_registry.csv` — mỗi
  dòng map tới `parent_incident_id` (incident positive gốc dùng để tìm
  contract mining). Tiêu chí lọc: cùng chain, cùng protocol (đã verify),
  trong khung ±7 ngày quanh incident, không mixer_or_exit bất thường, không
  fan-out kiểu split (>3 counterparty riêng biệt), volume > 0. Loại trừ:
  seed address của mọi incident, địa chỉ trong danh sách AMLGuard candidates
  (82 dòng), địa chỉ đã dùng cho incident/hard-negative khác.
- **Bridge/DEX/mixer protocol contracts**: xác nhận qua on-chain thật
  (function signature, khớp số tiền chính xác với báo cáo công khai), ghi
  trong `metadata/protocol_map.yaml`. Không suy đoán từ tên/memory — xem
  `metadata/annotation_guide.md` mục 1.

## Coverage

| Thuộc tính | Giá trị |
|---|---|
| Số dòng `incident_registry.csv` | 10 (5 positive + 5 hard-negative control gốc) — **KHÔNG phải 10 positive** |
| Số dòng positive (`label=1`) | 5: ronin_bridge_2022, qbridge_qubit_2022, feg_bridge_2024, deltaprime_arbitrum_2024, bsc_token_hub_2022 |
| Số dòng hard-negative mining (raw, `hard_negative_registry.csv`) | 208 |
| Số hard-negative mining "dùng được" (≥1 prefix row) | 191 |
| Chain | eth, bsc, arbitrum |
| Bridge family đã verify | Ronin Bridge, BSC Token Hub, Across Protocol SpokePool (3) |
| DEX family đã verify | Uniswap V2, Uniswap V3, PancakeSwap V2, 1inch v4 (4) |
| Mixer đã verify | Tornado Cash Router (1) |
| Khoảng thời gian | 2022-03 đến 2024-11 |
| **Tổng prefix row toàn dataset (25/50/75/100% + k=2,3,5,7)** | **457** = 30 (5 positive) + 9 (5 hard-negative control gốc) + 418 (191 hard-negative mining dùng được; 17 dòng rỗng đóng góp 0, đã trừ sẵn) |

Công thức prefix row/trajectory: xem `src/features/extractor.py::generate_prefixes`
— với trajectory `n` action, hợp 4 độ dài theo tỷ lệ (`ceil(n×0.25/0.5/0.75)`,
`n`) và 4 độ dài theo `k=2,3,5,7` (giữ nếu `k≤n`), khử trùng theo ĐỘ DÀI (không
phải nhãn) → số phần tử = số prefix. Trajectory `n=1` luôn cho đúng 1 prefix
(mọi mốc tỷ lệ đều làm tròn về 1, mọi k>1 bị loại); `n≥22` cho tối đa 8
(trần của công thức, 4 tỷ lệ + 4 k không còn trùng độ dài).

### Hard-negative mining theo incident positive

| parent_incident_id | Mục tiêu | Raw mining | Dùng được (≥1 prefix) | Rỗng | Tỷ lệ rỗng | Checked |
|---|---|---|---|---|---|---|
| ronin_bridge_2022 | 45 | 44 | 41 | 3 | 6.8% | 59 |
| qbridge_qubit_2022 | 45 | 44 | 38 | 6 | 13.6% | 100 (hết candidate) |
| feg_bridge_2024 | 45 | 31 | 31 | 0 | 0.0% | 100 (hết candidate) |
| deltaprime_arbitrum_2024 | 45 | 44 | 41 | 3 | 6.8% | 80 |
| bsc_token_hub_2022 | 45 | 45 | 40 | 5 | 11.1% | 64 |
| **TỔNG** | **225** | **208** | **191** | **17** | **8.2%** | 403 |

Ghi chú: tỷ lệ rỗng KHÔNG đồng đều (0.0%–13.6%), không phải hằng số ~8% ở
mọi nhóm — xem chẩn đoán chi tiết ở mục "Giới hạn đã biết" #1 và
`metadata/annotation_guide.md`. `qbridge_qubit_2022` và `feg_bridge_2024`
không đạt target raw 45 dù đã kiểm tra hết `max_candidates_checked=100` —
KHÔNG hạ tiêu chí lọc để ép đủ.

## Exclusions

- **XPEXE Bridge** (candidate STRONG_CANDIDATE_bridge_in_name, ETH,
  2025-01-25): loại — không tìm được bất kỳ báo cáo công khai nào xác
  nhận incident. Xem `experiments/logs/excluded_candidates.md`.
- **3 hard-negative bị loại sau QA leakage check** (2026-08-13):
  `ronin_bridge_2022__hn023` (trùng address với `ronin_benign_control_2022`),
  `deltaprime_arbitrum_2024__hn018` và `feg_bridge_2024__hn026` (trùng
  cùng 1 hex address xuất hiện độc lập trên 2 chain khác nhau — có thể
  cùng 1 EOA controlled bởi 1 private key hoạt động trên cả eth và
  arbitrum). Giữ `deltaprime_arbitrum_2024__hn043` (chủ sở hữu thật của
  address đó, seed hợp lệ) — xem lý do chi tiết trong git log.
- 26 candidate nhóm `CHECK_MANUALLY_non_eth_chain` phần lớn CHƯA được rà
  soát hết — cơ hội mở rộng dataset trong tương lai.
- Candidate trên chain ngoài scope (`FTM`, `Optimism`, `Polygon`, `BASE`)
  bị loại hoàn toàn theo `configs/data.yaml`.

## Giới hạn đã biết

1. **17/208 hard-negative (8.2%) có trajectory rỗng** khi build lại bằng
   `time_horizon_hours=72`/`min_tainted_share` chuẩn — bộ lọc structural
   của miner (khung ±7 ngày, chỉ check fan-out/mixer/volume>0, KHÔNG áp
   `min_tainted_share`) nhẹ hơn builder chuẩn (`min_tainted_share` +
   `time_horizon_hours` + allowlist). Tỷ lệ rỗng KHÔNG đồng đều giữa các
   incident (0.0%–13.6%) — xem chẩn đoán chi tiết trong
   `metadata/annotation_guide.md` mục 9. Các dòng rỗng vẫn giữ trong
   `hard_negative_registry.csv` (hợp lệ theo tiêu chí mining) nhưng KHÔNG
   đóng góp prefix row — đã trừ khỏi tổng 457 và khỏi con số "dùng được".
2. **KHÔNG đạt ngưỡng ≥200 hard-negative dùng được** (196/200, thiếu 4) —
   xem bảng đầu file. Đang trong quá trình mining bổ sung có buffer
   (mục tiêu mới: 220-230 dùng được) trước khi freeze v0.2 chính thức.
3. **`annotator_2` để trống cho TẤT CẢ 213 negative trajectory** — chưa
   qua review chéo độc lập. Xem `experiments/logs/cross_review_log.md`
   (viết cho v0.1, vẫn áp dụng nguyên cho v0.2 — quy mô review cần thiết
   giờ lớn hơn nhiều).
4. **`endpoint_confirmed=False` cho 2/5 incident positive** (Ronin,
   QBridge) — chưa trace được tới mixer/exit-service cuối cùng.
5. **2 incident (FEG Bridge, QBridge) chấp nhận evidence thay thế** thay
   vì bridge+DEX sạch trong outbound trajectory — xem
   `metadata/annotation_guide.md` mục 5.
6. **BSCTrace `fromBlock`/`toBlock` không có trong tài liệu công khai**
   dù đã xác nhận hoạt động thật — rủi ro thay đổi không báo trước từ nhà
   cung cấp. Bug thật liên quan đã sửa 2026-08-13: `collect_address_raw_data`
   ban đầu không dùng tham số này cho BSC, khiến cache một số contract chỉ
   phủ block rất cũ (1-1,021,501) thay vì đúng khung cần thiết.
7. **Hard-negative mining chỉ dùng 1 khung ±7 ngày cố định** (hoặc "chỉ
   trước" cho BSC Token Hub) — chưa thử các khung thời gian khác để tăng
   thêm pass rate cho `qbridge_qubit_2022`/`feg_bridge_2024`.
8. **`data/raw/` cache phụ thuộc thời điểm crawl** (2026-08-13) — dữ liệu
   on-chain bất biến nên không "cũ đi", nhưng API rate limit/pricing có
   thể đã thay đổi nếu crawl lại.

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

# Chạy lại toàn bộ mining hard-negative (dùng cache đã có, không gọi mạng)
# xem scripts/run_hard_negative_mining.py để chỉnh do_collect=False

# Chạy tests xác nhận tính nhất quán + QA leakage
pytest tests/ -v
```
