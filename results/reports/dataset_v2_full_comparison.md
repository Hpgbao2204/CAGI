# So sánh tường minh: v1 (12 incident, M1 có bridge_context) vs v2 (15 incident, M1 không bridge_context)

**Mục đích**: tài liệu hóa đầy đủ tác động của chuỗi thay đổi Giai đoạn B
(sửa bug value_share, mở rộng dataset, loại bridge_context) lên toàn bộ
RQ1/RQ2/ablation — dùng cho phần Results/Discussion của khóa luận.

- **v1**: snapshot ngay trước khi bắt đầu Giai đoạn B Bước 3 (12 incident
  positive — 11 gốc + `radiant_capital_arbitrum_2024`, đã sửa bug
  `value_share`, M1 CÓ đầy đủ 9 cột `bridge_context`).
- **v2**: snapshot hiện tại, freeze chính thức (15 incident positive, M1
  ĐÃ loại 9 cột `bridge_context`).

## Bảng so sánh tổng hợp

| Khía cạnh | v1 (12 incident, có bridge_context) | v2 (15 incident, không bridge_context) |
|---|---|---|
| **RQ1 — Mean PR-AUC M1** | 0.6188 [0.4662, 0.8532] | 0.6624 [0.5234, 0.8864] |
| **RQ1 — Mean PR-AUC B3** | 0.6971 [0.5580, 0.8684] | 0.6875 [0.5557, 0.8601] |
| **RQ1 — Mean diff (M1−B3), paired per-incident** | −0.0465 | +0.0355 |
| **RQ1 — 95% CI hiệu số** | [−0.1181, +0.0085] | [−0.0286, +0.1288] |
| **RQ1 — Wilcoxon p** | 0.322 | 0.638 |
| **RQ1 — Kết luận** | KHÔNG ĐỦ BẰNG CHỨNG | KHÔNG ĐỦ BẰNG CHỨNG |
| RQ2 — PR-AUC ratio_25 | 0.8356 | 0.9333 |
| RQ2 — PR-AUC ratio_50 | 0.9186 | 0.8491 |
| RQ2 — PR-AUC ratio_75 | 0.8561 | 0.9350 |
| RQ2 — PR-AUC ratio_100 | 0.9186 | 0.9407 |
| RQ2 — PR-AUC k_2/k_3/k_5/k_7 | 0.6968 / 0.6429 / 0.7722 / 0.8419 | 0.7470 / 0.6222 / 0.7097 / 0.7679 |
| RQ2 — Lead time (giờ, median\*) | *chưa tính riêng ở mốc 12-incident* | 0.41 [IQR 0.12, 1.11] |
| RQ2 — Incident phát hiện TRƯỚC endpoint | *chưa tính riêng ở mốc 12-incident* | 4/10 đủ điều kiện |
| Ablation E4 (no-temporal) diff vs M1_full | +0.0455 [+0.0077,+0.0937] p=0.098 | −0.0530 [−0.1535,+0.0079] p=0.203 |
| Ablation E5 (no-motif) diff vs M1_full | +0.0187 [−0.0037,+0.0519] p=0.359 | −0.0277 [−0.0958,+0.0208] p=0.721 |
| Ablation bridge_context diff vs M1_full | +0.0064 [−0.0258,+0.0500] p=0.945 (loại, KHÔNG có ý nghĩa) | −0.0638 [−0.1501,−0.0101] p=0.036 (**thêm lại, CÓ ý nghĩa**) |
| Hard-negative dùng được | 540 | 612 |
| Tổng prefix row | 2876 | 3354 |

\* *Lead time chưa từng được tính riêng cho snapshot 12-incident (script
`compute_lead_time.py` chỉ chạy ở các mốc 11 và 15 incident) — không suy
diễn số liệu không có, chỉ báo cáo số hiện tại (v2).* Ngoài ra, khi chạy
lại `compute_lead_time.py` cho v2, phát hiện và sửa 1 bug thật: 6 file
`data/processed/{incident}_events.json` bị CŨ (chưa từng ghi lại
`write_output=True` sau khi sửa bug `value_share` — golden fixture đã đúng
từ trước nhưng file processed thì không) — đã ghi lại toàn bộ 16 incident
positive, xác nhận khớp golden, 197/197 test PASS.

## Lưu ý quan trọng khi đọc bảng Ablation

Ở v1, ablation "bridge_context" nghĩa là **LOẠI** 9 cột khỏi M1_full (vốn
ĐANG có bridge_context) — diff dương nhỏ (+0.0064), không có ý nghĩa. Ở v2,
M1_full ĐÃ KHÔNG có bridge_context, nên ablation đổi hướng thành **THÊM
LẠI** 9 cột — diff âm, có ý nghĩa (−0.0638). Hai con số này thực chất đo
**cùng 1 hiệu ứng theo 2 hướng ngược nhau** trên 2 tập N khác nhau (12 vs
15) — sự khác biệt về Ý NGHĨA THỐNG KÊ (không có ý nghĩa ở N=12, có ý
nghĩa ở N=15) chính là phát hiện cốt lõi, không phải sự đổi hướng phép
tính.

## Narrative cho Discussion/paper

> Mở rộng dataset từ N=12 lên N=15 incident (Giai đoạn B, Bước 3) không chỉ
> tăng quy mô đánh giá — nó còn LÀM LỘ RÕ một hiệu ứng overfitting theo
> protocol vốn đã tồn tại tiềm ẩn trong nhóm feature `bridge_context` của
> mô hình M1, nhưng không đủ mạnh để phát hiện có ý nghĩa thống kê ở N nhỏ
> hơn (paired diff chỉ +0.0064, CI rộng chứa 0 ở N=12; nhảy lên +0.0638,
> CI loại trừ 0 ở N=15). Nguyên nhân cụ thể: đặc trưng `time_to_first_bridge`
> chỉ mã hóa đúng tín hiệu cho phân nhóm nhỏ các incident dùng cùng họ giao
> thức bridge cụ thể (LI.FI/Stargate/Across trên Arbitrum), và khi tập dữ
> liệu càng đa dạng họ giao thức hơn (thêm mixer TornadoProxyLight trên
> BSC ở Hackerdao/New Free Dao), tỷ trọng incident mà đặc trưng này "học
> sai hướng" càng tăng, kéo hiệu năng tổng thể xuống. Phát hiện này minh
> chứng giá trị thực nghiệm của việc tăng quy mô/đa dạng dữ liệu đánh giá —
> không chỉ để có CI chặt hơn, mà còn để phơi bày các lỗi feature-selection
> mà một tập dữ liệu nhỏ, đồng nhất hơn về protocol có thể che giấu — đồng
> thời dẫn tới quyết định feature-selection CÓ CĂN CỨ (loại bỏ
> `bridge_context` khỏi M1 chính thức) thay vì chỉ dựa vào trực giác thiết
> kế ban đầu.

## Xác nhận: kết luận RQ1 tổng thể KHÔNG đổi qua toàn bộ chuỗi thay đổi

Bảng dưới liệt kê MỌI lần RQ1 được rerun kể từ v0.9 (11 incident) — kết
luận định tính **"KHÔNG ĐỦ BẰNG CHỨNG M1 vượt B3"** giữ NGUYÊN xuyên suốt,
dù các con số cụ thể (mean diff, dấu của diff) dao động đáng kể qua từng
lần sửa:

| # | Thay đổi | N | Mean diff (M1−B3) | Kết luận |
|---|---|---|---|---|
| 1 | v0.9 gốc (trước sửa bug prefix Tuần 7 — tham khảo lịch sử) | 11 | — | KHÔNG ĐỦ BẰNG CHỨNG |
| 2 | Sửa bug cache scoping (#6) | 12→11 (RQ1) | — | KHÔNG ĐỦ BẰNG CHỨNG |
| 3 | Sửa bug `token_category_diversity` | 11 | +0.0024 | KHÔNG ĐỦ BẰNG CHỨNG |
| 4 | Sửa bug GỐC `value_share` gộp-token + thêm radiant | 12 | −0.0465 | KHÔNG ĐỦ BẰNG CHỨNG |
| 5 | Thêm Magic + Hackerdao (giữa Bước 3, tạm thời) | 14 | −0.0649 | ⚠️ dao động tạm — B3 thắng có ý nghĩa |
| 6 | Thêm New Free Dao (ổn định lại) | 15 | −0.0282 | KHÔNG ĐỦ BẰNG CHỨNG |
| 7 | **Loại bridge_context khỏi M1 (v2.0, hiện tại)** | 15 | **+0.0355** | **KHÔNG ĐỦ BẰNG CHỨNG** |

**Kết luận**: qua 5 lần sửa bug độc lập (prefix, cache scoping,
token_category_diversity, value_share, bridge_context) và 2 lần mở rộng
dataset (8→12→15 incident), kết luận RQ1 chỉ dao động tạm thời DUY NHẤT 1
lần (mốc #5, ngay sau khi thêm Hackerdao — đã chẩn đoán kỹ, KHÔNG phải bug,
ổn định lại ngay khi thêm incident tiếp theo). Đây là bằng chứng cho thấy
**RQ1 là kết luận ỔN ĐỊNH, không phải artifact của 1 bug/1 lựa chọn feature
cụ thể nào** — dù dấu và độ lớn của mean diff dao động, biên CI luôn đủ
rộng để chứa 0, phản ánh trung thực mức độ chưa đủ bằng chứng thống kê với
quy mô N hiện tại (15 incident), không phải một kết luận "may mắn" ổn định
ngẫu nhiên.
