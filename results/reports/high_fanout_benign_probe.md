# Probe: M1 trên benign entity fan-out cao có nhãn công khai xác nhận

(Tuần 9 bổ sung — theo yêu cầu sau khi E6 phát hiện M1 làm tệ hơn trên "unmatched
negative" mà danh tính KHÔNG được xác nhận công khai. Bài test này dùng 4 candidate
market maker/exchange hot wallet có **nhãn công khai xác nhận** — evidence mạnh hơn
hẳn nhóm unmatched-negative.)

**⚠️ Kết quả: INCONCLUSIVE — không phải "M1 xử lý tốt" hay "M1 thất bại".** 0/4
candidate tạo ra được trajectory có fan_out>3 (mục tiêu ban đầu) trong ngân sách
API nhỏ đã dùng. Nguyên nhân đã điều tra và xác định cụ thể (không phải bug),
xem Bước 2. **Không mở rộng thêm API call để "cố" ra kết quả** (đúng ràng buộc
"không ép đủ số").

## Bước 1 — 4 candidate đã xác minh (KHÔNG dùng contract router/aggregator)

| Entity | Loại | Chain | Nhãn công khai | Nguồn xác minh |
|---|---|---|---|---|
| Wintermute | market_maker | eth | `Wintermute 2` | [etherscan.io/address/0x000002cb…](https://etherscan.io/address/0x000002cba8dfb0a86a47a415592835e17fac080a), cross-verify qua blockscan.com |
| Binance | exchange_hot_wallet | bsc | `Binance: Hot Wallet 20` | [bscscan.com/address/0xf977814e…](https://bscscan.com/address/0xf977814e90da44bfa03b6295a0616a897441acec), cross-verify qua blockscan.com (cũng gắn nhãn giống hệt trên etherscan.io/arbiscan.io) |
| Jump Trading | market_maker | arbitrum | `Jump Trading` | [etherscan.io/address/0xf584f872…](https://etherscan.io/address/0xf584f8728b874a6a5c7a8d4d387c9aae9172d621), cross-verify qua blockscan.com |
| Cumberland (DRW) | market_maker | arbitrum | `Cumberland: 0xad6...862 Fund` | [etherscan.io/address/0xad6eaa73…](https://etherscan.io/address/0xad6eaa735d9df3d7696fd03984379dae02ed8862), cross-verify qua blockscan.com |

Xác minh qua **blockscan.com** (multichain explorer độc lập) — fetch trực tiếp
Etherscan/BscScan bị chặn bot (HTTP 403), nên dùng nguồn thay thế đáng tin cậy
tương đương. Cả 4 địa chỉ đều được xác nhận là **EOA** (không phải smart
contract) và **entity thật có nhãn công khai**, không suy đoán từ tên ví. Chi
tiết đầy đủ: `metadata/high_fanout_benign_candidates.csv`.

## Bước 2 — Build trajectory: 3/4 rỗng, 1/4 quá nhỏ — ĐÃ ĐIỀU TRA NGUYÊN NHÂN

Dùng `max_iterations=0` (chỉ hoạt động trực tiếp của candidate, không mở rộng
frontier — đúng kế hoạch, tránh bùng nổ API call cho entity fan-out siêu cao),
cửa sổ block = từ `start_block` của 1 incident tham chiếu (cùng chain), kéo dài
`config.time_horizon_hours` (72h) về phía trước — **cùng quy ước window đã dùng
xuyên suốt dự án cho positive/hard-negative**.

| Entity | Chain | Window (block) | n_actions | fan_out |
|---|---|---|---|---|
| Wintermute | eth | [21506058, 21526218] (~72h quanh feg_bridge_2024, T12/2024) | **0** | — |
| Binance HW20 | bsc | [21933735, 22020135] (~72h quanh bsc_token_hub_2022, T10/2022) | 2 | **1** |
| Jump Trading | arbitrum | [273285000, 273630600] (~72h quanh deltaprime_arbitrum_2024, T11/2024) | **0** | — |
| Cumberland | arbitrum | [105366596, 105712196] (~72h quanh chibi_finance_2023, T6/2023) | **0** | — |

**Đã kiểm tra trực tiếp cache JSON thô** (không suy đoán) cho 3 trường hợp rỗng:
API trả về hợp lệ (`status`/`message`/`result` đúng cấu trúc Etherscan/Arbiscan),
**nhưng `result: []`** — nghĩa là các địa chỉ này **THẬT SỰ không có giao dịch
nào** trong đúng cửa sổ 72h đã chọn (không phải lỗi decode/parse).

**Nguyên nhân cụ thể (không phải bug pipeline):**
1. **Cửa sổ thời gian không khớp hoạt động thật của từng địa chỉ trên đúng
   chain đó.** Cửa sổ được neo theo block của 1 incident THAM CHIẾU (chỉ để có
   volume band tương đối, không bắt buộc — đúng lưu ý trong yêu cầu), KHÔNG
   phải theo hoạt động thật của candidate. Ví dụ: Wintermute 2 — theo
   blockscan.com — "hoạt động từ 09/2022, gần đây có vẻ đã ngừng hoạt động",
   trong khi cửa sổ neo theo feg_bridge_2024 là 12/2024 — RẤT CÓ THỂ rơi vào
   giai đoạn địa chỉ này đã ngừng dùng.
2. **Market maker đa-chain nhưng phân bổ hoạt động RẤT LỆCH theo chain.**
   Jump Trading: 96% portfolio trên Ethereum, chỉ ~$1.3M trên Arbitrum (theo
   blockscan.com) — cửa sổ 72h trên riêng Arbitrum nhiều khả năng không bắt
   được hoạt động nào. Tương tự Cumberland (Arbitrum chỉ là 1 trong ~15 chain
   phụ, không phải trọng tâm).
3. **`fan_out` đo OUTGOING diversity — hot wallet sàn giao dịch có thể fan-IN
   cao (nhận nhiều deposit từ user) nhưng fan-OUT thấp trong cửa sổ ngắn**
   (gom/quét định kỳ về ít địa chỉ, không phải gửi liên tục ra nhiều nơi).
   Binance HW20: 77 event liên quan trong cửa sổ nhưng chỉ 4 event có
   `src=chính địa chỉ này`, cả 4 đều tới cùng 1 destination → fan_out=1. Đây
   là bằng chứng cụ thể cho thấy giả định ban đầu "hot wallet = fan-out cao"
   **không đúng ở khung 72h** — hot wallet có thể fan-in cao hơn fan-out.

**Xác nhận mục tiêu: 0/4 candidate có fan_out THẬT > 3** trong ngân sách probe
này — không đạt mục tiêu ban đầu.

## Quyết định: DỪNG, không mở rộng thêm

Theo đúng ràng buộc ("test NHỎ, không ép đủ số/mở rộng mining đại trà"), **không
retry thêm cửa sổ thời gian khác hay gọi thêm API** để cố tạo ra trajectory
fan_out>3. Đã dùng khoảng 12 API call (đúng ước lượng ban đầu ~10) — dừng ở đây.

## Bước 3 — Kết quả (dữ liệu có được, dùng với caveat rõ ràng)

Chỉ 1/4 candidate (Binance HW20) có trajectory hợp lệ, nhưng **fan_out=1**
(KHÔNG đạt >3 — không phải đúng nhóm cần test). Dùng `m1_final.joblib`
(KHÔNG train lại) dự đoán: **prob=0.0001 → đúng (negative)** — nhưng con số
này **KHÔNG trả lời được câu hỏi ban đầu** (M1 có false-positive trên benign
fan-out CAO không), vì candidate duy nhất có dữ liệu lại không phải fan-out cao.

### Bảng so sánh 3 nhóm (cùng model `m1_final.joblib`, cùng threshold=0.5, cùng full-length trajectory)

| group | n | mean_fan_out | % bị gắn nhãn positive (threshold=0.5) |
|---|---|---|---|
| matched_hard_negative (fan_out≤3, chính thức) | 509 | 1.29 | 0.00% |
| unmatched_negative (E6, fan_out>3, danh tính CHƯA xác nhận) | 460 | 2.66 | 0.22% |
| high_fanout_benign_labeled (nhóm mới, nhãn công khai xác nhận) | **1** | **1.00** | 0.00% |

**Dòng thứ 3 KHÔNG đại diện cho câu hỏi "fan-out cao, danh tính benign xác
nhận"** — n=1 và fan_out=1 (không cao) — chỉ giữ lại để minh bạch dữ liệu thô,
không dùng làm bằng chứng kết luận.

## Bước 4 — Kết luận cho paper (Limitations/Future Work)

Thay vì một câu khẳng định chung chung, đây là bằng chứng đo được cụ thể để
đưa vào Limitations:

> **Đã thử probe M1 trên 4 entity benign fan-out cao có nhãn công khai xác
> nhận (Wintermute, Binance Hot Wallet 20, Jump Trading, Cumberland — market
> maker/exchange hot wallet, không phải contract hạ tầng). Kết quả
> INCONCLUSIVE: 0/4 tạo được trajectory fan_out>3 trong cửa sổ 72h neo theo
> thời điểm 1 incident tham chiếu — do (a) cửa sổ không khớp giai đoạn hoạt
> động thật của từng địa chỉ trên đúng chain, và (b) fan_out (đo outgoing)
> có thể không phải chỉ số đúng để bắt "hoạt động cao" của hot wallet (vốn
> thiên về fan-in). Câu hỏi "M1 có false-positive trên benign fan-out cao
> không" vẫn CHƯA được trả lời dứt khoát bằng bằng chứng danh tính-xác-nhận
> — E6 (candidate danh tính chưa xác nhận, fan_out>3 thật) cho thấy PR-AUC
> giảm có ý nghĩa thống kê khi gặp fan-out cao, nhưng chưa tách được liệu đó
> là do fan-out THẬT SỰ đáng ngờ hay do các candidate đó (dù benign) có mẫu
> hành vi khác biệt vì lý do khác. Cần một vòng probe kỹ hơn (chọn cửa sổ
> theo hoạt động THẬT của từng địa chỉ, không neo theo incident) để trả lời
> dứt khoát — hoãn lại, ngoài phạm vi bài test nhỏ này.**

## Ràng buộc đã tuân thủ

- Không dùng contract router/aggregator (Uniswap V3 Router, 1inch...) — cả 4
  candidate đều là EOA thật, xác nhận qua blockscan.com.
- Không train lại M1 — chỉ `joblib.load(m1_final.joblib)` + `predict_proba`.
- Không hạ tiêu chí (không nới `min_tainted_share`, không đổi window để "moi"
  thêm dữ liệu) dù biết trước sẽ dẫn tới kết quả rỗng ở 3/4 candidate.
- Đã báo cáo ước lượng API call trước khi fetch (~10, thực tế dùng ~12) và
  KHÔNG vượt quá phạm vi đã báo.
- KHÔNG đổi kết luận RQ1/RQ2 chính thức — đây là test bổ sung độc lập.
