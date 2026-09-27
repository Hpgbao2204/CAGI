# Candidate bị loại khỏi incident_registry.csv

Ghi lại theo đúng ràng buộc "không hạ chuẩn evidence": nếu không xác nhận
được incident bằng ≥1 nguồn báo cáo công khai (CertiK/SlowMist/Beosin/
BlockSec/SharkTeam hoặc tin tức uy tín) VÀ tái dựng được ≥1 bridge link +
≥1 DEX action bằng bằng chứng on-chain thật, candidate bị loại — không cố
ép bằng cách suy đoán hoặc dùng AMLGuard làm ground truth.

## XPEXE Bridge (ETH, 2025-01-25) — LOẠI

- Seed từ `incident_candidates_amlguard.csv`: `0x269ff4d056252A30CAd249a4CD75cb9Bcfb1F46c`,
  start_block=21679440, screening_note=`STRONG_CANDIDATE_bridge_in_name`.
- **Lý do loại**: Tra cứu WebSearch nhiều biến thể query ("XPEXE Bridge hack
  exploit January 2025", "XPEXE token exploit rug pull crypto 2025", tra
  trực tiếp theo địa chỉ) — không tìm được BẤT KỲ báo cáo công khai nào
  (CertiK/SlowMist/Beosin/BlockSec/SharkTeam/tin tức) xác nhận sự tồn tại
  của incident này hay của một dự án tên "XPEXE Bridge". Etherscan UI
  (etherscan.io/address/...) trả 403 khi fetch trực tiếp nên không đối
  chiếu được label/tag chính thức.
- **Kiểm tra sơ bộ qua API thật** (2026-08-13): địa chỉ CÓ hoạt động on-chain
  thật quanh start_block (nhận 0.2046 ETH funding từ 0x3bdb03ad..., sau đó
  1 tx contract-creation (`to` rỗng) ở block 21679474, tương tác nhận WETH
  từ 0xa7a88f1f... và gọi tới `0xba122222...` — rất giống địa chỉ Balancer V2
  Vault thật, dạng pattern flash-loan/exploit-contract điển hình) — nhưng
  đây chỉ là suy luận từ cấu trúc giao dịch, KHÔNG phải xác nhận độc lập
  rằng đây là 1 incident đã công bố, và KHÔNG được dùng screening_note của
  AMLGuard làm ground truth thay thế.
- **Kết luận**: Loại khỏi registry theo đúng ràng buộc "threshold không được
  tự nới lỏng". Nếu sau này tìm được nguồn công khai xác nhận, có thể thêm
  lại.
- **Thay thế**: xem Bước C (tìm thêm incident từ nhóm CHECK_MANUALLY) để bù
  vào chỗ trống này.

## Vòng mở rộng 8→12 (2026-08-14) — rà 19 candidate CHECK_MANUALLY_non_eth_chain còn lại

Lọc theo scope chain (bsc/arbitrum, loại FTM/Optimism/Polygon/BASE vì
`configs/data.yaml` không có collector) → 12 candidate khả thi. WebSearch
từng candidate. Chốt 4: XKingdom (Arbitrum), Wault.Finance (BSC), Paraluni
(BSC), LianGo (BSC) — xem `metadata/annotation_guide.md` mục 13 cho chi
tiết evidence từng vụ.

### Redruby DAO (BSC, 2022-03-18) — LOẠI

WebSearch nhiều biến thể query không tìm được BẤT KỲ báo cáo công khai nào
(CertiK/SlowMist/Beosin/BlockSec/SharkTeam/PeckShield/tin tức) xác nhận sự
tồn tại của incident này. Không đủ evidence để xác nhận độc lập.

### Whale Loans (BSC, 2022-06-20) — LOẠI

CertiK có report ("Whale Loans Incident Analysis") xác nhận exploit thật
(lỗi k-invariant trong Stable AMM, ~$12,000 tổng thiệt hại qua 2 lần tấn
công) — NHƯNG báo cáo xác nhận rõ "All funds have been transferred from
two attacker contracts to the attacker account", KHÔNG có bridge/DEX/mixer
tiếp theo nào — tiền vẫn nằm nguyên trong ví attacker tại thời điểm phân
tích. Không đủ evidence bridge+DEX (hay evidence thay thế) để dựng outbound
trajectory có ý nghĩa.

## Vòng mở rộng 12→? (2026-08-27) — Giai đoạn B, Bước 3

### Novo Defi (BSC, 2022-05-29) — LOẠI

CertiK có report ("Novo Defi Incident Analysis") xác nhận exploit thật
(flash loan, ~278 BNB/~83K USD, khai thác `transferFrom()` thao túng giá
NOVO/PancakeSwap). Xác nhận qua on-chain thật: funding tại block 18224603
khớp chính xác BlockNumber AMLGuard (18224600).

**Lý do loại**: sau khi build trajectory (depth=2 + pipeline chính thức),
chỉ có **1 action** dùng được. Chẩn đoán sâu: cash-out thật đi qua node
trung gian `0x0376564615...` với **~30 lần chuyển đều đúng 2.398 BNB** tới
cùng 1 địa chỉ (`0x0d5550d5...`) — mẫu hình "smurfing"/chia nhỏ đều để né
phát hiện — NHƯNG mỗi lần chỉ chiếm ~3.3% tổng outflow của node trung gian
đó, dưới ngưỡng `min_tainted_share=5%` nên TOÀN BỘ 30 giao dịch này bị loại
dù là evidence thật. Đây là giới hạn kiến trúc CÓ THẬT của
`min_tainted_share` (không xử lý tốt trường hợp split đều thành nhiều phần
bằng nhau, mỗi phần đều nhỏ hơn ngưỡng) — không phải bug tại incident này,
nhưng KHÔNG sửa giữa Bước 3 (tránh gián đoạn kế hoạch mở rộng, đã hỏi ý
kiến người dùng) — ghi nhận lại đây làm ứng viên cho 1 investigation/fix
riêng trong tương lai (tương tự phát hiện bug value_share ở Radiant
Capital). Không hạ ngưỡng để ép vụ này vào dataset.

### LianGo (BSC, 2023-02-07) — LOẠI, thay bằng CirculateBUSD-CirculateWBNB

CertiK có report chính thức ("LianGo Protocol Incident Analysis") xác nhận
exploit thật (~$1.6M, LGT Pool bị rút cạn qua LP token giả mạo, Tornado
Cash gas funding 58 ngày trước) — NHƯNG khi kiểm tra độc lập địa chỉ Heist
trong CSV (`0xCb65d000ec8Ee9cB74D9b4Ffb8E6fF36EcA166Ae`), địa chỉ này
KHÔNG CÓ bất kỳ hoạt động on-chain nào trong toàn bộ cửa sổ 11 ngày trước
`BlockNumber` CSV (25680000-25776600, tương ứng 2023-02-07 đến
2023-02-18) — chỉ bắt đầu hoạt động từ 2023-02-18, lệch 11 ngày so với
ngày exploit CertiK báo cáo (2023-02-07). Không xác nhận độc lập được đây
là đúng địa chỉ/thời điểm exploit — loại theo đúng nguyên tắc "không suy
đoán, phải xác nhận qua dữ liệu on-chain thật". Thay bằng
CirculateBUSD-CirculateWBNB (đã tìm được từ đầu, CertiK report, địa chỉ
seed khớp chính xác và timing khớp chính xác giờ UTC báo cáo).
