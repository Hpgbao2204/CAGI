# Giai đoạn B, Bước 3 — Tổng kết mở rộng dataset (12 → 15 incident)

**Điểm dừng**: đạt mốc 15 incident (mục tiêu gốc của Giai đoạn B) sau khi xử
lý 4 candidate tuần tự (3 thêm thành công, 1 loại) — quyết định dừng tại
đây thay vì ép đủ 5 incident mới, vì các candidate còn lại đều yếu (Loser
Coin, ~$10K, rủi ro giống Whale Loans) hoặc ngoài phạm vi chain hỗ trợ
(Fantasm/Pragma/Exactly/Sonne/CryptoBottle/Polter/Clober — FTM/Optimism/
Polygon/BASE, chưa có collector).

## Bước 0 — Áp dụng depth-limit ngay từ đầu

Mọi incident mới đều fetch với `max_depth=2` trước (thay vì `max_depth=6`
gây nổ chi phí ở Ronin), theo dõi số địa chỉ mới sau round 0. Không incident
nào trong đợt này vượt ngưỡng cảnh báo (~150 call/round 0) — round 0 dao
động 0-19 địa chỉ mới (~0-60 call), thấp hơn nhiều so với dự đoán xấu nhất.

## Bước 1-2 — Candidate đã xử lý tuần tự

| # | Candidate | Chain | Kết quả | API call (ước tính) | Bug/phát hiện mới |
|---|---|---|---|---|---|
| 1 | Magic (Abracadabra MIM/GMX V2) | Arbitrum | ✅ Thêm (incident #13) | ~180 | 2 bug nhỏ: `rebuild_one` không fetch seed hoàn toàn mới; timeout API 30s quá ngắn cho contract lớn (LI.FI Diamond ~200s/response) |
| 2 | Hackerdao | BSC | ✅ Thêm (incident #14) | ~150 | Không |
| 3 | Novo Defi | BSC | ❌ Loại | ~15 (dừng sớm) | Phát hiện giới hạn kiến trúc thật: `min_tainted_share` không xử lý tốt mẫu hình "smurfing" (nhiều lần chia đều dưới ngưỡng 5%) — ghi vào `excluded_candidates.md`, KHÔNG sửa giữa chừng |
| 4 | New Free Dao | BSC | ✅ Thêm (incident #15) | ~400 | BSCTrace rate-limit thật (429 lặp lại) khi mine PancakeSwap V2 — sửa `max_retries=10` |

**Tổng API call đợt này: ~745**, tất cả trong ngưỡng an toàn (không có ca
nào giống Ronin — hàng trăm/nghìn call không hội tụ).

## Phát hiện quan trọng nhất: `TornadoProxyLight` (mixer BSC thiếu trong protocol_map)

Khi QA leakage giữa `hackerdao_2022` và `new_free_dao_2022`, phát hiện địa
chỉ `0x0d5550d52428e7e3175bfc9550207e4ad3859b17` trùng giữa 2 group. Điều
tra xác nhận: đây là contract thật (`ContractName=TornadoProxyLight` qua
`getsourcecode`), hành vi mixer xác nhận qua mẫu hình internal-tx (gửi tiền
nội bộ tới nhiều địa chỉ không liên quan, `gasUsed` đồng nhất ~893956 khớp
zk-SNARK verify của Tornado withdraw()) — **chính là endpoint Tornado Cash
mà CertiK/Halborn đã báo cáo cho CẢ HAI incident nhưng trước đó không bắt
được** (protocol_map.yaml chỉ có bản Tornado Cash trên ETH).

Sau khi thêm vào `protocol_map.yaml` + `configs/data.yaml` mixer_allowlist:
- `hackerdao_2022`: +4 action `mixer_or_exit` thật (trước đó là `transfer` thường).
- `new_free_dao_2022`: 9 → **12 action, TOÀN BỘ là `mixer_or_exit`** — khớp
  chính xác báo cáo ("$111,544 vào Tornado Cash"). **Nâng `eval_tier` từ
  `auxiliary_low_evidence` lên `primary`.**

Đây là bằng chứng cho thấy QA leakage không chỉ bắt lỗi rò rỉ — đôi khi còn
phát hiện lỗ hổng THIẾU trong protocol_map, cải thiện chất lượng dữ liệu.

## Bước 3 — Kiểm tra ổn định RQ1 sau mỗi 2-3 incident (đã thực hiện đúng 2 lần)

| Thời điểm | N incident | Mean diff (M1-B3) | 95% CI | Kết luận |
|---|---|---|---|---|
| Trước đợt mở rộng (12 incident) | 12 | -0.0465 | [-0.1181, +0.0085] | KHÔNG ĐỦ BẰNG CHỨNG |
| **Sau Hackerdao (14 incident)** | 14 | **-0.0649** | **[-0.1290, -0.0127]** | **⚠️ H1 BỊ BÁC BỎ (B3 thắng)** |
| Sau New Free Dao (15 incident) | 15 | -0.0282 | [-0.1565, +0.0902] | KHÔNG ĐỦ BẰNG CHỨNG (ổn định trở lại) |

Dao động giữa chừng đã được **chẩn đoán kỹ trước khi báo cáo** (không phải
bug — kiểm tra OOF predictions xác nhận hackerdao là ca đơn giản khiến M1
kém hơn B3 thật sự; ngược lại new_free_dao_2022 kéo mạnh theo hướng M1
thắng nhờ feature mixer typed). Đây chính là lý do quy trình yêu cầu kiểm
tra sau mỗi 2-3 incident thay vì đợi hết mới kiểm tra 1 lần — nếu chỉ dừng
lại sau Hackerdao, kết luận RQ1 sẽ SAI LỆCH so với bức tranh đầy đủ hơn.

## RQ1/RQ2/Ablation cuối cùng (15 incident, đã freeze)

**RQ1**: Mean diff (M1-B3) = -0.0282, 95% CI [-0.1565, +0.0902] —
**KHÔNG ĐỦ BẰNG CHỨNG**, nhất quán với kết luận trước khi mở rộng.

**RQ2** (mean PR-AUC theo mốc prefix, 15 fold):

| Mốc | PR-AUC |
|---|---|
| ratio_25 | 0.9667 |
| ratio_50 | 0.8491 |
| ratio_75 | 0.9350 |
| ratio_100 | 0.9407 |
| k_2/k_3/k_5/k_7 | 0.75/0.62/0.75/0.77 |

**Ablation E4/E5** — 2/3 vẫn không có ý nghĩa thống kê (no_temporal CI
[-0.0138,+0.0352]; no_motif CI [-0.0125,+0.1410]) nhưng **1 phát hiện MỚI
đáng chú ý**: `no_bridge_context` (loại 9 cột bridge-context) cho paired
diff **+0.0638, 95% CI [+0.0101, +0.1501]** — **KHÔNG chứa 0**, p=0.036 —
**loại bỏ bridge_context feature lại CẢI THIỆN M1 có ý nghĩa thống kê** trên
tập 15 incident. Đây là phát hiện MỚI, ngược hướng với giả thuyết "feature
càng nhiều càng tốt" — CHƯA điều tra sâu nguyên nhân (ngoài phạm vi Bước 3
này), đề xuất làm investigation riêng nếu cần cho Bước 6.

## Tổng số liệu dataset cuối (đã freeze)

| | Trước Bước 3 (12 incident) | Sau Bước 3 (15 incident) |
|---|---|---|
| Positive incident | 12 | **15** |
| Hard-negative dùng được | 540 | 612 |
| Tổng prefix row | 2876 | **3354** |
| Commit hash | `a7b1db9` | `8ab7e4c` |

## Việc CÒN LẠI của Giai đoạn B (chưa làm trong Bước 3 này)

- Bước 4 (gốc): thử lại probe benign fan-out cao (Wintermute, Binance HW20,
  Jump Trading, Cumberland) với time window đúng theo hoạt động thật từng
  địa chỉ.
- Bước 5: QA leakage cuối cùng toàn diện + freeze version chính thức với
  changelog rõ ràng.
- Bước 6: so sánh tường minh kết luận cũ (11 incident) vs mới (15 incident)
  cho TOÀN BỘ RQ1/RQ2/ablation (báo cáo này đã làm 1 phần, cần viết report
  riêng đầy đủ hơn nếu muốn chính thức hoá).
- Investigation riêng: nguyên nhân `no_bridge_context` cải thiện M1 có ý
  nghĩa (phát hiện mới ở trên).
- Investigation riêng (đã ghi nhận, chưa sửa): giới hạn `min_tainted_share`
  với mẫu hình "smurfing" (phát hiện ở Novo Defi).
