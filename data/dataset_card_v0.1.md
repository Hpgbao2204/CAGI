# Dataset Card — CAGI-ED v0.1

**Ngày freeze:** 2026-08-13
**Trạng thái:** ⚠️ Proof-of-concept, KHÔNG đạt đủ ngưỡng "≥200 hard-negative"
(xem mục "Giới hạn đã biết" — quyết định freeze có ghi chú rõ, không phải
đạt đầy đủ mọi tiêu chí data gate).

---

## Nguồn dữ liệu

- **Danh sách seed ứng viên**: `metadata/incident_candidates_amlguard.csv`
  (82 dòng công khai: thời gian, chain, tên vụ, địa chỉ, block) — **CHỈ
  dùng để tra cứu**, KHÔNG dùng ground truth AMLGuard (chưa công khai).
- **Ground truth**: `self_annotated` — mọi trajectory/nhãn tự dựng từ dữ
  liệu on-chain thật (Etherscan API V2, BSCTrace/MegaNode) + đối chiếu báo
  cáo công khai độc lập (CertiK, SlowMist, Halborn, Merkle Science, Elliptic,
  Nansen, crypto.news, và các nguồn tin tức uy tín khác — xem `source_url`
  trong `metadata/incident_registry.csv` cho từng incident).
- **Bridge/DEX/mixer protocol contracts**: xác nhận qua on-chain thật
  (function signature, khớp số tiền chính xác với báo cáo công khai), ghi
  trong `metadata/protocol_map.yaml`. Không suy đoán từ tên/memory — xem
  `metadata/annotation_guide.md` mục 1 cho bài học cụ thể.

## Coverage

| Thuộc tính | Giá trị |
|---|---|
| Số incident | 10 (5 positive + 5 hard-negative control) |
| Chain | eth, bsc, arbitrum |
| Bridge family đã verify | Ronin Bridge, BSC Token Hub, Across Protocol SpokePool (3) |
| DEX family đã verify | Uniswap V2, Uniswap V3, PancakeSwap V2, 1inch v4 (4) |
| Mixer đã verify | Tornado Cash Router (1) |
| Khoảng thời gian | 2022-03 đến 2024-11 |
| Tổng số action (outbound trajectory) | 65 |
| Tổng số prefix row (25/50/75/100% + k=2,3,5,7) | 39 (30 positive, 9 negative) |

### Danh sách incident

| incident_id | label | chain | endpoint_confirmed |
|---|---|---|---|
| ronin_bridge_2022 | 1 | eth | False (chưa trace tới mixer/exit cuối) |
| qbridge_qubit_2022 | 1 | bsc | False |
| feg_bridge_2024 | 1 | eth | True (Tornado Cash) |
| deltaprime_arbitrum_2024 | 1 | arbitrum | True (bridge sang Ethereum) |
| bsc_token_hub_2022 | 1 | bsc | True (provenance khớp chính xác báo cáo) |
| ronin_benign_control_2022 | 0 | eth | — |
| qbridge_benign_control_2022 | 0 | bsc | — |
| feg_benign_control_2024 | 0 | eth | True (Tornado Cash, dùng hợp pháp) |
| deltaprime_benign_control_2024 | 0 | arbitrum | — |
| bsc_token_hub_benign_control_2022 | 0 | bsc | True (bridge hợp pháp) |

## Exclusions

- **XPEXE Bridge** (candidate STRONG_CANDIDATE_bridge_in_name, ETH,
  2025-01-25): loại — không tìm được bất kỳ báo cáo công khai nào xác
  nhận incident, dù địa chỉ có hoạt động on-chain giống pattern exploit.
  Xem `experiments/logs/excluded_candidates.md`.
- 26 candidate nhóm `CHECK_MANUALLY_non_eth_chain` phần lớn CHƯA được rà
  soát hết (chỉ 4 đã dùng: BSC Token Hub, Radiant Capital chưa dùng tới,
  DeltaPrime dùng, Chibi Finance/XKingdom/WooPPV2/Magic/Sonne Finance/
  Polter Finance/Clober DEX/CryptoBottle chưa rà soát) — cơ hội mở rộng
  dataset trong tương lai nếu cần thêm incident.
- Candidate trên chain ngoài scope (`FTM`, `Optimism`, `Polygon`, `BASE`)
  bị loại hoàn toàn theo `configs/data.yaml` (chỉ `eth`, `bsc`, `arbitrum`).

## Giới hạn đã biết

1. **KHÔNG đạt ngưỡng "≥200 hard-negative"** — chỉ có 39 prefix row tổng
   (9 negative). Nguyên nhân: trajectory thật rất ngắn (1-22 action, trung
   bình ~6.5) vì đây là dữ liệu thật, không tổng hợp; sinh prefix theo tỷ
   lệ 25/50/75/100% + k=2,3,5,7 chỉ cho tối đa 1-8 prefix riêng biệt/
   trajectory. Người dùng đã xác nhận freeze v0.1 với ghi chú này thay vì
   tiếp tục tìm thêm incident (2026-08-13).
2. **`annotator_2` để trống cho TẤT CẢ 10 incident** — chưa qua review
   chéo độc lập bởi người thứ 2 (phiên làm việc chỉ có 1 người + AI hỗ
   trợ). Xem `experiments/logs/cross_review_log.md`.
3. **`endpoint_confirmed=False` cho 3/5 incident positive** (Ronin,
   QBridge) — chưa trace được tới mixer/exit-service cuối cùng trong cửa
   sổ dữ liệu đã crawl (giới hạn `time_horizon_hours=72` + `max_depth=6`
   theo `configs/data.yaml`). Không suy diễn cash-out khi chưa xác nhận.
4. **2 incident (FEG Bridge, QBridge) chấp nhận evidence thay thế** thay
   vì bridge+DEX sạch trong outbound trajectory — xem
   `metadata/annotation_guide.md` mục 5 để biết chi tiết và lý do.
5. **BSCTrace field mapping dựa trên hành vi API quan sát được**, không
   phải tài liệu chính thức đầy đủ (`fromBlock`/`toBlock` hoạt động nhưng
   không được document công khai) — có rủi ro thay đổi không báo trước từ
   phía nhà cung cấp.
6. **`data/raw/` cache phụ thuộc thời điểm crawl** (2026-08-13) — dữ liệu
   on-chain là bất biến (immutable) nên không có rủi ro dữ liệu "cũ đi",
   nhưng nếu cần crawl lại, API rate limit/pricing có thể đã thay đổi.

## License / sử dụng

- Dữ liệu on-chain: công khai theo bản chất (public blockchain), không có
  vấn đề bản quyền.
- Báo cáo công khai được trích dẫn (CertiK, SlowMist, Halborn,...): chỉ
  dùng để đối chiếu số liệu, luôn dẫn nguồn qua `source_url` trong
  `metadata/incident_registry.csv`, không sao chép nội dung báo cáo.
- KHÔNG chứa dữ liệu ground truth độc quyền của AMLGuard.
- Repo này (bao gồm dataset) dùng cho mục đích nghiên cứu KLTN, không
  phải sản phẩm thương mại.

## Tái tạo lại dataset

```bash
# Chạy lại pipeline cho 1 incident (dùng cache đã có)
python scripts/run_incident_pipeline.py --incident-id <incident_id> --no-collect

# Chạy tests xác nhận tính nhất quán
pytest tests/ -v
```
