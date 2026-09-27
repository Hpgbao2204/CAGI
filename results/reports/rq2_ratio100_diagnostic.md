# [LỊCH SỬ — ĐÃ SUPERSEDE] Chẩn đoán: PR-AUC giảm ratio_75 (0.955) → ratio_100 (0.852)

> **⚠️ Tài liệu chẩn đoán lịch sử, KHÔNG dùng làm kết luận cuối.** Chẩn đoán ban
> đầu (bên dưới) mô tả đúng hiện tượng và định vị đúng nguyên nhân
> (`specs.setdefault()` trong `generate_prefixes()`), nhưng lúc đó kết luận
> tạm "không phải bug, có nguyên nhân cấu trúc" — sau khi người dùng xem xét
> lại, đây **THỰC SỰ LÀ BUG tầng dữ liệu** (thiên lệch có hệ thống loại bỏ
> mọi trajectory ngắn khỏi mốc `ratio_100`) và đã được **SỬA GỐC**. Xem báo
> cáo chính thức: [`rq2_ratio100_fix_v1.md`](rq2_ratio100_fix_v1.md) và commit
> sửa lỗi trong `src/features/extractor.py`. File này giữ lại chỉ để tham
> khảo lịch sử điều tra.

(Tuần 7, chẩn đoán bổ sung theo yêu cầu — xem `scripts/diagnose_ratio100_drop_v1.py` cho phần phân tích gốc.)

## (a) Tập incident/fold có giống nhau giữa 2 bucket không?

**CÓ, giống hệt nhau** — cả `ratio_75` và `ratio_100` đều có đúng 11 `held_out_group` (same_set = True). Không có incident nào chỉ xuất hiện riêng ở bucket 100%.

## (b) Vì tập incident giống nhau, điểm số giảm đến từ đâu?

### Nguyên nhân gốc (đã xác nhận trong code `src/features/extractor.py:32-54`)

`generate_prefixes()` duyệt `ratios=(0.25, 0.5, 0.75, 1.0)` theo đúng thứ tự này, dùng `specs.setdefault(length, label)` — nếu 2 mốc ratio khác nhau tính ra **cùng 1 độ dài nguyên** (hay xảy ra với trajectory ngắn), chỉ nhãn ratio **được xử lý TRƯỚC** (nhỏ hơn) được giữ. Hệ quả: một trajectory cần độ dài ≥ 4 hành động mới có thể có đủ 4 nhãn ratio_25/50/75/100 **phân biệt nhau**; trajectory ngắn hơn (1–3 hành động) **KHÔNG BAO GIỜ có dòng nhãn `ratio_100`** — dòng full-length của nó bị 'nuốt' vào ratio_75/50/25.

### Xác nhận bằng dữ liệu thật (số hard-negative theo group)

                          n_hard_neg_traj  median_len  n_traj_len_ge_4  pct_survive_to_ratio100  n_rows_ratio100_actual
group                                                                                                                  
bsc_token_hub_2022                     78         2.0               12                15.384615                      12
chibi_finance_2023                     35         1.0                2                 5.714286                       2
deltaprime_arbitrum_2024               75         1.0                9                12.000000                       9
feg_bridge_2024                        42         1.0                0                 0.000000                       0
paraluni_2022                          31         5.0               18                58.064516                      18
qbridge_qubit_2022                     46         3.5               23                50.000000                      23
ronin_bridge_2022                      75         1.0                3                 4.000000                       3
utopiasphere_2024                      33         1.0                4                12.121212                       4
wault_finance_2021                     32         6.5               20                62.500000                      20
wooppv2_2024                           35         1.0                3                 8.571429                       3
xkingdom_2024                          32         2.0                0                 0.000000                       0

`xkingdom_2024` và `feg_bridge_2024`: **100% hard-negative của chính 2 group này ngắn hơn 4 hành động** → 0 dòng `ratio_100` cho cả 2 → khi 2 group này là held-out fold ở bucket `ratio_100`, tập validation chỉ còn đúng 1 dòng (positive), **0 negative** → PR-AUC không xác định (NaN), bị loại khỏi mean (đúng, không nên gán 0 hay 1 giả).

`deltaprime_arbitrum_2024` (9/75 = 12%) và `wooppv2_2024` (3/35 = 8.6%): chỉ một phần rất nhỏ hard-negative đủ dài để sống sót tới `ratio_100`. Đây là **hiệu ứng chọn lọc**: số ít sống sót lại chính là các hard-negative **DÀI/PHỨC TẠP NHẤT** (deltaprime có hard-negative dài tới 224 hành động trong khi chính positive chỉ dài 5 hành động) — khó phân biệt hơn hẳn so với các hard-negative ngắn 'dễ' đã bị hút hết vào `ratio_25/50/75`. PR-AUC của 2 fold này vì vậy rơi từ 1.0 (ratio_75, có cả negative dễ) xuống 0.333 (ratio_100, chỉ còn negative khó).

### Bảng so sánh trực tiếp 2 bucket theo từng fold

                          n_val_75  pr_auc_75  n_val_100  pr_auc_100  delta_pr_auc
held_out_group                                                                    
bsc_token_hub_2022              41        1.0         13    1.000000      0.000000
chibi_finance_2023              18        1.0          3    1.000000      0.000000
deltaprime_arbitrum_2024        30        1.0         10    0.333333     -0.666667
feg_bridge_2024                  4        0.5          1         NaN           NaN
paraluni_2022                   25        1.0         19    1.000000      0.000000
qbridge_qubit_2022              39        1.0         24    1.000000      0.000000
ronin_bridge_2022               24        1.0          4    1.000000      0.000000
utopiasphere_2024               16        1.0          5    1.000000      0.000000
wault_finance_2021              28        1.0         21    1.000000      0.000000
wooppv2_2024                     9        1.0          4    0.333333     -0.666667
xkingdom_2024                   21        1.0          1         NaN           NaN

Mean ratio_75 (11/11 fold hợp lệ) = **0.9545**. Mean ratio_100 (9/11 fold hợp lệ, loại 2 fold NaN) = **0.8519**.

**Kết luận (b):** không phải một incident 'mới' kéo điểm xuống — mà (i) 2/11 fold trở thành *không xác định* và bị loại khỏi mẫu số (giảm cỡ mẫu), và (ii) 2/11 fold khác bị đánh giá trên một tập negative đã bị lọc thiên lệch về phía khó hơn, do đúng cơ chế dedup theo độ dài của `generate_prefixes()` — đây là hạn chế cấu trúc cần ghi chú rõ trong báo cáo RQ2 (bucket `ratio_100` không đại diện đầy đủ cho toàn bộ negative population, thiên lệch loại bỏ các hard-negative ngắn).

## (c) 0.852 (ratio_100) có khớp với PR-AUC M1 đã báo cáo ở RQ1/Tuần 6 không?

**KHÔNG khớp — và điều đó là đúng như kỳ vọng, không phải sai số cần sửa:**

| Nguồn | Giá trị | Cách tính |
|---|---|---|
| RQ1/Tuần 6 (`rq1_answer.md`, headline) | **0.7190** [0.5319, 0.8834] | Bootstrap incident-level point estimate — 1 model/fold train+eval trên TOÀN BỘ 1304 dòng (gộp cả 8 bucket ratio_25/50/75/100 + k_2/3/5/7), OOF pooled rồi mới bootstrap-resample 11 incident |
| RQ1/Tuần 6 (trung bình đơn giản 11 per-incident PR-AUC, cùng model/predictions) | **0.7892** | Trung bình cộng 11 giá trị PR-AUC/incident (KHÔNG bootstrap pooled) — cùng dữ liệu, khác cách gộp |
| RQ2/Tuần 7 (`ratio_100` bucket) | **0.8519** (9/11 fold) | 1 model/fold RIÊNG chỉ train+eval trên 105 dòng nhãn `ratio_100` — model, tập train, tập eval ĐỀU khác RQ1 |

**Nguồn khác biệt, xác nhận từng phần:**

1. **Phạm vi model/dữ liệu (nguyên nhân chính):** RQ1 đánh giá M1 như 1 model/fold học từ TẤT CẢ độ dài prefix trộn chung (train set 10 incident × 8 bucket); RQ2 `ratio_100` train một model/fold RIÊNG BIỆT, nhỏ hơn nhiều, chỉ thấy dữ liệu ở đúng 1 mốc độ dài. Đây là 2 thí nghiệm khác nhau, không phải cùng 1 con số báo cáo 2 lần.

2. **Cách chọn threshold: GIỐNG HỆT NHAU**, không phải nguồn khác biệt — cả 2 tuần đều dùng `evaluate_model_nested(..., target_fpr=0.01)` với inner Leave-One-Group-Out y hệt.

3. **Cách tính mean: có khác biệt, và tự nó cũng gây chênh lệch** — ngay trong Tuần 6, bootstrap pooled-then-scored (0.7190) và trung bình per-incident đơn giản (0.7892) đã lệch nhau ~0.07 trên CÙNG 1 tập dự đoán, vì pooling thay đổi trọng số theo số dòng/incident. Số 0.852 của Tuần 7 dùng cách tính thứ 3 (trung bình per-fold PR-AUC, loại các fold NaN) trên tập dữ liệu nhỏ hơn hẳn (105 dòng thay vì 1304).

**Khuyến nghị cho báo cáo RQ2:** không nên so trực tiếp '0.852 (ratio_100)' với '0.7190 (RQ1 headline)' như cùng 1 đại lượng — nên ghi rõ đây là PR-AUC của model chuyên biệt-theo-mốc-prefix, đánh giá trên tập validation nhỏ và bị lệch thành phần negative (thiếu hard-negative ngắn) ở mốc 100%, đồng thời loại 2/11 fold (xkingdom_2024, feg_bridge_2024) do không có negative nào để đánh giá ở mốc này.
