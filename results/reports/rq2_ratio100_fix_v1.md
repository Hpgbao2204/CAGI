# Sửa bug `generate_prefixes()` — thiên lệch có hệ thống ở mốc `ratio_100`

**Tuần 7, bổ sung.** Bug được phát hiện qua chẩn đoán câu hỏi "PR-AUC giảm
0.955 (ratio_75) → 0.852 (ratio_100)" (xem tài liệu lịch sử
[`rq2_ratio100_diagnostic.md`](rq2_ratio100_diagnostic.md)), sau đó xác nhận
là **bug tầng dữ liệu cần sửa gốc** (không chỉ ghi caveat) theo yêu cầu người
dùng, vì ảnh hưởng trực tiếp RQ2 — RQ quan trọng nhất của đề tài.

## Bug là gì

`generate_prefixes()` ([`src/features/extractor.py:32-54`](../../src/features/extractor.py#L32-L54))
dùng `specs.setdefault(length, label)`: khi nhiều mốc ratio (25/50/75/100%)
tính ra **cùng một độ dài nguyên** (luôn xảy ra với trajectory ngắn hơn 4
hành động), chỉ nhãn **được xử lý trước** (ratio nhỏ hơn, do duyệt thứ tự
0.25→0.5→0.75→1.0) được giữ lại. Hệ quả: **mọi trajectory ngắn hơn 4 hành
động không bao giờ có dòng nhãn `ratio_100`** — dòng full-length của nó bị
gán nhầm nhãn `ratio_25`/`ratio_50`/`ratio_75` thay vì `ratio_100`. Đây là
thiên lệch **có hệ thống, không ngẫu nhiên**: trajectory càng ngắn càng chắc
chắn bị loại khỏi mốc 100%, và phần lớn hard-negative rất ngắn (median 1-2
hành động) nên bucket `ratio_100` trước khi sửa gần như chỉ còn lại các
hard-negative dài/phức tạp nhất — một quần thể validation bị lệch mẫu.

## Bước 1 — Sửa `generate_prefixes()`

Thay `Dict[int, str]` (1 length → 1 label) bằng `Dict[int, List[str]]` (1
length → nhiều label). Không còn `setdefault` loại bỏ nhãn trùng — mỗi nhãn
trùng length sinh ra **1 dòng `PrefixSpec` riêng** (kiến trúc hiện tại là
1-label-1-dòng nên không thể "gộp nhãn vào 1 dòng"). Thêm `assert` bắt buộc:
mọi trajectory phải có đúng 1 dòng `ratio_100` với `length == len(trajectory)`.

Test mới trong `tests/test_no_future_leakage.py`:
- `test_generate_prefixes_short_trajectory_always_has_ratio_100` — xác nhận
  bất biến trên với n=1,2,3,4,10; xác nhận invariant chống leakage cũ
  (`sum(action_count_tho) == prefix_len`) vẫn giữ nguyên.
- `test_generate_prefixes_covers_ratios_and_k_values` (cập nhật) — xác nhận
  length trùng nhau (3 và 5 trong ví dụ 10-action) giờ giữ **cả 2** nhãn
  (`ratio_25`+`k_3`, `ratio_50`+`k_5`) thay vì mất 1 nhãn.

`pytest tests/ -v`: **170/170 pass** sau bước này.

## Bước 2 — Rebuild `features_v2.parquet`

Không gọi API on-chain nào — chỉ tính lại `generate_prefixes`/`extract_features`
trên trajectory đã build sẵn trong cache (`scripts/build_features_v2.py`).

| | Trước | Sau | Thay đổi |
|---|---|---|---|
| Tổng số dòng | 1304 | **2681** | **x2.06** (tăng nhiều hơn "nhẹ" như dự kiến ban đầu — báo cáo trung thực con số thật) |
| Leakage check (`sum(action_count_thô) == prefix_len`) | sạch | **sạch, 0/2681 vi phạm** | không đổi |

Xác nhận trực tiếp với 4 group đã nêu vấn đề trong chẩn đoán — % hard-negative
của group có mặt ở bucket `ratio_100`:

| Group | Trước | Sau |
|---|---|---|
| `xkingdom_2024` | 0% (0/32) | **100% (32/32)** |
| `feg_bridge_2024` | 0% (0/42) | **100% (42/42)** |
| `deltaprime_arbitrum_2024` | 12% (9/75) | **100% (75/75)** |
| `wooppv2_2024` | 8.6% (3/35) | **100% (35/35)** |

File cũ (1304 dòng) đã backup: `data/processed/features_v2_PRE_RATIO100FIX_backup.parquet`.

## Bước 3 — Chạy lại RQ2 prefix evaluation

`scripts/run_rq2_prefix_evaluation.py` không cần sửa (chỉ đọc `prefix_label`
cột có sẵn). Bảng PR-AUC theo mốc, trước vs sau:

| Bucket | PR-AUC trước | PR-AUC sau | Δ | n_fold hợp lệ trước | n_fold hợp lệ sau |
|---|---|---|---|---|---|
| ratio_25 | 0.7029 | 0.7029 | 0.0000 | 11/11 | 11/11 |
| ratio_50 | 0.8167 | **0.9545** | **+0.1379** | 10/11 | 11/11 |
| ratio_75 | 0.9545 | 0.9545 | 0.0000 | 11/11 | 11/11 |
| **ratio_100** | 0.8519 | **0.8864** | **+0.0345** | **9/11 (2 NaN)** | **11/11 (0 NaN)** |
| k_2 | 0.6318 | 0.6498 | +0.0180 | 10/11 | 11/11 |
| k_3 | 0.6706 | 0.6793 | +0.0087 | 9/11 | 10/11 |
| k_5 | 0.4682 | **0.7843** | **+0.3161** | 5/11 | 9/11 |
| k_7 | 0.8214 | 0.8036 | -0.0179 | 8/11 | 7/11 |

**Không còn fold nào NaN ở mốc `ratio_100`** — đúng như kỳ vọng, vì mọi
trajectory giờ đều có dòng `ratio_100` hợp lệ. Tác động lan rộng hơn dự
kiến ban đầu: `ratio_50` và `k_5` cũng bị bug tương tự (kém nghiêm trọng
hơn `ratio_100`) và cũng cải thiện rõ rệt — đúng bản chất của bug (mọi cặp
nhãn trùng length đều bị mất nhãn thứ 2 trở đi, không riêng `ratio_100`).

File cũ đã backup: `results/tables/rq2_prefix_evaluation_folds_PRE_RATIO100FIX_backup.csv`,
`main_table_PRE_RATIO100FIX_backup.csv`.

## Bước 4 — Chạy lại Bước 3-6 Tuần 7 cũ (lead time, leakage, biểu đồ, case study)

**Leakage check** (`scripts/run_rq2_leakage_check.py`) trên dữ liệu mới
(2681 dòng): **sạch — 0 vi phạm** ở cả 4 kiểm tra (endpoint-context cols,
model.feature_cols_, action_count invariant, prefix_len ≤ trajectory_len).

**Lead time** (`scripts/compute_lead_time.py`): kết luận tổng thể **ổn
định** — vẫn 7/11 incident đủ điều kiện, vẫn 2/7 chưa từng alert
(`feg_bridge_2024`, `wooppv2_2024`), vẫn 2/7 phát hiện trước endpoint
(`deltaprime_arbitrum_2024` lead=4826s, `utopiasphere_2024` lead=2348s,
**giá trị giống hệt trước sửa**), vẫn 3/7 phát hiện muộn, median lead time
1.00h IQR[0.82,1.17] **không đổi**. Chỉ 1/7 incident đổi chi tiết:
`xkingdom_2024` — mốc alert sớm nhất đổi từ `ratio_75`(length=10) sang
`ratio_50`(length=7), lead_time_sec đổi từ -17667 → -17116 (vẫn âm/muộn cả 2
lần, kết luận không đổi).

**Biểu đồ** (`scripts/plot_rq2_figures.py`): vẽ lại cả 3 file trong
`results/figures/` (PR curve theo mốc, detection-rate-vs-prefix, lead-time
distribution) trên dữ liệu mới.

**Case study** (`scripts/generate_alert_case_studies.py`):
- Case 1 (true positive, `qbridge_qubit_2022`, `ratio_25`): **không đổi**
  — prob=0.9981, threshold=0.9594, top motif/feature contribution giống hệt
  trước sửa (trajectory này dài 52 hành động, không thuộc diện bị bug ảnh
  hưởng).
- Case 2 (false positive): case cũ (`paraluni_2022__hn005`, `k_3`) **không
  còn là false positive thật nữa** trên dữ liệu đã sửa (prob=0.9510 <
  threshold=1.0000 → không kích hoạt alert) — đây là bằng chứng gián tiếp
  cho thấy composition bucket đã đổi thật sự (model/threshold huấn luyện
  lại trên tập ratio_50-đã-đầy-đủ dữ liệu hơn). Đã **chọn lại** một false
  positive thật từ `data/processed/rq2_oof_predictions.csv` (lọc
  `label==0 & oof_prob>=oof_threshold`), ưu tiên `paraluni_2022` (vẫn là
  incident yếu nhất, giữ nhất quán narrative với `error_analysis_v1.md`):
  **`paraluni_2022__hn013`, bucket `ratio_50`, prefix 5/9 hành động**,
  prob=0.9700, threshold=0.3517.

Tổng cộng **19 false positive thật** tồn tại trên toàn bộ dữ liệu mới
(label=0, oof_prob≥oof_threshold, trên 2595 dòng hard-negative).

File cũ đã backup: `results/tables/lead_time_results_PRE_RATIO100FIX_backup.csv`,
`results/reports/alert_case_studies_v1_PRE_RATIO100FIX_backup.md`.

`pytest tests/ -v`: **170/170 pass** sau toàn bộ Bước 1-4.

## ⚠️ Tác động lan sang RQ1 (Tuần 6) — ĐÃ XỬ LÝ, xem `rq1_v2_prefixfix.md`

> **Cập nhật:** người dùng đã quyết định cách xử lý (dedupe theo `(source_id,
> prefix_len)` trước khi pool) và RQ1 đã được rerun đầy đủ. Kết quả:
> **kết luận RQ1 không đổi (byte-for-byte giống hệt)** — xem chi tiết đầy đủ
> tại [`rq1_v2_prefixfix.md`](rq1_v2_prefixfix.md). Phần dưới đây giữ nguyên
> làm bối cảnh lịch sử của quyết định.

`features_v2.parquet` là file DUY NHẤT dùng chung cho cả RQ1 (Tuần 6) và
RQ2 (Tuần 7). Bug fix này làm file tăng từ 1304 → 2681 dòng — nghĩa là các
artifact chính thức của RQ1 hiện **không còn khớp với dữ liệu mới**:

- `results/tables/main_table.csv` (headline M1 PR-AUC=0.7190, B0-B3 so
  sánh) — tính trên 1304 dòng cũ.
- `results/models/m1_final.joblib` + `results/reports/model_card_m1.md` —
  M1 train trên 1304 dòng cũ (train_and_save_m1_final.py).
- `results/reports/rq1_answer.md`, `error_analysis_v1.md`,
  `rq1_ceiling_sensitivity.md` — toàn bộ số liệu dựa trên dữ liệu cũ.

Lý do KHÔNG tự ý rerun các artifact này: (1) yêu cầu hiện tại của người
dùng chỉ nêu rõ Bước 1-4 của **Tuần 7**, không nhắc RQ1; (2) RQ1 pool TẤT
CẢ 8 prefix bucket vào 1 model/fold — việc 1 trajectory ngắn giờ có thể
đóng góp tới 4 dòng trùng feature (khác nhãn `prefix_label`) vào cùng 1 tập
train/eval có thể làm lệch trọng số theo hướng ưu tiên trajectory ngắn hơn
so với trước, một hiệu ứng cần cân nhắc riêng (có thể cần thêm bước
dedup-theo-trajectory trước khi pool, hoặc chấp nhận vì mỗi dòng vẫn là 1
"góc nhìn" hợp lệ ở độ dài khác nhau) — đây là quyết định thiết kế nên hỏi
người dùng, không tự quyết. **RQ2 (bucket-by-bucket) không bị ảnh hưởng bởi
vấn đề này** vì mỗi bucket chỉ có đúng 1 dòng/trajectory.

**Khuyến nghị:** nếu RQ1 sẽ được trích dẫn cùng RQ2 trong luận văn, nên
rerun `run_full_evaluation_v1.py` + `train_and_save_m1_final.py` trên dữ
liệu đã sửa để nhất quán — nhưng cần quyết định trước cách xử lý duplicate
theo trajectory khi pool (xem trên). Đang chờ quyết định của người dùng
trước khi thực hiện.
