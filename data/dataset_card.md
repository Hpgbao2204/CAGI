# Dataset Card — CAGI-ED v2.0

**Ngày freeze:** 2026-08-28
**Trạng thái:** ✅ Nhảy version lớn từ v0.9 (thay vì v1.x) vì có CHUỖI thay
đổi lớn giữa 2 lần freeze (chưa từng log riêng): sửa bug gốc `value_share`
gộp-token, thêm incident thứ 12 (`radiant_capital_arbitrum_2024`), sửa band
`fan_out`, mở rộng 12→15 incident (Giai đoạn B Bước 3), và **quyết định
feature-selection có căn cứ**: loại bỏ nhóm `bridge_context` (9 cột) khỏi
M1 chính thức sau khi ablation xác nhận gây hại có ý nghĩa thống kê ở N=15
(không hại ở N=11-12 — hiệu ứng do quy mô dữ liệu khuếch đại). Hard-negative
dùng được **612** (15 incident primary + `circulate_2023` auxiliary không
tính) / tổng prefix row **3354**. RQ1 (`M1` — nay KHÔNG có `bridge_context`
— vs `B3`): **KHÔNG ĐỦ BẰNG CHỨNG**, kết luận ỔN ĐỊNH xuyên suốt toàn bộ
chuỗi thay đổi trên (xem `results/reports/dataset_v2_full_comparison.md`).
**Bản trước:** `data/dataset_card_v0.1.md` … `data/dataset_card_v0.9.md`
(freeze v0.9, 12 incident, 430 usable) — giữ lại nguyên trạng các bản trước
để đối chiếu/audit. Xem `experiments/registry.csv` dòng `dataset_freeze_v2.0`
cho tóm tắt đầy đủ toàn bộ chuỗi thay đổi.

---

## [MỚI v2.0] Sửa bug value_share + mở rộng 12→15 incident + loại bridge_context khỏi M1 (2026-08-28)

### Tóm tắt chuỗi thay đổi từ v0.9 (chưa từng log riêng, ghi đầy đủ ở đây)

1. **Sửa bug GỐC `value_share` gộp-token** trong `build_trajectory()`
   (`src/trajectories/builder.py::outflow_by_src_token`) — `outflow_by_src`
   trước đây cộng dồn raw value của NHIỀU TOKEN KHÁC NHAU (ETH+ARB+WBTC+
   USDC...) như thể cùng đơn vị, khiến giao dịch thật bị tính `value_share`
   sai và bị loại oan. Phát hiện khi thêm incident mới `radiant_capital_arbitrum_2024`
   (seed đúng nhưng trajectory RỖNG do bug này). Fix đơn điệu một chiều —
   xác nhận trên 17 incident/control cũ (cache sẵn có, không gọi API mới):
   12/17 tăng action (+9 đến +437), **0/17 mất action nào**. Sau rebuild
   thật (fetch dữ liệu cho địa chỉ mới reachable ở hop sâu hơn):
   `ronin_bridge_2022` 113→1625, `paraluni_2022` 38→511, `qbridge_qubit_2022`
   52→698, `radiant_capital_arbitrum_2024` 0 (rỗng)→248. Xem
   `results/reports/value_share_unit_mix_fix_v1.md`.
2. Sửa bug `token_category_diversity` (đếm cả dust token, không lọc theo
   value share) — xem `results/reports/token_category_diversity_fix_v1.md`.
3. Thêm `radiant_capital_arbitrum_2024` (incident thứ 12, Abracadabra —
   Radiant Capital exploit Arbitrum Oct 2024, ~$53M, UNC4736/Bắc Triều
   Tiên theo Mandiant) — chính incident này dẫn tới phát hiện bug #1.
4. Sửa band `fan_out` (Giai đoạn B Bước 1) — từ ngưỡng cố định `≤3` sang
   band tương đối theo log-scale so với `fan_out` của chính positive
   tương ứng (`compute_max_fan_out()`).
5. **Mở rộng 12→15 incident** (Giai đoạn B Bước 3, xem
   `results/reports/giai_doan_b_buoc3_expansion_summary.md`):
   - Thêm **Magic/Abracadabra** (Arbitrum, MIM/GMX V2 Cauldron exploit,
     25/3/2025, ~$13M, CertiK).
   - Thêm **Hackerdao** (BSC, flash loan, 24/5/2022, ~$65K, CertiK).
   - Thêm **New Free Dao** (BSC, flash loan, 8/9/2022, ~$1.25M, 6+ nguồn
     độc lập) — ban đầu chỉ 9 action pure-transfer nên phân loại tạm
     `eval_tier=auxiliary_low_evidence`; sau khi QA leakage phát hiện
     `TornadoProxyLight` (mixer Tornado Cash trên BSC, thiếu trong
     `protocol_map.yaml` từ trước) và thêm vào, trajectory tăng lên 12
     action TOÀN BỘ là `mixer_or_exit` khớp chính xác báo cáo — **nâng lên
     `eval_tier=primary`**.
   - **Loại `Novo Defi`** (BSC, flash loan, 29/5/2022) — evidence thật (mẫu
     hình "smurfing", ~30 lần chia đều 2.398 BNB) bị kiến trúc
     `min_tainted_share` chặn vì mỗi lần chỉ chiếm ~3.3% tổng outflow node
     trung gian, dưới ngưỡng 5%. Đây là giới hạn kiến trúc CÓ THẬT
     (`min_tainted_share` không xử lý tốt trường hợp split đều nhiều phần
     bằng nhau) — KHÔNG sửa giữa Bước 3, ghi nhận làm investigation riêng
     tương lai. Xem `experiments/logs/excluded_candidates.md`.
6. **Phát hiện quan trọng nhất: `bridge_context` gây hại cho M1, khuếch đại
   bởi N** (xem `results/reports/bridge_context_ablation_investigation.md`)
   — ablation trên 15 incident phát hiện loại bỏ nhóm feature
   `bridge_context` (9 cột: `time_to_first_bridge`,
   `action_count_bridge_deposit(_ratio)`, `action_count_bridge_withdraw(_ratio)`,
   `num_bridge_families`, `swap_after_bridge`, `motif_bridge_then_swap`,
   `motif_nested_bridge`) cải thiện M1 có ý nghĩa thống kê (paired diff
   +0.0638, 95% CI [+0.0101,+0.1501], p=0.036). Điều tra xác nhận:
   - `action_count_bridge_withdraw(_ratio)`: hằng số tuyệt đối (0/15
     incident có giá trị khác 0) — hoàn toàn vô dụng.
   - Chỉ 2/9 cột thực sự được XGBoost dùng để split (theo SHAP); CẢ HAI
     đều gây hại: `time_to_first_bridge` chỉ học đúng hướng cho 5/15
     incident có bridge thật (dùng LI.FI/Stargate/Across), SAI HƯỚNG cho
     9/15 incident còn lại (chủ yếu BSC/mixer).
   - Hiệu ứng **tăng theo N**: không có ý nghĩa thống kê ở N=11-12 (diff
     0.002-0.007, CI luôn chứa 0 rộng), chỉ lớn+có ý nghĩa ở N=15 — đúng
     vì thêm incident dùng protocol đa dạng hơn (TornadoProxyLight, LI.FI,
     Stargate) khuếch đại overfitting theo protocol vốn tiềm ẩn.
   - **Quyết định (đã xác nhận với người dùng)**: loại bỏ TOÀN BỘ 9 cột
     khỏi M1 chính thức (`src/models/baselines.py::BRIDGE_CONTEXT_COLS_EXCLUDED`).
     Xác nhận đối xứng hoàn hảo sau fix: thêm lại 9 cột cho đúng
     diff=-0.0638 (ngược dấu, cùng độ lớn).

### RQ1 ổn định xuyên suốt toàn bộ chuỗi thay đổi

| Mốc | N | Mean diff (M1-B3) | 95% CI | Kết luận |
|---|---|---|---|---|
| v0.9 (trước value_share fix) | 11 | +0.0024 | [-0.0734,+0.0772] | KHÔNG ĐỦ BẰNG CHỨNG |
| Sau value_share fix + radiant | 12 | -0.0465 | [-0.1181,+0.0085] | KHÔNG ĐỦ BẰNG CHỨNG |
| Sau Hackerdao (giữa Bước 3) | 14 | -0.0649 | [-0.1290,-0.0127] | ⚠️ dao động tạm (B3 thắng) |
| Sau New Free Dao (15, có bridge_context) | 15 | -0.0282 | [-0.1565,+0.0902] | KHÔNG ĐỦ BẰNG CHỨNG (ổn định lại) |
| **v2.0 (15, KHÔNG bridge_context)** | **15** | **+0.0355** | **[-0.0286,+0.1288]** | **KHÔNG ĐỦ BẰNG CHỨNG** |

Xem `results/reports/dataset_v2_full_comparison.md` cho bảng so sánh đầy
đủ v1 (12 incident, có bridge_context) vs v2 (15 incident, không
bridge_context).

---

## [v0.9] Re-verify + sửa gốc bug #6 (2026-08-14, theo yêu cầu người dùng)

Sau freeze v0.8, người dùng yêu cầu 4 việc trước khi dữ liệu được dùng để
train model: (1) re-verify riêng `ronin_bridge_2022` (mức tăng lớn nhất,
16 lần), (2) sửa GỐC bug #6 thay vì giữ vá tạm, (3) xác nhận rõ scope RQ1,
(4) freeze lại nếu số liệu đổi.

### Bước 1 — Re-verify `ronin_bridge_2022` (113 action)

| Kiểm tra | Kết quả |
|---|---|
| 2 tx hash gốc (`0xed2c72ef...`=USDC, `0xc28fad5e...`=ETH) còn nguyên vẹn | ✅ Có, nằm trong `provenance_events` (KHÔNG lẫn vào 113 action — kiến trúc builder chỉ mở rộng OUTBOUND từ seed, 2 sự kiện bridge là INBOUND) |
| Tổng giá trị bridge deposit | `math.expm1(amount_norm)` = **25,500,000.000000026 USDC** + **173,600.0 ETH** — khớp CHÍNH XÁC báo cáo gốc, không đổi |
| Số lần `bridge_deposit` trong 113 action | **0** — đúng thiết kế (bridge deposit là provenance, không phải outbound action) |
| Số provenance event | Đúng **2**, không nhiều hơn — không double-count |
| Phân loại 113 action | 111 `transfer` + 2 `swap` — toàn bộ là outbound value-flow phát sinh SAU bridge deposit, không phải bridge deposit bị đếm trùng |
| Trùng lặp signature | 0/113 — không có dòng nào trùng `(tx_hash, event_type, src, dst, amount_norm, token)`. 2 tx_hash xuất hiện 2 lần nhưng là 2 leg khác nhau THẬT của 1 tx multi-hop (USDC→trung gian, trung gian→1inch bằng ETH) |

**Kết luận: SẠCH, không sai lệch.** 173,600 ETH + 25,500,000 USDC không đổi;
toàn bộ 113 action tăng thêm đến từ swap/transfer downstream thật (bug #3/#4
ở v0.8 khiến trước đây pipeline dừng mở rộng sớm do 1inch/Uniswap V3 pool bị
coi nhầm là ví thường).

### Bước 2 — Sửa GỐC bug #6 (cache key `(chain, address, incident_id)`)

Thay vì giữ vá tạm ("chốt 1 thứ tự fetch cố định" ở v0.8), đã đổi cache key
thật: `data/raw/{chain}/{address}/{incident_id}/...json` (thêm 1 tầng thư
mục `incident_id`) cho CẢ 2 client (`EtherscanClient`, `BscTraceClient`) và
thread `incident_id` qua toàn bộ chuỗi gọi (`collect_address_raw_data`,
`_load_cached_rows`, `_load_cached_bsctrace_rows`, `load_events_for_addresses`,
`find_provenance_bridge_events`, `find_swap_evidence`, và các hàm tương ứng
trong `hard_negative_miner.py`).

**Test bắt buộc** (`tests/test_collector.py::test_two_incidents_same_address_different_window_do_not_overwrite`,
`tests/test_bsctrace_client.py::test_two_incidents_same_address_different_window_do_not_overwrite`):
giả lập 2 incident cùng fetch 1 địa chỉ với 2 cửa sổ khác nhau — xác nhận cả
2 file cache tồn tại độc lập dưới 2 thư mục `incident_id` riêng, fetch lại
1 incident KHÔNG ảnh hưởng cache của incident kia, bất kể thứ tự trước/sau.

**Migrate dữ liệu cache đã có** (`scripts/migrate_cache_to_incident_scoped.py`):
COPY (không re-fetch mạng) toàn bộ cache hiện có sang cấu trúc mới, dùng
đúng "processed address set" mà bản code TRƯỚC khi sửa (nạp động từ git
HEAD) đã tính khi build v0.8 — không suy đoán/nhớ lại từ memory. Xác nhận
sau migrate: cả 17/17 dòng `incident_registry.csv` cho action count **giống
hệt** v0.8 (khớp từng số), 436/436 hard-negative dùng lại được. `pytest
tests/ -v`: 157/157 pass.

**Xác nhận kết quả không đổi cho 2 incident dùng chung địa chỉ đã phát hiện**
(`0xdd90e5e8...`, 481 gửi/789 nhận độc lập — CEX/OTC hot wallet, KHÔNG phải
leak thật):
- `qbridge_qubit_2022`: fetch lại `paraluni_2022` với cửa sổ riêng của nó →
  `qbridge_qubit_2022` **GIỮ NGUYÊN 52 action**, không bị ảnh hưởng (trước
  khi sửa gốc, việc này sẽ ghi đè và làm sai qbridge_qubit_2022).
- `paraluni_2022`: khi fetch đúng cửa sổ RIÊNG của nó cho địa chỉ dùng chung
  (thay vì dùng "ké" dữ liệu cũ phản ánh cửa sổ của qbridge_qubit_2022) →
  **23 → 24 action** (+1 action thật, +1 địa chỉ processed) — bằng chứng
  bug #6 THẬT SỰ đã ảnh hưởng dữ liệu trước đây, không chỉ là rủi ro lý
  thuyết. Đã cập nhật golden fixture.

`0xdef171fe...` (Velora, giữa `qbridge_qubit_2022`/`utopiasphere_2024`) đã
được allowlist ở v0.8 (bug #4) nên không còn là điểm mở rộng frontier —
không còn rủi ro ghi đè giữa 2 incident này nữa (dù kiến trúc cache mới vẫn
bảo vệ cả trường hợp này).

Đã bỏ ghi chú "giới hạn kiến trúc chưa sửa triệt để" liên quan bug #6 khỏi
mục Giới hạn — xem mục Giới hạn hiện tại (đã cập nhật).

### Bước 3 — Xác nhận rõ scope RQ1

**`circulate_2023` (CirculateBUSD) đã chính thức bị loại khỏi tập 11
incident dùng cho RQ1 chính** (`eval_tier=auxiliary_low_evidence` trong
`incident_registry.csv`, `role=auxiliary_low_evidence` trong
`split_manifest.json`) — chỉ giữ trong tập 12 incident đầy đủ để tham
khảo/robustness check phụ (VD: kiểm tra mô hình có generalize sang case
"toàn transfer, không motif rõ ràng" hay không). Lý do: gate yếu nhất
trong 12 incident, chỉ có evidence thay thế (không có swap/bridge_deposit
chính thức trong outbound trajectory). Quyết định này đã có từ trước v0.8
(ghi trong mục "Eval tier" bên dưới) — xác nhận lại rõ ràng ở đây theo yêu
cầu, KHÔNG chỉ ngầm hiểu qua bảng số liệu.

### Bước 4 — Freeze lại (v0.9)

Số liệu ĐỔI (dù nhỏ): `paraluni_2022` 23→24 action sau khi có đúng cửa sổ
riêng (bug #6 sửa gốc). Freeze v0.9 với commit hash thật — xem
`experiments/registry.csv`.

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
| `paraluni_2022` | 16 | **24** (v0.8 tạm: 23, sửa gốc bug #6 ở v0.9 mới đúng cửa sổ riêng) | Bug #1/#2/#4/#6 |
| `wooppv2_2024`, `xkingdom_2024`, `feg_bridge_2024`, `deltaprime_arbitrum_2024` | không đổi | không đổi | Đã xác nhận SẠCH qua audit — không bị ảnh hưởng bởi 6 bug trên |

Toàn bộ thay đổi đã đối chiếu tx-level: các action mới đều là giao dịch
thật, nằm trong cửa sổ hợp lệ của incident (không phải nhiễu từ mở rộng cửa
sổ), xác nhận qua Etherscan/BscScan (nhãn contract) hoặc qua chính cấu trúc
dữ liệu on-chain (provenance bridge event cùng seed).

---

## Eval tier — RQ1 chính (15 incident) vs auxiliary (16 incident đầy đủ)

*(cập nhật v2.0, 2026-08-28 — `circulate_2023` vẫn là auxiliary DUY NHẤT,
không đổi kể từ v0.7, không tính vào N chính của RQ1, xem lý do gốc ở
`data/dataset_card_v0.7.md`; 3 incident thêm ở v2.0 — Magic, Hackerdao, New
Free Dao — ĐỀU là `primary`, không phải auxiliary)*

| | 16 incident đầy đủ (toàn dataset) | **15 incident (RQ1 chính)** |
|---|---|---|
| Positive incident | 16 | **15** |
| Hard-negative — raw mining | 646 | 624 |
| Hard-negative — dùng được | 522 | **500** |
| + hard-negative v2-complexity dùng được | 107 | 107 |
| + control gốc | 5 | 5 |
| **TỔNG dùng được** | 634 | **612** |
| Tổng prefix row | 3502 (positive+8, negative+140 từ circulate_2023) | **3354** |

**612 ≥ 200 → RQ1 chính vẫn đạt ngưỡng dư dả**, tăng đáng kể so với v0.9
(408) sau toàn bộ chuỗi sửa bug + mở rộng ở trên.

---

## QUY ƯỚC BẮT BUỘC — 2 con số riêng biệt, không gộp chung

- **"raw mining"**: số dòng có mặt trong `hard_negative_registry.csv` (đã
  pass tiêu chí lọc CỦA MINER ở mức giao dịch — `_passes_structural_filter`,
  không áp `min_tainted_share`/`time_horizon_hours`).

  **Tiêu chí `_passes_structural_filter` đầy đủ, giá trị ngưỡng CHÍNH XÁC**
  (`src/collect/hard_negative_miner.py`, đọc trực tiếp từ code, không suy
  đoán — bổ sung 2026 Tuần 10 vì Tuần 9's E6 cần tiêu chí này để giải
  thích kết quả):
  - `no_events_in_window`: không có event nào trong `[start_block, end_block]`.
  - `insufficient_complexity_vs_positive`: số event < `min_candidate_events`
    (mặc định=1 tức KHÔNG áp — chỉ áp cho vòng mine bổ sung Tuần 5, xem
    `compute_min_candidate_events()`).
  - `no_direct_interaction_with_contract`: không có event nào chạm trực
    tiếp `contract_address`.
  - `multiple_mixer_events_unusual` (nếu contract LÀ mixer) / `unexpected_mixer_followup`
    (nếu KHÔNG): >1 lần dùng mixer khác nhau / có bất kỳ `mixer_or_exit` nào.
  - **`fan_out_split_like_pattern`: `len({e.dst for e in candidate_src_events}) > 3`**
    — candidate có **hơn 3 địa chỉ đích khác nhau** (tính từ event có
    `src=candidate`) trong cửa sổ mining bị LOẠI. Đây là tiêu chí bị reject
    NHIỀU NHẤT (~82% trong 505 candidate bị loại còn cache được, Tuần 9
    Bước 0). **Hệ quả trực tiếp, đã xác nhận bằng dữ liệu thật (Tuần 9,
    E6 — `results/reports/e6_robustness_v1.md`)**: tập hard-negative CHÍNH
    THỨC (436 dòng) có `fan_out` trung bình 1.29 (median=1, max=3 — đúng
    ngưỡng), trong khi các candidate bị loại vì tiêu chí này (`fan_out`
    trung bình 2.66, max **144**) khi build lại trajectory đầy đủ cho thấy
    M1 phân biệt KÉM HƠN hẳn (PR-AUC 0.55 vs 0.72, có ý nghĩa thống kê) —
    tiêu chí `fan_out≤3` vô tình khiến tập hard-negative "sạch" hơn thực
    tế vận hành, KHÔNG kiểm chứng được M1 trên entity fan-out cao NHƯNG
    benign (xem mục Giới hạn đã biết #12 bên dưới, và
    `results/reports/high_fanout_benign_probe.md`).
  - `zero_volume`: tổng `abs(amount_norm)` các event outgoing từ candidate = 0.
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
3. **[ĐÃ SỬA GỐC v0.9] Kiến trúc cache theo (chain, address) không phân
   biệt incident/cửa sổ thời gian** — ĐÃ sửa triệt để bằng cách thêm
   `incident_id` vào cache key (`data/raw/{chain}/{address}/{incident_id}/`),
   có test bắt buộc xác nhận + migrate toàn bộ cache hiện có. Xem mục
   "Re-verify + sửa gốc bug #6" ở đầu dataset card. KHÔNG còn là giới hạn.
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
12. **[MỚI Tuần 9-10] Tiêu chí `fan_out_split_like_pattern` (`unique_dst > 3`,
    xem mục "QUY ƯỚC BẮT BUỘC" ở trên) khiến tập hard-negative CHÍNH THỨC
    thiên lệch về phía fan-out THẤP** (mean=1.29, max=3) — không đại diện
    cho các entity benign hoạt động mạnh/fan-out cao thật ngoài đời (market
    maker, exchange hot wallet). Đã kiểm chứng 2 lần: (1) E6 — "unmatched
    negative" (candidate bị loại chính vì tiêu chí này, fan_out thật lên
    tới 144) khiến M1 phân biệt kém hẳn (PR-AUC 0.55 vs 0.72 trên tập
    matched, có ý nghĩa thống kê); (2) probe 4 entity market maker/exchange
    có NHÃN CÔNG KHAI XÁC NHẬN (Wintermute, Binance Hot Wallet 20, Jump
    Trading, Cumberland) — KHÔNG kết luận được dứt khoát (0/4 tạo được
    trajectory fan_out>3 trong ngân sách probe nhỏ, do cửa sổ thời gian
    không khớp giai đoạn hoạt động thật của từng địa chỉ — xem
    `results/reports/high_fanout_benign_probe.md`). **Kết luận: đây là
    limitation THẬT của dataset, chưa được giải quyết** — mở rộng
    dataset/nới tiêu chí (có kiểm soát, không hạ chuẩn evidence) đã hoãn
    lại sau khi hoàn thành các bước kiểm chứng còn lại (quyết định người
    dùng, Tuần 9).

## License / sử dụng (rà soát lại đầy đủ, Tuần 10)

**Dữ liệu ĐƯỢC PHÉP chia sẻ/công bố:**
- Toàn bộ on-chain data (địa chỉ, tx hash, block number, amount) — công khai
  theo bản chất (public blockchain, ai cũng đọc được qua block explorer/API).
- Nhãn (`label`, `event_type`, motif, `endpoint_confirmed`...) — **TỰ nhóm
  trace và tự gán**, không sao chép từ bất kỳ ground truth độc quyền/chưa
  công khai nào.
- Toàn bộ code (`src/`, `scripts/`, `tests/`), config (`configs/`,
  `metadata/*.yaml`, `*.csv` do nhóm tự tạo), kết quả (`results/`) — sản
  phẩm gốc của nhóm.
- Trích dẫn báo cáo công khai (tin tức/hậu kiểm cộng đồng về từng vụ hack)
  dùng để ĐỐI CHIẾU/xác nhận nhãn — chỉ giữ `source_url` tham chiếu, KHÔNG
  sao chép nguyên văn nội dung.

**KHÔNG chứa / KHÔNG dùng:**
- **KHÔNG chứa ground truth độc quyền của AMLGuard** — README của AMLGuard
  ghi rõ dữ liệu nhãn phát hành "upon acceptance" (paper đang trong quá
  trình xét duyệt tại thời điểm dự án bắt đầu, xem `proposal_revision_v1.md`
  mục đọc AMLGuard). `metadata/incident_candidates_amlguard.csv` (82 dòng)
  **CHỈ dùng làm seed list tham khảo** (tên/chain/địa chỉ/block số công khai
  để rút ngắn thời gian tìm incident) — mọi trajectory/nhãn/motif đều do
  nhóm TỰ trace và TỰ gán từ dữ liệu on-chain thật, không sao chép nhãn
  AMLGuard.
- **License của `AML_Incidents.csv`/`SOTA-Tool.zip` (figshare AMLGuard)
  CHƯA từng được xác nhận rõ ràng** (đã kiểm tra đầu dự án, không thấy
  license hiển thị — xem `proposal_revision_v1.md` mục "Hành động cần làm
  ngay") — vì lý do này, code AMLGuard KHÔNG được import/tái sử dụng trực
  tiếp vào pipeline chính ở bất kỳ đâu (chỉ tham khảo kỹ thuật khi viết
  spider thu thập của nhóm).
- **License Terms of Service của Etherscan/BscScan/NodeReal API cho việc
  REDISTRIBUTE dữ liệu response thô (`data/raw/*.json`) CHƯA được rà soát
  kỹ trong dự án này** — ghi nhận rõ đây là điểm CHƯA xác nhận (không giả
  định compliance), và cũng là một phần lý do `data/raw/` không commit lên
  git (ngoài lý do dung lượng).
- Repo này dùng cho mục đích nghiên cứu KLTN, không phải sản phẩm thương mại.

## Tái tạo lại dataset

```bash
# Chạy lại pipeline cho 1 incident gốc (dùng cache đã có)
python scripts/run_incident_pipeline.py --incident-id <incident_id> --no-collect

# Chạy lại mining hard-negative (do_collect=False dùng cache, hoặc
# do_collect=True cần BSCTRACE_API_KEY/ETHERSCAN_API_KEY trong .env)

# Tính lại toàn bộ số liệu raw/usable/tổng prefix row + tỷ lệ rỗng theo incident
python scripts/compute_dataset_v0.9_stats.py

# Chạy tests xác nhận tính nhất quán + QA leakage + gate usable>=200 + golden fixtures
pytest tests/ -v
```
