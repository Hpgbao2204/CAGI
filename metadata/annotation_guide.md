# Annotation Guide — CAGI-ED

Tài liệu này tổng hợp mọi quyết định ngữ nghĩa đã áp dụng **nhất quán** qua
các incident trong `incident_registry.csv`, để người tiếp theo (hoặc chính
mình sau này) annotate incident mới theo đúng chuẩn, không lặp lại sai lầm
đã gặp. Đọc mục 1 trước tiên — đây là bài học quan trọng nhất.

---

## 1. ⚠️ Cảnh báo hàng đầu: KHÔNG suy đoán địa chỉ contract từ tên/memory

**Sự cố gốc:** `metadata/protocol_map.yaml` ban đầu ghi `0x098b716b8aaf215
12996dc57eb0615e2383e2f96` là contract "Ronin Bridge". Địa chỉ này thực ra
là **ví của kẻ tấn công** (Lazarus Group, bị OFAC chế tài) — nó trùng với
địa chỉ trong `incident_candidates_amlguard.csv` (bị AMLGuard/LLM memory
gán nhầm vai trò), không phải contract bridge thật. Nếu không phát hiện và
sửa, toàn bộ pipeline sẽ decode sai (`bridge_deposit`/`bridge_withdraw` gắn
nhầm cho giao dịch của kẻ tấn công, thay vì contract bridge thật).

**Nguyên tắc bắt buộc áp dụng cho MỌI địa chỉ mới thêm vào `protocol_map.yaml`:**

1. **Không bao giờ** tin một địa chỉ chỉ vì nó "nghe có vẻ đúng tên" hoặc
   xuất hiện trong danh sách seed AMLGuard — danh sách đó chỉ dùng để tra
   cứu, không phải nguồn xác thực vai trò contract.
2. **Xác nhận vai trò qua chính dữ liệu on-chain thật**, theo thứ tự ưu
   tiên:
   - **Khớp số tiền chính xác** với báo cáo công khai (mạnh nhất) — vd BSC
     Token Hub: 2 tx nội bộ đúng 1,000,000 BNB mỗi lần, khớp *chính xác*
     "2,000,000 BNB minted" từ Halborn/Elliptic.
   - **Chữ ký hàm đặc trưng** thấy trực tiếp trong `functionName` của tx
     thật — vd `depositV3(...)` chỉ có ở Across Protocol SpokePool,
     `deposit(address _tornado, bytes32 _commitment,...)` chỉ có ở Tornado
     Cash Router. Đây là bằng chứng hành vi từ ABI đã verify trên chain,
     không phải suy đoán.
   - **Label công khai trên block explorer** (BscScan/Etherscan hiển thị
     tên contract đã được họ xác minh, vd "BSC: Token Hub").
3. Ghi rõ **evidence cụ thể** trong comment YAML (tx hash, block, số liệu
   đối chiếu) — không ghi chung chung "đã verify".
4. `verify_status` dùng đúng định dạng `verified_onchain_<ngày>` khi xác
   nhận qua on-chain thật (khác `verified_<ngày>` khi người dùng tự đối
   chiếu qua kênh khác) — để phân biệt nguồn xác thực khi audit lại sau.
5. Nếu một địa chỉ là **ví liên quan tới incident nhưng KHÔNG phải bridge/
   DEX/mixer contract** (vd ví nhận tiền của kẻ tấn công), đặt vào mục
   `known_seed_wallets`, **không** đặt vào `bridges`/`dexes` — nếu không,
   `build_verified_bridge_address_index()` sẽ coi nhầm nó là 1 bridge
   contract thật khi decode (xem `src/normalize/decoder.py`).

---

## 2. Ground truth và nguồn dữ liệu

- **Không dùng ground truth AMLGuard** — chưa công khai.
  `incident_candidates_amlguard.csv` chỉ dùng làm **danh sách seed để tra
  cứu** (địa chỉ, ngày, chain gợi ý). Mọi label/trajectory phải tự dựng từ
  dữ liệu on-chain thật + đối chiếu báo cáo công khai độc lập.
- **≥1 nguồn báo cáo công khai bắt buộc** (CertiK, SlowMist, Beosin,
  BlockSec, SharkTeam, Halborn, hoặc tin tức uy tín) trước khi thêm 1
  incident vào registry. Nếu không tìm được, **loại** — xem mục 5.
- **non-ETH chain KHÔNG đồng nghĩa cross-chain.** Khi duyệt nhóm
  `CHECK_MANUALLY_non_eth_chain` trong `incident_candidates_amlguard.csv`,
  phải tự kiểm tra bridge hop thật qua dữ liệu on-chain, không suy đoán từ
  việc "chain khác ETH" là đủ.

---

## 3. Threat model — endpoint và provenance

Theo `threat_model.md` mục 4: endpoint hợp lệ là **known mixer, public
exit-service label, hoặc kết thúc trajectory được report xác nhận**. Không
khẳng định cash-out chỉ vì địa chỉ "giống" CEX.

### Provenance vs outbound trajectory

`src/trajectories/builder.py::build_trajectory` chỉ **mở rộng forward** từ
seed — sự kiện đưa tiền **VÀO** seed (lý do seed được coi là incident-
linked) không thuộc outbound trajectory. Pattern áp dụng nhất quán:

- `find_provenance_bridge_events()` — bridge event đưa tiền vào seed (vd
  Ronin: 173,600 ETH + 25.5M USDC từ Ronin Bridge; BSC Token Hub: 2,000,000
  BNB từ TokenHub).
- `find_swap_evidence()` — swap event thật nhưng không nằm trong node_depth
  forward-only (vd LP pool trả BNB về ví, thấy ở QBridge/BSC Token Hub).

Cả 2 đều là **bằng chứng bổ sung hợp lệ** cho gate check (≥1 bridge link +
≥1 DEX action), **không cần ép** vào outbound trajectory. Ghi rõ trong
`notes` của registry khi dùng pattern này (khác với incident có bridge/
swap nằm sạch trong outbound trajectory, vd DeltaPrime).

### Mixer/DEX router = endpoint, KHÔNG phải hop để tiếp tục trace

**Bug thật đã sửa (2026-08-13):** thêm Tornado Cash Router vào
`mixer_allowlist` khiến `build_trajectory` mở rộng `node_depth` QUA mixer,
kéo theo các lượt rút tiền của **người dùng khác không liên quan** (chia
sẻ cùng mixer contract) vào trajectory — trajectory phình từ 15 lên 237
action. Cùng rủi ro với DEX router dùng chung (PancakeSwap Router).

**Nguyên tắc:** mọi địa chỉ trong `config.allowlist` (bridge + dex + mixer)
được **chấp nhận vào trajectory** (bỏ qua `value_share`) nhưng **không bao
giờ** được dùng làm `src` để tiếp tục mở rộng — xem comment trong
`build_trajectory()`. Test hồi quy:
`tests/test_builder.py::test_does_not_expand_frontier_through_allowlisted_*`.

---

## 4. `value_share` — chỉ so sánh được cùng đơn vị giá trị

**Bug thật đã sửa (2026-08-13), 2 lớp:**

1. **Log-scale bug:** `value_share` ban đầu tính trên `amount_norm` (đã
   log-scale theo schema Bước 1) — `log(a)+log(b) ≠ log(a+b)`, phép cộng
   dồn trên giá trị log không có ý nghĩa toán học đúng. Đã sửa bằng
   `math.expm1()` (nghịch đảo `log1p`) **chỉ trong nội bộ builder**, không
   đổi `CanonicalEvent.amount_norm` (vẫn giữ log-scale đúng schema).
2. **So sánh khác token không quy đổi:** ngay cả với giá trị thật (raw),
   so sánh "2.967 WBTC" với "300,000 USDC+ARB+WETH cộng dồn" theo **số
   lượng token thô** vẫn sai — không có dữ liệu giá để quy USD. Đây là lý
   do `bridge_allowlist`/`dex_allowlist`/`mixer_allowlist` trong
   `configs/data.yaml` **bắt buộc phải điền** (không được để trống) — nhánh
   `counterparty_allowed` trong `build_trajectory()` là lối thoát duy nhất
   cho trường hợp cash-out qua nhiều token khác nhau.

**Hệ quả cho annotator:** khi thêm 1 bridge/DEX/mixer contract mới vào
`protocol_map.yaml`, **luôn đồng bộ thêm vào `configs/data.yaml`**
allowlist tương ứng — nếu không, incident dùng contract đó có thể build ra
trajectory rỗng dù có bằng chứng thật (đã xảy ra với DeltaPrime/WBTC).

---

## 5. Ngưỡng bằng chứng — không được tự nới lỏng

Tiêu chí gốc: **≥1 bridge link + ≥1 DEX action** bằng bằng chứng on-chain
thật (giống Ronin). Khi 1 incident không đạt cấu trúc này sạch sẽ, đã áp
dụng các mức độ chấp nhận **rõ ràng và có xin ý kiến người dùng trước**,
không tự quyết:

| Incident | Bằng chứng thay thế | Được chấp nhận vì |
|---|---|---|
| FEG Bridge | bridge + **mixer** (Tornado Cash) thay DEX | mixer_or_exit là 1 trong 6 nhóm feature chính thức, phù hợp core mission hơn cả DEX |
| QBridge | bridge/DEX chỉ có ở dạng "evidence ngoài trajectory" (provenance/swap-evidence), không sạch trong outbound | vẫn là bằng chứng thật, dùng đúng pattern đã thống nhất |

**XPEXE Bridge bị loại hẳn** (không dùng bất kỳ mức chấp nhận nào) vì
**không tìm được bất kỳ nguồn báo cáo công khai nào** xác nhận incident —
xem `experiments/logs/excluded_candidates.md`. Dù địa chỉ có hoạt động
on-chain giống pattern exploit (funding nhỏ → contract creation → tương
tác Balancer Vault), suy luận hành vi **không thay thế được** yêu cầu
nguồn công khai độc lập.

**Nguyên tắc chung:** nếu sau khi thử hết STRONG_CANDIDATE + CHECK_MANUALLY
vẫn không đủ 6 incident hợp lệ, **dừng lại và báo cáo**, không hạ chuẩn
evidence để chạy đủ số lượng.

---

## 6. Hard-negative — tiêu chí lựa chọn

Quyết định đã thống nhất với người dùng (2026-08-13): **khớp cấu trúc hành
vi + volume theo log-scale**, **không cần khớp tuyệt đối USD** — vì hầu
như không thể tìm 1 user benign chuyển số tiền ngang một vụ hack $600M+ mà
vẫn hợp lý (nếu có, bản thân nó đã đáng ngờ).

Quy trình đã áp dụng cho cả 5 hard-negative:
1. Lấy 1 contract bridge/DEX/mixer **đã verify** liên quan tới incident
   positive tương ứng.
2. Tìm 1 địa chỉ **khác** tương tác với **cùng contract**, **cùng ngày**
   (dùng `fromBlock`/`toBlock` — tham số không có trong tài liệu công khai
   của BSCTrace nhưng **hoạt động thật**, xem `src/collect/bsctrace_client.py`).
3. Kiểm tra địa chỉ đó **không** có hoạt động split/fan-out/mixer bất
   thường tiếp theo trong cửa sổ đã crawl.
4. Ưu tiên địa chỉ có **ít giao dịch nhất** trong cửa sổ hẹp — hệ sinh
   thái DEX (đặc biệt PancakeSwap trên BSC) bị chi phối mạnh bởi bot/MEV,
   khó tìm "user thuần túy cá nhân" hoàn toàn sạch; chấp nhận và ghi rõ
   giới hạn này trong `notes` thay vì giả vờ đã tìm được mẫu hoàn hảo.

**Lưu ý về `start_block`:** phải khớp đúng block hoạt động THẬT của địa
chỉ negative (không copy nguyên `start_block` của incident positive tương
ứng) — lệch dù chỉ vài chục block có thể khiến `time_horizon_hours` bỏ lỡ
toàn bộ hoạt động (gặp phải ở `qbridge_benign_control_2022`, lệch 15
block khiến trajectory rỗng).

---

## 7. Hạ tầng thu thập dữ liệu — giới hạn đã biết

- **Etherscan free-tier KHÔNG hỗ trợ BSC** (cả API V1 lẫn V2 unified) —
  dùng **BSCTrace (MegaNode/NodeReal)** làm thay thế miễn phí chính thức,
  xem `src/collect/bsctrace_client.py`. Schema response **khác hẳn** tài
  liệu công khai (đã xác nhận qua `smoke_test()` với key thật):
  - `category` hợp lệ: `external, internal, 20, 721, 1155, state, deposit,
    withdraw` — **`"20"` không phải `"erc20"`**.
  - `value`: hex string **raw base-unit**, không phải decimal có sẵn.
  - `blockTimeStamp`: unix int ở **top-level**, không nested trong
    `metadata`.
  - Phân trang qua `pageKey`, không phải `pageToken`.
  - `logIndex` là field thật, không cần offset giả.
  - `fromBlock`/`toBlock` **hoạt động** dù không có trong tài liệu công
    khai — dùng để lọc lịch sử theo block range khi tìm hard-negative.
- **Etherscan giới hạn 10,000 record/call** — `EtherscanClient` tự phân
  trang bằng cách đẩy `startblock` lên block cuối cùng đã nhận + dedup ở
  biên (xem `_fetch_all_pages`).
- **BSCTrace không lọc theo block range trong `fetch_asset_transfers()`
  mặc định** (không dùng `fromBlock`/`toBlock` do chưa xác nhận tính ổn
  định lâu dài) — bắt buộc lọc `[start_block, end_block]` ở tầng
  `src/pipeline/incident_pipeline.py::expand_and_build_trajectory` trước
  khi đưa vào `build_trajectory`, nếu không sẽ dính bug pha loãng
  tainted-share (xem mục 4).
- **Cache đa file cần dedup khi đọc lại** — nếu cùng 1 địa chỉ được fetch
  nhiều lần ở các thời điểm khác nhau (vd thăm dò thủ công), các file cache
  riêng lẻ có thể chứa transfer trùng nhau; `_load_cached_bsctrace_rows()`
  dedup theo `(hash, category, logIndex)`.

---

## 8. Checklist thêm 1 incident mới

1. Xác nhận qua ≥1 nguồn báo cáo công khai độc lập (mục 2).
2. Thêm dòng vào `incident_registry.csv` (seed, start_block, chain, label).
3. Chạy `python scripts/run_incident_pipeline.py --incident-id <id>`.
4. Nếu gặp contract mới chưa có trong `protocol_map.yaml`: xác nhận qua
   on-chain thật (mục 1), **không đoán từ tên**.
5. Nếu thêm bridge/DEX/mixer mới đã verify: đồng bộ vào
   `configs/data.yaml` allowlist tương ứng (mục 4).
6. Đối chiếu số liệu (amount, tx hash) với báo cáo công khai — nếu lệch,
   ghi rõ vào `notes`, không tự "làm khớp".
7. Kiểm tra gate: ≥1 bridge link + ≥1 DEX action (outbound trajectory HOẶC
   provenance/swap-evidence, ghi rõ loại nào) — nếu không đạt, xin ý kiến
   trước khi hạ chuẩn hoặc loại (mục 5).
8. Chạy `pytest tests/ -v`, xác nhận pass trước khi sang incident tiếp.
9. Tìm hard-negative tương ứng (mục 6).
10. Cập nhật golden fixtures nếu builder/pipeline logic thay đổi
    (`tests/fixtures/golden/`).

---

## 9. Chẩn đoán trajectory rỗng ở hard-negative mining (2026-08-13)

**Bối cảnh:** sau khi mining 208 hard-negative (v0.2 lần đầu), phát hiện
17/208 (8.2%) có trajectory RỖNG (0 action) khi build lại bằng
`expand_and_build_trajectory` chuẩn — dù đã pass tiêu chí lọc của miner.
Điều này khiến số "hard-negative dùng được" (sinh ra ≥1 prefix row) thấp
hơn số dòng trong `hard_negative_registry.csv`, và ban đầu bị báo cáo SAI
là "208 đạt ngưỡng 200" trong khi con số dùng được thật chỉ là 196 (<200).

**Công cụ chẩn đoán:** `src/trajectories/builder.py::build_trajectory` có
flag debug `CAGI_ED_DEBUG_BUILDER=1` (in lý do skip/eval từng event) —
dùng khi cần điều tra tương tự trong tương lai.

### 2 nguyên nhân riêng biệt, đã tách bạch rõ

**(A) Bug thật — đã sửa (2026-08-13):** `decode_bsctrace_transfer_row`
(BSC, category `external`/`internal` = native BNB transfer) dùng
`logIndex` từ BSCTrace làm `CanonicalEvent.log_index`. Nhưng native
transfer KHÔNG phải EVM log thật, nên BSCTrace luôn trả `logIndex=0` cho
MỌI leg loại này — xác nhận qua dữ liệu thật: 2 leg khác nhau của cùng 1
swap (`seed -> router` và `router -> seed`, cùng `tx_hash`) đều có
`logIndex=0` nhưng `traceIndex` khác nhau (0 vs 12). Vì
`CanonicalEvent.dedup_key() = (chain_id, tx_hash, log_index)`, 2 leg này
bị coi là TRÙNG NHAU và `_dedup()` trong `build_trajectory` chỉ giữ lại 1
— thường làm MẤT chính leg outbound từ seed, khiến trajectory trông như
không có hoạt động dù thực tế có. **Đã sửa**: dùng `traceIndex` (+ offset
theo category để không đụng `logIndex` thật của ERC-20) làm `log_index`
cho category `external`/`internal`. Xem
`src/normalize/decoder.py::_bsctrace_effective_log_index`.

Tác động của bug: không chỉ gây trajectory rỗng, mà còn làm SAI cả
`value_share` (mẫu số `outflow_by_src` bị thiếu 1 leg) và fan-out count
(`unique_dst` bị đếm thiếu) cho MỌI trajectory BSC có multi-leg native
swap trong cùng tx_hash — ảnh hưởng rộng hơn chỉ 17 dòng rỗng, có thể đã
âm thầm làm sai một số quyết định accept/reject khác trong lần mining đầu.
Sau khi sửa và mining lại: tỷ lệ rỗng giảm từ 8.2% xuống ~4.2%, và số
raw accepted của `qbridge_qubit_2022`/`bsc_token_hub_2022` cũng giảm
(một số candidate trước đây được accept SAI do fan-out bị đếm thiếu).

**(B) Đặc tính hệ thống (không phải bug) — vẫn tồn tại sau khi sửa (A):**
miner (`_passes_structural_filter`) kiểm tra `touches_contract` theo CẢ
2 CHIỀU (`e.src == contract or e.dst == contract`), nhưng
`build_trajectory` CHỈ mở rộng forward (chỉ chấp nhận event có
`src` đã nằm trong `node_depth`, bắt đầu từ seed). Nếu quan hệ DUY NHẤT
giữa candidate và contract trong cửa sổ mining là INBOUND (contract gửi
tiền TỚI candidate, vd candidate nhận payout từ 1 lần rút bridge trước
đó), miner vẫn chấp nhận candidate (đúng theo tiêu chí: có tương tác
với contract, không mixer, không fan-out) nhưng builder không có gì để
trace forward → trajectory rỗng. Đây LÀ giới hạn thật của thiết kế 2 tầng
lọc (miner nhẹ ở mức giao dịch, builder chặt ở mức `value_share`/
`time_horizon`) — KHÔNG sửa bằng cách nới lỏng miner (sẽ chấp nhận nhiều
candidate không đủ chất lượng hơn), chỉ có thể giảm bằng cách: (a) chấp
nhận tỷ lệ hao hụt này và mining dư ra để bù (đã áp dụng), hoặc (b) thêm
điều kiện `has_outgoing_event` vào `_passes_structural_filter` (làm miner
chặt hơn, giảm candidate pool nhưng tăng usable rate — CHƯA áp dụng, để
dành nếu cần tối ưu lại sau).

### Tỷ lệ rỗng theo incident (sau khi sửa bug A)

| parent_incident_id | Rỗng/Raw | Tỷ lệ |
|---|---|---|
| ronin_bridge_2022 | 3/44 | 6.8% |
| qbridge_qubit_2022 | 0/26 | 0.0% |
| feg_bridge_2024 | 0/31 | 0.0% |
| deltaprime_arbitrum_2024 | 3/45 | 6.7% |
| bsc_token_hub_2022 | 2/41 | 4.9% |

Không đồng đều tuyệt đối, nhưng KHÔNG còn lệch cực đoan như trước (0%–
13.6%) — phần lớn khác biệt trước đó tới từ bug (A), vốn ảnh hưởng nặng
hơn tới các chain/tx pattern có nhiều multi-leg native swap (BSC).

## 10. Bug thứ 2 phát hiện khi re-verify trajectory BSC sau bug (A) — `merge_events_into_semantic_actions` chọn sai representative (2026-08-13)

Sau khi sửa bug (A) ở mục 9 và freeze v0.3 (258 usable), người dùng yêu
cầu re-verify 2 positive trajectory BSC (`qbridge_qubit_2022`,
`bsc_token_hub_2022`) bằng cách rebuild lại từ `data/raw/` với decoder đã
sửa, đối chiếu với số liệu đã dùng để verify ban đầu. `qbridge_qubit_2022`
không đổi (22/22 action giống hệt — không tx nào trong trajectory này có
2 leg trùng tx_hash nên không rơi vào tình huống merge). Nhưng
`bsc_token_hub_2022` giảm từ 14 xuống CHỈ CÒN 10 action, mất đúng 4 action
`swap` thật (PancakeSwap V2) vốn là bằng chứng "khớp chính xác" đã dùng để
verify incident này ban đầu — phát hiện nghiêm trọng, dừng lại để chẩn
đoán trước khi đi tiếp (không tự sửa rồi âm thầm cập nhật).

### Nguyên nhân gốc — KHÔNG phải bug (A) tái phát, mà là hệ quả mới của bản fix (A)

`merge_events_into_semantic_actions()` (`src/normalize/decoder.py`) gộp
các `CanonicalEvent` cùng `tx_hash` thành 1 action `swap` khi có ≥2 token,
≤2 src, ≤2 dst — trước khi sửa, hàm này chọn `representative = tx_events[0]`
**sau khi sort theo `log_index` tăng dần**, không quan tâm hướng dòng tiền.

- **Trước bug (A):** leg native (`external`/`internal`) luôn có
  `log_index=0` cố định → luôn sort lên đầu → luôn được chọn làm
  representative. Với 4 swap bị mất, leg native TÌNH CỜ chính là leg
  outbound (`src=seed`, seed chi BNB) nên representative luôn đúng hướng
  — **đúng một cách tình cờ**, không phải do logic đúng.
- **Sau bug (A) được sửa:** leg native được offset `+600000`/`+700000`
  (để hết dedup nhầm, xem mục 9) → `log_index` native giờ LUÔN LỚN HƠN
  `log_index` ERC-20 thật → thứ tự sort ĐẢO NGƯỢC → representative giờ là
  leg ERC-20 (LP pool → seed, **inbound**) → action gộp có `src` = LP pool
  (không phải seed) → bị `build_trajectory` loại bỏ (builder forward-only,
  chỉ nhận `src` đã nằm trong `node_depth`) → action **biến mất khỏi
  trajectory**, chỉ còn xuất hiện lệch hướng trong "swap evidence ngoài
  trajectory".

**Phát hiện thêm khi verify sâu hơn (sau khi được người dùng yêu cầu sửa
và rebuild lại toàn bộ BSC):** cùng cơ chế đại diện-chọn-theo-log_index
này còn là 1 bug ĐỘC LẬP, **có từ trước** cả bug (A), không liên quan gì
tới native/BSCTrace — xảy ra ngay cả khi CẢ 2 leg đều là ERC-20 thật (2
`logIndex` thật, không có offset giả nào). Ví dụ: địa chỉ trung gian
`0x46ed8b4a...` trong `bsc_token_hub_2022` có nhiều swap WBNB↔BNBHACK mà
leg outbound (WBNB ra) tình cờ có `logIndex` LỚN HƠN leg inbound (BNBHACK
vào) → representative bị chọn nhầm thành leg inbound → toàn bộ các swap
này biến mất khỏi trajectory TỪ TRƯỚC KHI bug (A) tồn tại, không phải do
bản fix hôm nay gây ra — bản fix hôm nay chỉ tình cờ giúp lộ ra bug này
khi verify kỹ hơn.

### Cách sửa

Thay vì sort theo `log_index`, representative được chọn là leg XUẤT PHÁT
từ địa chỉ "tự tham chiếu" (self-referencing) — địa chỉ xuất hiện vừa là
`src` của 1 leg vừa là `dst` của leg còn lại trong CÙNG tx (đúng pattern
round-trip của 1 swap: trader chi token A ra, nhận token B về). Nếu không
tìm được địa chỉ tự tham chiếu (cấu trúc không rõ ràng), fallback về hành
vi cũ (sort theo `log_index`, lấy leg đầu) để an toàn. Xem code + comment
chi tiết tại `merge_events_into_semantic_actions()`. Test hồi quy mới:
`tests/test_decoders.py::test_merge_events_swap_representative_uses_outbound_leg_not_log_index_order`
(dựng 2 leg tổng hợp với log_index CỐ Ý ngược nhau, assert representative
luôn là leg outbound bất kể thứ tự log_index) — đóng lỗ hổng coverage mà
141 test cũ không bắt được bug này.

### Tác động sau khi sửa và rebuild lại toàn bộ

- `bsc_token_hub_2022` (positive): 14 (số cũ, SAI) → 63 action (rebuild
  đúng, phục hồi cả 4 swap của seed lẫn rất nhiều swap thật của
  `0x46ed8b4a...` trước đó bị ẩn hoàn toàn).
- `qbridge_qubit_2022` (positive): không đổi, 22 action.
- `qbridge_benign_control_2022` (hard-negative control gốc): 3 → **134**
  action — địa chỉ này hóa ra là 1 bot giao dịch PancakeSwap tự động rất
  tích cực (khớp đúng cảnh báo "bị chi phối bởi bot/MEV" đã ghi sẵn trong
  `incident_registry.csv` khi chọn), KHÔNG phải địa chỉ "ít giao dịch
  nhất" như tiêu chí chọn ban đầu tưởng — tiêu chí đó dựa trên dữ liệu
  decode sai. Vẫn giữ `label=0` (không liên quan QBridge/Qubit qua bất kỳ
  nguồn nào, cấu trúc PancakeSwap swap vẫn hợp lệ làm hard-negative), chỉ
  không còn là ví dụ "cá nhân sạch" — xem `data/dataset_card.md` mục Giới
  hạn.
- `bsc_token_hub_benign_control_2022`: không đổi, 3 action.
- Hard-negative mining BSC: `_passes_structural_filter` dùng chung
  `load_events_for_addresses` → `merge_events_into_semantic_actions`, nên
  TẬP candidate đã accept trước đó cũng bị ảnh hưởng (không chỉ nội dung
  trajectory của tập đã chọn) → phải mine lại từ đầu (không chỉ rebuild
  trajectory của tập cũ) bằng `scripts/run_hard_negative_remine_bsc_after_merge_fix.py`,
  dùng lại đúng `target_count`/`max_candidates_checked` đã dùng trước đó
  (`do_collect=False`, chỉ dùng cache đã có, không cần gọi mạng mới):
  `qbridge_qubit_2022` 26 → 34 accepted, `bsc_token_hub_2022` 69 → 70
  accepted (rồi -1 do QA leak, còn 69 — xem dưới). `ronin_bridge_2022`,
  `deltaprime_arbitrum_2024`, `feg_bridge_2024` (ETH/Arbitrum) KHÔNG re-mine
  (ngoài phạm vi bug này — golden regression test
  `test_regression_ronin_bridge_2022_matches_pilot_golden` xác nhận
  `ronin_bridge_2022` không đổi 1 bit sau bản fix).
- QA leakage round 3: phát hiện `0x58f876857a02d6762e0101bb5c46a8c1ed44dc16`
  (1 trong 3 địa chỉ leak quen thuộc từ các vòng trước) trùng giữa
  `bsc_token_hub_2022` và `qbridge_qubit_2022` sau khi mine lại. Loại
  `bsc_token_hub_2022__hn043` (chỉ 1 action, ít giá trị hơn), giữ
  `qbridge_qubit_2022__hn027` (8 action). 274 → 273 raw final.

### Tỷ lệ rỗng theo incident (sau cả 2 lần sửa bug, freeze v0.4)

| parent_incident_id | Rỗng/Raw | Tỷ lệ |
|---|---|---|
| ronin_bridge_2022 | 4/69 | 5.8% |
| qbridge_qubit_2022 | 0/34 | 0.0% |
| feg_bridge_2024 | 0/31 | 0.0% |
| deltaprime_arbitrum_2024 | 5/70 | 7.1% |
| bsc_token_hub_2022 | 3/69 | 4.3% |

### Giới hạn còn lại, chưa xử lý (ghi nhận trung thực, không suy đoán)

`merge_events_into_semantic_actions` là hàm DÙNG CHUNG cho mọi chain
(ETH/BSC/Arbitrum), fix hôm nay là tổng quát (không chỉ riêng BSC) —
nhưng CHỈ có bằng chứng thực nghiệm rằng `ronin_bridge_2022` không đổi
(golden test). `feg_bridge_2024`/`deltaprime_arbitrum_2024` KHÔNG có
golden fixture nên chỉ xác nhận được gián tiếp: so khớp action count
on-disk (build trước phiên sửa bug hôm nay) với action count rebuild lại
bằng code hiện tại — khớp y hệt (`feg_bridge_2024`: 9=9,
`deltaprime_arbitrum_2024`: 4=4) → 2 incident này cũng không đổi, nhưng
đây KHÔNG phải golden-test có khóa cứng nội dung, chỉ là so sánh 1 lần,
nên KHÔNG loại trừ hoàn toàn khả năng có tx pattern tương tự chưa gặp
phải trong dữ liệu hiện có. Khuyến nghị: thêm golden fixture cho
`feg_bridge_2024`/`deltaprime_arbitrum_2024`/`bsc_token_hub_2022` giống
`ronin_bridge_2022` để khóa cứng hành vi cho các lần sửa decoder sau này.

## 11. Đối chiếu bsc_token_hub_2022/qbridge_benign_control_2022 với báo cáo công khai + tiêu chí matching (2026-08-13)

Sau khi sửa xong bug (A) (mục 9) và bug đại diện swap (mục 10), người dùng
yêu cầu KHÔNG mặc định coi trajectory "không rỗng" là "đúng" — phải đối
chiếu ngoài (báo cáo công khai / tiêu chí matching gốc) trước khi tin dùng.

### Bước 1 — bsc_token_hub_2022 (63 action) vs báo cáo công khai: BAN ĐẦU KHÔNG khớp

Fetch lại Halborn + Elliptic (2 nguồn gốc). Elliptic: "The attacker
deposited **900,000 newly-minted BNB and 8 million USDT as collateral** on
**Venus Protocol** (BSC) và Banker Joe (Avalanche)". Trajectory 63-action
lúc đó CHỈ có PancakeSwap trading — hoàn toàn thiếu Venus Protocol, dù dữ
liệu vBNB (`0xa07c5b74c9b40447a954e1466938b865b6bbea36`) THẬT CÓ trong raw
cache của seed (3 tx native BNB: 600,000 + 300,000 + 0.1 = 900,000.1 BNB,
kèm vBNB mint về đúng seed cùng tx_hash) — chỉ là chưa được nhận diện vì
Venus chưa có trong `protocol_map.yaml`.

**3 bug MỚI phát hiện khi tích hợp Venus** (xem commit `4594af7`):
1. Trường hợp đối xứng (2 leg, seed<->vBNB contract đều tự tham chiếu) —
   representative selection cũ chọn nhầm leg ERC-20 "phản hồi" (vBNB mint,
   src=contract, không nằm trong node_depth) thay vì leg native thật
   (src=seed) → mất toàn bộ 900,000 BNB deposit khỏi trajectory. Fix: ưu
   tiên leg native (`token in ('BNB','ETH')`) khi ambiguous.
2. Nhánh 'swap' ghi đè `event_type` của representative thành 'swap' vô
   điều kiện, xóa mất nhãn `lending_deposit` đã gắn đúng trước đó qua
   `protocol_map.yaml`. Fix: giữ nguyên event_type protocol-specific
   (bridge/lending deposit-withdraw, mixer_or_exit) nếu đã có sẵn.
3. `amount_norm` nhánh 'swap' trung bình 2 leg — SAI cho deposit thật
   (trung bình BNB với vBNB, decimals/tỷ giá khác hẳn → lệch ~7 lần: tx lớn
   nhất báo cáo amount_norm=15.22 thay vì đúng 13.30 = log1p(600000)). Fix:
   event protocol-specific giữ `amount_norm` của representative, không
   trung bình.

**Kết quả sau khi sửa cả 3 và thêm Venus Protocol vào `protocol_map.yaml`
(`lending_protocols`, verified_onchain qua BscScan token label + đối
chiếu độc lập Blockscan/Bitquery)**: 63 → **66 action**, 3 action mới là
`lending_deposit` tới Venus Protocol, tổng amount thật = 899,995.8-900,000.1
BNB (log-scale, khớp CHÍNH XÁC "900,000 BNB" Elliptic báo cáo).

**Kiểm tra riêng `0x46ed8b4a...`** (địa chỉ trung gian PancakeSwap, chiếm
phần lớn action còn lại): xác nhận qua debug builder, action nhận
BNBHACK từ seed (tx `0x80c0a3a888`) có `value_share=0.82-0.88` (82-88%
tổng outflow của seed trong cửa sổ) — vượt xa ngưỡng `min_tainted_share=
0.05`, được giữ đúng theo rule `configs/data.yaml`, KHÔNG phải
over-expansion/bug logic builder. (Lưu ý: `value_share` vẫn dao động nhẹ
0.82↔0.88 giữa các lần build do hạn chế đã biết — `outflow_by_src` cộng
raw value across nhiều token khác nhau không có ý nghĩa toán học đầy đủ,
xem comment `TrajectoryConfig.allowlist` — nhưng KHÔNG đổi kết quả accept/
reject ở đây vì cả 2 giá trị đều vượt xa 5%.)

**Kết luận Bước 1**: bsc_token_hub_2022 (66 action) giờ khớp CHÍNH XÁC cả
provenance (2,000,000 BNB, đã verify từ trước) LẪN hành động hậu-exploit
chính (900,000 BNB Venus deposit) — đạt chuẩn "khớp chính xác" như Ronin.

### Bước 2 — qbridge_benign_control_2022 (134 action) vs tiêu chí matching gốc: KHÔNG pass

Tiêu chí matching gốc (Bước D, `_passes_structural_filter`): cùng chain,
cùng protocol contract, trong khung ±7 ngày, không mixer bất thường,
**không fan-out kiểu split (`unique_dst <= 3` tính trên các event có
`src=candidate`)**, volume > 0.

Chạy lại `_passes_structural_filter` thật cho `0xd76a7c3828...` (seed của
`qbridge_benign_control_2022`) với PancakeSwap V2 router, cửa sổ mining
gốc: **FAIL, reason=`fan_out_split_like_pattern`** — địa chỉ này có
**275 địa chỉ đích khác nhau** (`unique_dst=275`) trong 586 event tự nó
gửi đi, trong đúng cửa sổ ±7 ngày đã dùng để mining ban đầu. Đây rõ ràng
là hoạt động bot/MEV tự động quy mô lớn — không phải "địa chỉ ít giao
dịch nhất" như lý do chọn ban đầu (dựa trên dữ liệu decode SAI trước khi
sửa 4 bug hôm nay).

**Kết luận Bước 2**: KHÔNG pass tiêu chí matching gốc → phải loại khỏi
vai trò "hard-negative control gốc" theo đúng yêu cầu người dùng, mining
1 candidate thay thế qua đúng pipeline `mine_hard_negatives_for_incident`
(loại trừ toàn bộ địa chỉ đã dùng trong dataset). Xem
`data/dataset_card.md` mục Lịch sử sửa lỗi để biết candidate thay thế cụ
thể (nếu tìm được) hoặc quyết định cuối nếu không tìm được trong ngân
sách hợp lý.

## 12. Mở rộng dataset lên 8 incident (2026-08-14) — Chibi Finance, WooPPV2, UtopiaSphere

Mục tiêu: vượt minimum gate 6 incident (đang có 5), tiến gần ngưỡng target
10-15. Rà lại `experiments/logs/excluded_candidates.md` (chỉ có XPEXE Bridge,
vẫn không tìm được nguồn công khai) + 26 dòng `CHECK_MANUALLY_non_eth_chain`
trong `incident_candidates_amlguard.csv` (2 dòng đã dùng: DeltaPrime, BSC
Token Hub; 24 dòng chưa dùng). Lọc theo scope chain (`bsc`/`arbitrum`, loại
FTM/Optimism/Polygon/BASE vì `configs/data.yaml` không có collector) → 17
candidate khả thi. WebSearch từng candidate tìm nguồn công khai + bằng
chứng bridge/DEX — chốt 3 candidate có evidence mạnh nhất:

1. **Chibi Finance** (Arbitrum, 2023-06-27) — CertiK official report, exit
   scam $1M+, Tornado Cash funded, swap qua DEX aggregator + bridge Ethereum
   qua Multichain/Stargate, cuối cùng Tornado Cash.
2. **WooPPV2/WOOFi** (Arbitrum, 2024-03-05) — CUBE3/Beosin/Cyfrin report,
   $8.5M price manipulation, Tornado Cash funded, bridge sang chain khác.
3. **UtopiaSphere** (BSC, 2024-07-21) — CertiK official report, $521k flash
   loan, swap sang ETH + bridge sang địa chỉ Ethereum cụ thể.

Loại (evidence không đủ mạnh sau khi kiểm tra): Radiant Capital Jan 2024
(CSV) — CertiK/PeckShield/Beosin xác nhận exploit thật ($4.5M, exploiter
`0x826D5F4d...` xác nhận độc lập qua search) nhưng KHÔNG tìm được báo cáo
công khai mô tả hành động bridge/DEX cụ thể sau exploit (nguồn nói "1.9K
ETH vẫn nằm trong ví hacker" tại thời điểm đưa tin) — không đủ để dựng
outbound trajectory đối chiếu được. Magic/Treasure DAO 2025-03-25 (CSV) —
search chỉ tìm ra sự kiện Treasure DAO tháng 3/2023 (NFT theft, khác ngày,
không match), không xác nhận được sự kiện 2025-03-25 nào.

### Chibi Finance — chi tiết dựng trajectory

**Bug thật phát hiện khi tích hợp**: `decode_normal_tx_row`/
`decode_internal_tx_row` (đường ETH/Arbitrum, dùng cho native ETH tx) CHƯA
BAO GIỜ check `bridge_address_index` — chỉ `decode_bsctrace_transfer_row`
(BSC) có check này cho MỌI category. Hệ quả: 2 bridge_deposit thật (400 ETH
Multichain + 156.4 ETH Stargate, seed gọi trực tiếp `anySwapOutNative()`/
`swapETH()` kèm native ETH value) bị decode thành `event_type='transfer'`
chung chung, mất hoàn toàn nhãn bridge dù dữ liệu on-chain đầy đủ. Sửa bằng
cách thêm `bridge_address_index` param cho cả 2 hàm, đồng bộ với BSCTrace.
Rebuild lại toàn bộ 5 incident cũ (golden test xác nhận KHÔNG đổi — vì
không incident nào trước đó có bridge deposit qua native ETH tx thuần, chỉ
qua ERC-20 hoặc BSC).

**Xác định `start_block` thật**: `BlockNumber` trong
`incident_candidates_amlguard.csv` (104090264) chỉ là thời điểm chuẩn bị
(gửi 0.2 ETH gas, 2023-06-23), KHÔNG phải thời điểm drain thật (2023-06-27,
4 ngày sau). Nếu dùng block đó làm `start_block`, cửa sổ 72h mặc định
(ước lượng ~4800 block/giờ cho Arbitrum) sẽ KHÔNG phủ tới thời điểm drain
thật — vì tốc độ block Arbitrum thực tế giai đoạn này ~14,400 block/giờ
(gấp 3 lần ước lượng), một hạn chế đã biết của `APPROX_BLOCKS_PER_HOUR`
(comment gốc đã ghi rõ đây chỉ là xấp xỉ thô). Xác định đúng bằng cách fetch
window rộng hơn thủ công, tìm block giao dịch nhận đồng loạt USDC.e/WETH/
WBTC/USDT/ARB (105366596, khớp `2023-06-27 07:34:20 UTC`) rồi dùng đúng
block đó làm `start_block`.

**Xác nhận 2 địa chỉ bridge**: KHÔNG suy đoán từ tên — tìm địa chỉ qua
WebSearch (Stargate ETH Router, Multichain Router V6), rồi XÁC NHẬN LẠI
bằng cách đối chiếu với dữ liệu on-chain thật của chính seed: 2 địa chỉ tìm
được qua search khớp CHÍNH XÁC với 2 địa chỉ `to` thật trong txlist của
seed, VÀ function selector gọi thật (`anySwapOutNative`/`swapETH`) khớp
đúng chữ ký hàm chuẩn của từng bridge — xác nhận kép (search + on-chain).

## 13. Mở rộng dataset lên 12 incident (2026-08-14) — XKingdom, Wault.Finance, Paraluni, LianGo

Vòng mở rộng thứ 2 (8→12), sau khi rà hết 19 candidate `CHECK_MANUALLY_
non_eth_chain` còn lại. Lọc scope chain (bsc/arbitrum) → 12 candidate khả
thi. WebSearch từng vụ, chốt 4: XKingdom (Arbitrum), Wault.Finance (BSC),
Paraluni (BSC), LianGo (BSC). Loại Redruby DAO (không tìm được nguồn công
khai) và Whale Loans (CertiK xác nhận exploit thật nhưng tiền vẫn nằm
nguyên trong ví attacker, không có bridge/DEX/mixer tiếp theo) — xem
`experiments/logs/excluded_candidates.md`.

### Phát hiện bug thật khi điều tra QA leakage cho Paraluni: dữ liệu cache của `qbridge_qubit_2022` bị THIẾU (không đầy đủ)

Khi kiểm tra địa chỉ `0xdd90e5e87a2081dcf0391920868ebc2ffb81a1af` (1 trong
2 ví trung gian trọng tâm của `qbridge_qubit_2022`, cũng bị Paraluni chạm
tới 1 lần) để xác nhận đây có phải leak thật hay chỉ là địa chỉ dùng
chung phổ biến, đã fetch lại raw data cho địa chỉ này với cửa sổ RỘNG HƠN
(14,740,000-16,010,000, phủ cả khung QBridge lẫn Paraluni). Kết quả: 481
địa chỉ gửi / 789 địa chỉ nhận độc lập trong cửa sổ đã kiểm tra — xác nhận
đây là địa chỉ dùng chung phổ biến (hành vi CEX/OTC hot wallet), KHÔNG
phải liên hệ rửa tiền riêng giữa QBridge và Paraluni — đã thêm vào danh
sách loại trừ của QA leak test.

**Tác dụng phụ quan trọng hơn**: cửa sổ fetch rộng hơn này VÔ TÌNH lấp đầy
1 lỗ hổng dữ liệu THẬT trong cache gốc của `qbridge_qubit_2022` — phát
hiện 3 giao dịch chuyển tiếp THẬT từ `0xdd90e5e8...` sang 3 địa chỉ mới
(`0x5180db02...`, `0xfdcd5daf...`, `0x768f2a7c...`), tổng ~43.8 (log-scale)
USDC/USDT, xảy ra chỉ vài giờ sau hoạt động gốc của QBridge (2022-01-28
22:18 - 2022-01-29 04:32 UTC, so với hoạt động gốc 20:42-21:57 UTC cùng
ngày) — **hoàn toàn nằm trong cửa sổ `time_horizon_hours=72` CHÍNH THỨC
của QBridge** (`start_block=14742000` → `end_block=14828400`, 3 tx này ở
block 14771563/14772965/14779021, đều trong khoảng này). Nghĩa là: dữ
liệu cache GỐC của QBridge (thu thập ở phiên rất sớm của dự án) đã THIẾU
3 sự kiện thật này ngay từ đầu — không phải do window sai, mà do lần fetch
gốc (rất có thể do giới hạn phân trang BSCTrace) không lấy đủ. Đây là bug
dữ liệu-hoàn-chỉnh (data completeness), không phải bug logic code.

**Đã sửa**: cache đã đầy đủ hơn (vẫn giữ nguyên do_collect=False, dùng lại
cache mới), rebuild lại `qbridge_qubit_2022` → **22 → 25 action**, cập
nhật golden fixture (`tests/fixtures/golden/qbridge_qubit_2022_events.
golden.json`). Nội dung 22 action gốc KHÔNG đổi (chỉ thêm 3 action mới ở
cuối, mở rộng thêm 1 hop) — golden test cũ vẫn PASS về mặt "không mất dữ
liệu", chỉ cần cập nhật để "thêm dữ liệu" không bị coi là lỗi.

**Giới hạn CHƯA xử lý (ghi nhận trung thực)**: không loại trừ khả năng các
địa chỉ dùng chung khác (ở CÁC incident khác, không chỉ QBridge) cũng có
cache gốc thiếu tương tự — việc rà soát TOÀN BỘ 12 incident cho vấn đề này
nằm NGOÀI phạm vi của vòng mở rộng hiện tại (chỉ phát hiện tình cờ khi
điều tra 1 leak cụ thể). Khuyến nghị: thêm 1 bước kiểm tra định kỳ
"re-fetch với cửa sổ rộng hơn, so sánh action count" cho các incident cũ
trong tương lai nếu có thời gian.

## 14. Rà soát cache/pagination hệ thống 2026-08-14 — 6 bug độc lập, sửa toàn diện

Theo yêu cầu người dùng sau freeze v0.7: rà soát cache/pagination completeness
cho 11 incident "primary" còn lại (đã fix riêng `qbridge_qubit_2022` ở mục
13). Audit ban đầu (re-fetch với cửa sổ RỘNG GẤP 3, so sánh action count)
cho thấy 6/15 dòng thay đổi — nhưng điều tra sâu hơn (thay vì chấp nhận số
liệu mới ngay) phát hiện đây KHÔNG phải 1 bug mà là **6 bug độc lập**
trong tầng cache/pagination + allowlist, nhiều bug nghiêm trọng hơn nhiều
so với "thiếu vài giao dịch":

**Bug 1 — thiếu dedup trong `_load_cached_rows`** (eth/arbitrum, khác
`_load_cached_bsctrace_rows` đã dedup từ trước): khi ≥2 file cache cửa sổ
chồng lấn tồn tại song song cho 1 địa chỉ (audit script tạo file mới CẠNH
file cũ), giao dịch trùng bị nạp 2 lần → sai `merge_events_into_semantic_
actions` (bằng chứng: `ronin_bridge_2022` cùng 1 tx nhưng amount_norm đổi
từ 12.119→10.786 giữa 2 lần build). Sửa: thêm dedup theo `(hash,
logIndex)` — copy nguyên tắc từ BSCTrace.

**Bug 2 — 2 client không tự dọn cache cũ trước khi fetch lại**: dù đã
dedup (bug 1), việc có ≥2 file cache chồng lấn VẪN gây lỗi merge tinh vi
hơn (không phải double-count đơn giản mà là ảnh hưởng tới logic phân loại
swap/split khi có leg gần-giống dư thừa) — bằng chứng: `chibi_finance_2023`
giảm 6→4 action sau khi dedup đúng (golden fixture GỐC vô tình đúng "6"
nhờ dữ liệu bị nhiễu theo 1 cách khác, không phải vì đúng). Sửa triệt để:
cả `EtherscanClient._fetch_all_pages` và `BscTraceClient.fetch_asset_
transfers[_bidirectional]` giờ XOÁ SẠCH file cache cũ của (address, action)
ngay trước khi bắt đầu fetch mới ("wipe-before-write") — đảm bảo tại mọi
thời điểm chỉ tồn tại ĐÚNG 1 thế hệ cache, phản ánh đúng lần fetch GẦN
NHẤT.

**Bug 3 — địa chỉ 1inch v4 AggregationRouter thiếu 1 ký tự cuối** trong cả
`protocol_map.yaml` VÀ `configs/data.yaml` (`0x1111111254fb6c44bac0bed
2854e76f90643097` — 39 hex, thiếu "d" cuối so với địa chỉ thật 40 hex).
So sánh chuỗi trong `known_protocol_allowlist` không bao giờ khớp → builder
coi 1inch là ví thường, mở rộng frontier VÀO router thật (nơi có hàng
triệu giao dịch không liên quan của người dùng khác) → nổ trajectory theo
cấp số nhân. Phát hiện qua `ronin_bridge_2022` (vụ pilot gốc, dùng xuyên
suốt dự án làm baseline "known-good"): rebuild sạch (sau khi sửa bug 1+2)
cho ra 7→25 action, trong đó nhiều action là SHIB/JPEG token không liên
quan gì tới vụ Ronin. Xác nhận qua Etherscan (WebSearch): nhãn "Aggregation
Router V4". Sửa: thêm ký tự "d" còn thiếu.

**Bug 4 — thiếu 2 địa chỉ hạ tầng DEX thật trong allowlist**, cùng loại
lỗi với bug 3 (không phải typo mà là CHƯA TỪNG được thêm):
- `0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640` — nhãn công khai "Uniswap
  V3: USDC 3" (pool thật, eth). Xác nhận qua WebSearch, giải thích phần
  còn lại của vụ nổ `ronin_bridge_2022` (sau khi sửa bug 3, còn 7→141
  action; sau khi thêm địa chỉ này, còn 7→113 — hợp lý, không còn đi lạc
  vào hạ tầng chưa allowlist).
- `0xdef171fe48cf0115b1d80b88dc8eab59176fee57` — nhãn công khai "Velora
  v5: Augustus Swapper" (tiền thân ParaSwap, DEX aggregator ~1.7 triệu
  giao dịch, bsc). Phát hiện qua QA leakage test báo lỗi giả (địa chỉ này
  xuất hiện ở CẢ `qbridge_qubit_2022` VÀ `utopiasphere_2024`) — điều tra
  xác nhận đây là hạ tầng DEX phổ biến, không phải leak thật, và ĐÚNG cách
  xử lý là allowlist (như 1inch) chứ không chỉ loại trừ trong test.

**Bug 5 — `frontier` dùng set-comprehension** (`{a.dst for a in traj.
actions}` trong `expand_and_build_trajectory`): thứ tự lặp của Python set
phụ thuộc hash-seed ngẫu nhiên của process, KHÁC NHAU giữa các lần chạy
riêng biệt (dù cùng dữ liệu cache) — ảnh hưởng thứ tự xử lý địa chỉ, có
thể ảnh hưởng kết quả `merge_events_into_semantic_actions` nếu logic đó
nhạy với thứ tự input. Phát hiện qua `wault_finance_2021` cho số action
khác nhau (11 vs 15) giữa 2 lần rebuild riêng biệt dùng CÙNG 1 cache. Sửa:
thay bằng `dict.fromkeys(a.dst for a in traj.actions)` — khử trùng lặp
NHƯNG giữ đúng thứ tự xuất hiện đầu tiên, ổn định/tái lập được giữa các
lần chạy process khác nhau.

**Bug 6 — cache theo (chain, address) không phân biệt incident/cửa sổ
thời gian** (giới hạn kiến trúc, CHƯA sửa triệt để): khi 2 incident khác
nhau cùng chạm 1 địa chỉ hạ tầng phổ biến (không phải leak — xem Exclusions
trong dataset_card.md) nhưng với cửa sổ block khác nhau, ai fetch SAU cùng
sẽ ghi đè cache của người trước (với BSCTrace, filename không hề mã hoá
window nên đè trực tiếp; với Etherscan, dù có 2 file riêng, bug 1+2 đã sửa
loại bỏ double-count nhưng KHÔNG giải quyết việc chọn đúng window cho từng
incident). Ảnh hưởng cụ thể: `qbridge_qubit_2022` ↔ `paraluni_2022` (địa
chỉ `0xdd90e5e8...`, đã xác nhận CEX/OTC hot wallet phổ biến qua on-chain
thật 2026-08-14: 481 gửi/789 nhận độc lập, không phải leak). **Xử lý thực
dụng** (không phải sửa kiến trúc, phạm vi quá lớn nếu làm triệt để — sẽ
yêu cầu re-mine phần lớn hard-negative BSC): chốt 1 thứ tự fetch CUỐI CÙNG
cố định, freeze kết quả, ghi rõ giới hạn trong dataset_card.md mục Giới
hạn #3.

**Nguồn phi-quyết-định thứ 2, KHÔNG phải bug code**: sau khi sửa cả 6 bug
trên, `wault_finance_2021`/`paraluni_2022` vẫn cho số action dao động nhẹ
giữa các lần fetch riêng biệt. Điều tra xác nhận: 2 địa chỉ trong 2 incident
này (`0xc1e16013...`, `0xf2ce52e3...`) có SỐ LƯỢNG GIAO DỊCH RẤT LỚN, chạm
gần giới hạn phân trang 100 trang (`max_pages=100`) của BSCTrace API — với
địa chỉ "hot" cỡ này, pagination cursor của 1 API thật có sai số nhỏ tự
nhiên giữa các lần gọi riêng biệt (không kiểm soát được từ phía client).
Đã chốt 1 kết quả ổn định (xác nhận lặp lại 2 lần liên tiếp không đổi) làm
golden fixture chính thức.

**Bài học phương pháp luận quan trọng nhất**: KHÔNG chấp nhận số liệu mới
(dù "nhiều hơn = đầy đủ hơn" trông có vẻ hợp lý) mà KHÔNG điều tra nguyên
nhân gốc trước. Lần đầu rebuild sạch `ronin_bridge_2022` cho 25 action (sau
sửa bug 1+2) trông như "phát hiện thêm dữ liệu thật" — nhưng khi in ra chi
tiết, phát hiện ngay có SHIB/JPEG token hoàn toàn không liên quan tới vụ
Ronin, dẫn tới phát hiện bug 3. Nguyên tắc: mọi thay đổi số liệu lớn PHẢI
in ra và đọc nội dung cụ thể, không chỉ so sánh con số tổng.

## 15. Re-verify + sửa gốc bug #6 theo yêu cầu người dùng (2026-08-14, v0.9)

Sau freeze v0.8 (mục 14), người dùng yêu cầu cụ thể: (1) re-verify riêng
`ronin_bridge_2022` (mức tăng lớn nhất, 7→113 action, 16 lần) trước khi
chấp nhận, (2) sửa GỐC bug #6 (cache key theo `(chain, address, incident_id)`)
thay vì giữ vá tạm, (3) xác nhận rõ scope RQ1, (4) freeze lại nếu đổi số.

**Bước 1 — Re-verify `ronin_bridge_2022`**: dùng `math.expm1(amount_norm)`
để tái tạo giá trị raw từ `provenance_events` (KHÔNG phải `traj.actions` —
kiến trúc builder chỉ mở rộng OUTBOUND từ seed, 2 sự kiện Ronin Bridge là
INBOUND) — cho đúng 25,500,000.000000026 USDC + 173,600.0 ETH, khớp
chính xác 2 con số gốc dùng để verify pilot từ session đầu tiên của dự án.
0 lần `bridge_deposit` trong 113 action (đúng thiết kế). 0/113 dòng trùng
signature. Kết luận: sạch, không cần sửa gì thêm cho incident này — toàn
bộ tăng trưởng 7→113 đến từ swap/transfer downstream thật (do bug #3/#4 ở
v0.8 khiến trước đây pipeline dừng mở rộng sớm).

**Bước 2 — Sửa gốc bug #6**: đổi cache key từ `(chain, address)` sang
`(chain, address, incident_id)` — thêm 1 tầng thư mục `data/raw/{chain}/
{address}/{incident_id}/`. Áp dụng cho CẢ 2 client:
- `EtherscanClient._cache_path`/`_fetch_all_pages`/`fetch_normal_txs`/
  `fetch_erc20_transfers`/`fetch_internal_txs`: thêm tham số `incident_id`.
- `BscTraceClient._cache_path`/`fetch_asset_transfers`/
  `fetch_asset_transfers_bidirectional`: thêm tham số `incident_id`.
- `src/pipeline/incident_pipeline.py`: thread `incident_id` qua
  `collect_address_raw_data`, `_load_cached_rows`, `_load_cached_bsctrace_rows`,
  `load_events_for_addresses`, `_load_events_etherscan`, `_load_events_bsctrace`,
  `find_provenance_bridge_events`, `find_swap_evidence`.
- `src/collect/hard_negative_miner.py`: `fetch_contract_counterparties`,
  `_passes_structural_filter` nhận thêm `incident_id` — dùng
  `parent_incident_id` làm scope (tất cả candidate của 1 parent dùng CHUNG
  1 window khi mining, xem `_mining_window`, nên scope theo parent là đủ,
  không cần scope theo từng `hard_negative_id` riêng).

**Test bắt buộc** (theo đúng yêu cầu): `test_two_incidents_same_address_
different_window_do_not_overwrite` ở cả `tests/test_collector.py` (Etherscan)
và `tests/test_bsctrace_client.py` (BSCTrace) — giả lập incident_a fetch
trước (window hẹp), incident_b fetch sau (window khác hẳn, CÙNG địa chỉ),
xác nhận cache của incident_b không bị mất khi incident_a fetch LẠI lần
nữa sau đó. Cả 2 test đều cố ý set up theo đúng kịch bản gây lỗi thật đã
xảy ra ở v0.8 (`qbridge_qubit_2022` ↔ `paraluni_2022`).

**Migration** (`scripts/migrate_cache_to_incident_scoped.py`): thay vì
re-fetch mạng toàn bộ (~440 hard-negative candidate, sẽ mất hàng giờ), nạp
ĐỘNG bản `incident_pipeline.py` CŨ (trước khi sửa, qua `importlib` đọc từ
git HEAD) để tính CHÍNH XÁC "processed address set" mà chính bản đó đã
dùng khi build ra kết quả v0.8 đang lưu trong `data/processed/`/golden
fixture — không suy đoán/nhớ lại từ memory. Bug thực gặp khi viết script:
`__file__` của module nạp động qua `importlib.util.spec_from_file_location`
trỏ vào đường dẫn TẠM (scratchpad), làm `REPO_ROOT`/`RAW_DIR` tự tính bị
sai hoàn toàn (trỏ ra ngoài repo) — phải ghi đè thủ công `old_mod.RAW_DIR`
bằng đường dẫn thật sau khi nạp module. Sau khi sửa: COPY (không di
chuyển, giữ file gốc) toàn bộ cache liên quan sang cấu trúc mới — xác
nhận lại toàn bộ 17/17 dòng `incident_registry.csv` cho action count
GIỐNG HỆT v0.8 (khớp từng số một).

**Bug phụ phát hiện khi verify**: `scripts/compute_dataset_v0.8/v0.9_stats.py`
và `tests/test_hard_negative_miner.py::test_real_hard_negative_registry_
reports_actual_count_vs_gate` dùng `row["hard_negative_id"]` (định danh
RIÊNG từng candidate) làm `incident_id` khi gọi `expand_and_build_trajectory`
để rebuild — nhưng cache LÚC MINING lại scope theo `parent_incident_id`
(dùng chung cho mọi candidate của 1 parent) → mismatch làm TOÀN BỘ
hard-negative trajectory rebuild ra RỖNG (usable tụt từ 425 xuống 5!) khi
mới bật scoping. Đã sửa: đổi cả 2 nơi dùng `row["parent_incident_id"]`
thay vì `row["hard_negative_id"]` — khớp đúng quy ước scope lúc mining.

**Xác nhận cache isolation THẬT** (không chỉ test giả lập): fetch lại
`paraluni_2022` với cửa sổ RIÊNG của nó cho địa chỉ dùng chung
`0xdd90e5e8...` (trước đó "mượn ké" dữ liệu phản ánh cửa sổ của
`qbridge_qubit_2022`, do 2 vụ này fetch cùng địa chỉ ở các thời điểm khác
nhau) — kết quả: `paraluni_2022` 23→**24** action (+1 action thật, bằng
chứng bug #6 THẬT SỰ đã ảnh hưởng dữ liệu, không chỉ lý thuyết), trong khi
`qbridge_qubit_2022` **giữ nguyên 52 action tuyệt đối** — xác nhận cache
2 incident giờ hoàn toàn độc lập.

**Bước 3**: xác nhận `circulate_2023` chính thức nằm ngoài 11 incident
RQ1 chính (đã quyết định từ trước v0.8, ghi lại rõ ràng bằng câu trả lời
trực tiếp trong `dataset_card.md` theo yêu cầu, không chỉ ngầm hiểu qua bảng).

**Bước 4**: freeze v0.9 — số liệu tổng (raw/usable/prefix row) KHÔNG đổi
so với v0.8 (`paraluni_2022`'s +1 action không đổi số prefix vì đã chạm
trần công thức `generate_prefixes`), chỉ đổi nội dung golden fixture của
`paraluni_2022`. `pytest tests/ -v`: 157/157 pass (0 skip, kể cả 2 test
"real data" — QA leakage + gate ≥200).
