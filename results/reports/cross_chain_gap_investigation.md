# Điều tra gap cross-chain (Tuần 11, Bước 1-2) — KHÔNG sửa code, chỉ điều tra

**Bối cảnh:** Giai đoạn A phát hiện feature `cross_chain` "DEAD" vì mọi
trajectory hiện có chỉ có 1 `chain_id` — nghi ngờ đây là gap kiến trúc
(bridge event được ghi nhận nhưng không tiếp tục trace ở chain đích).
Điều tra này định lượng gap bằng dữ liệu đã có, KHÔNG gọi API mới.

## Bước 1 — Định lượng gap

### Số liệu tổng thể (11 incident, dữ liệu `data/processed/*_events.json` đã có)

| Incident | Chain | Tổng action | `bridge_deposit` | `bridge_withdraw` | Action sau `bridge_deposit` cuối |
|---|---|---|---|---|---|
| ronin_bridge_2022 | eth | 113 | 0 | 0 | — |
| qbridge_qubit_2022 | bsc | 52 | 0 | 0 | — |
| feg_bridge_2024 | eth | 9 | 0 | 0 | — |
| deltaprime_arbitrum_2024 | arbitrum | 5 | 1 | 0 | 0 |
| bsc_token_hub_2022 | bsc | 74 | 0 | 0 | — |
| chibi_finance_2023 | arbitrum | 16 | 2 | 0 | 8 (từ nhánh khác, không phải tiếp nối bridge) |
| wooppv2_2024 | arbitrum | 6 | 2 | 0 | 0 |
| utopiasphere_2024 | bsc | 17 | 11 | 0 | 1 |
| xkingdom_2024 | arbitrum | 13 | 1 | 0 | 12 (từ nhánh khác, không phải tiếp nối bridge) |
| wault_finance_2021 | bsc | 15 | 0 | 0 | — |
| paraluni_2022 | bsc | 24 | 0 | 0 | — |
| **TỔNG** | | **344** | **17** | **0** | |

**17/344 = 4,94% tổng số action là `bridge_deposit`** (0% `bridge_withdraw`
outbound — hợp lý vì `bridge_withdraw` là dòng tiền VÀO, không phải điểm
"rời khỏi trajectory"). **6/11 incident (55%) không có action bridge nào**
trong outbound trajectory.

### Kiểm tra chính xác: có tiếp nối TỪ chính bridge contract không?

Với **cả 17/17 (100%) action `bridge_deposit`** đã kiểm tra trực tiếp: **0
action nào sau đó có `src` = địa chỉ contract bridge đó** (đã grep chính
xác trên dữ liệu thật, không suy đoán). Ví dụ cụ thể:

```
deltaprime_arbitrum_2024: bridge_deposit -> Across Protocol SpokePool -> continuation=0
chibi_finance_2023:       bridge_deposit -> Multichain Router V6      -> continuation=0
chibi_finance_2023:       bridge_deposit -> Stargate (LayerZero)      -> continuation=0
wooppv2_2024 (x2):        bridge_deposit -> Stargate (LayerZero)      -> continuation=0
utopiasphere_2024 (x11):  bridge_deposit -> LI.FI Diamond             -> continuation=0
xkingdom_2024:            bridge_deposit -> Stargate (LayerZero)      -> continuation=0
```

**Nguyên nhân đã xác nhận qua code** (`src/trajectories/builder.py`,
`build_trajectory()`): đây là **THIẾT KẾ CÓ CHỦ ĐÍCH**, không phải bug bỏ
sót — logic frontier expansion **cố ý KHÔNG mở rộng qua địa chỉ đã verify
trong allowlist** (bridge/DEX/mixer contract), vì đây là hạ tầng dùng
chung bởi rất nhiều user không liên quan — nếu tiếp tục trace qua đó sẽ
lẫn lộn hoạt động của người dùng khác vào trajectory. Hệ quả PHỤ (không
chủ đích): **không có cách nào hiện tại để "nhảy" sang chain đích** sau
một bridge event, vì kiến trúc không hề fetch/lưu thông tin destination
chain của bridge event đó.

### Trường hợp `ronin_bridge_2022` — KHÔNG phải ví dụ của gap này

Đã kiểm tra trực tiếp: `ronin_bridge_2022` có **0 `bridge_deposit`/
`bridge_withdraw`** trong toàn bộ 113 action (111 transfer + 2 swap).
`seed_address` (`0x098b716b...`) là địa chỉ **ETHEREUM** đã nhận tiền
SAU KHI vụ hack Ronin Bridge (xảy ra trên chain Ronin, KHÔNG nằm trong
phạm vi 3 chain hỗ trợ eth/bsc/arbitrum) đã hoàn tất — nghĩa là bước
"cross-chain" thật sự (Ronin → Ethereum) xảy ra **TRƯỚC ĐIỂM BẮT ĐẦU** của
trajectory này, hoàn toàn ngoài tầm quan sát của pipeline vì lý do khác
(chain Ronin không được hỗ trợ, không phải vì "bridge event bị bỏ sót
theo dõi"). 2 action `swap` (qua Uniswap V3/1inch) **ĐÃ ĐƯỢC GHI NHẬN ĐẦY
ĐỦ** — vì chúng xảy ra hoàn toàn trong phạm vi chain Ethereum mà trajectory
này đang theo dõi, không cần "nhảy chain" gì cả.

**Kết luận:** ví dụ `ronin_bridge_2022` mà đề bài nêu ra **KHÔNG minh họa
đúng gap đang điều tra** — gap thật (bridge_deposit không có tiếp nối) chỉ
xuất hiện ở **5/11 incident (45%): deltaprime_arbitrum_2024,
chibi_finance_2023, wooppv2_2024, utopiasphere_2024, xkingdom_2024** — cả
5 đều dùng bridge THẬT SỰ đa chain (Across Protocol, Multichain, Stargate/
LayerZero, LI.FI Diamond) có khả năng đi tới các chain KHÁC (bao gồm cả
eth/bsc/arbitrum mà dự án đã hỗ trợ) — đây là gap CÓ THẬT và có thể lượng
hóa: **17 action bridge_deposit, 100% không có dữ liệu chain đích.**

## Bước 2 — Ước lượng chi phí sửa

### Việc cần làm (nếu quyết định sửa)

1. **Decode protocol-specific bridge event để lấy destination chain +
   recipient CÓ EVIDENCE** (đúng yêu cầu proposal mục 5.5: "chỉ dùng
   mapping có evidence: explicit destination recipient") — đã kiểm tra
   `metadata/protocol_map.yaml` (158 dòng): **hiện KHÔNG có bất kỳ trường
   `destination_chain`/`dst_chain` nào** — cần decode TỪ ĐẦU log event
   thật của TỪNG loại bridge (Stargate `Swap`/`SendMsg` event, Across
   Protocol `FundsDeposited` event, LI.FI `LiFiTransferStarted` event,
   Multichain `LogAnySwapOut` event) — **4 protocol khác nhau, 4 ABI/schema
   khác nhau**, cần đọc tài liệu/verify từng cái riêng (không suy đoán từ
   tên hàm).
2. **Mở rộng `src/collect/`** để dispatch fetch sang chain đích (có thể là
   1 trong 3 chain đã hỗ trợ, HOẶC 1 chain hoàn toàn mới — Stargate/LI.FI
   hỗ trợ hàng chục chain, không biết trước cho tới khi decode xong bước
   1).
3. **Mở rộng `src/trajectories/builder.py`** — kiến trúc hiện tại
   (`CanonicalEvent.chain_id` đơn, `Trajectory` không có khái niệm
   "current chain", `expand_and_build_trajectory` dùng 1 `client` cố định
   theo `chain` truyền vào) cần đổi để hỗ trợ **frontier đa-chain** (1
   trajectory có thể có node ở nhiều chain khác nhau) — đây là thay đổi
   kiến trúc, không phải patch nhỏ.
4. **Rebuild lại TOÀN BỘ 11 incident** (không thể áp dụng tăng dần) — vì
   thêm continuation sau bridge sẽ đổi `trajectory_len`/action
   count/feature MỌI incident có bridge event, và feature `cross_chain_*`
   chỉ có ý nghĩa nếu tính lại trên TOÀN BỘ dataset (không thể trộn
   trajectory cũ 1-chain với trajectory mới đa-chain trong cùng so sánh) —
   khớp đúng kỷ luật "rebuild đầy đủ sau thay đổi kiến trúc" đã áp dụng
   xuyên suốt dự án (Tuần 7/9).

### Ước lượng quy mô

- **Phạm vi hưởng lợi thật sự nhỏ:** chỉ 5/11 incident, 17 bridge_deposit
  action — KHÔNG phải toàn bộ dataset.
- **Công sức decode protocol:** 4 protocol khác nhau, mỗi protocol cần
  đọc contract ABI/event thật (không có sẵn tài liệu trong repo) — tương
  đương công sức đã bỏ ra ở Tuần 2-3 khi decode `bridge_deposit`/
  `bridge_withdraw` lần đầu, nhân 4.
- **Số API call mới CHƯA THỂ ước lượng chính xác** cho tới khi decode
  xong bước 1 (không biết trước chain đích/recipient) — đây là quy trình
  2 pha (decode trước, fetch sau), không thể báo số liệu cụ thể ngay bây
  giờ như các lần fetch trước (nơi biết trước target).
- **Rủi ro:** recipient ở chain đích CÓ THỂ không phải chính `seed_address`
  (bridge có thể gửi tới địa chỉ khác) — nếu vậy, đây lại mở ra 1 trajectory
  MỚI hoàn toàn (không phải "nối tiếp"), cần suy nghĩ lại cả khái niệm
  "trajectory" hiện tại (hiện là 1 seed = 1 trajectory).

**Kết luận Bước 2: đây là thay đổi kiến trúc LỚN, tương đương hoặc vượt
công sức 1 tuần làm việc gốc (Tuần 2-4, khi build decoder/collector lần
đầu) — không phải patch nhỏ.** Với phạm vi hưởng lợi hiện tại (5/11
incident, 17 action), khuyến nghị: **để dành cho 1 giai đoạn riêng (không
gộp vào Giai đoạn B hiện tại — mining thêm incident KHÔNG đụng tới vấn đề
này), quyết định dựa trên việc liệu RQ nào thực sự cần feature cross-chain
mới đáng giá công sức này.** Không tự ý bắt tay vào sửa — chờ quyết định.
