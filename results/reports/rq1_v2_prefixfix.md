# RQ1 rerun trên `features_v2.parquet` đã sửa bug `generate_prefixes`

**Tuần 6 (bổ sung), nối tiếp** [`rq2_ratio100_fix_v1.md`](rq2_ratio100_fix_v1.md).
RQ1 pool cả 8 prefix bucket vào 1 tập train/eval mỗi fold — khác RQ2 (đánh
giá từng bucket riêng). Sau khi sửa bug `generate_prefixes()` (1 độ dài có
thể mang nhiều nhãn), cần dedupe trước khi pool cho RQ1, rồi rerun toàn bộ
B0-B3+M1 để xác nhận kết luận RQ1 có đổi không.

## Bước 1 — Dedupe trước khi pool

Hàm mới `dedupe_pooled_prefixes()` ([`src/evaluation/nested_eval.py`](../../src/evaluation/nested_eval.py)):
nhóm theo `(source_id, prefix_len)`, giữ đúng 1 dòng/nhóm — feature 2 dòng
trong cùng nhóm giống hệt nhau (cùng length) nên chọn dòng nào không ảnh
hưởng kết quả; quy tắc chọn: ưu tiên nhãn theo đúng thứ tự cũ
(`ratio_25→ratio_50→ratio_75→ratio_100→k_2→k_3→k_5→k_7`), khớp với thứ tự
mà logic `setdefault` cũ (buggy) từng dùng để chọn "người sống sót" — chỉ
để có 1 quy tắc xác định/tái lập được, không ảnh hưởng giá trị feature.

**Bug tự phát hiện khi implement (đã sửa trước khi dùng số liệu):** bản đầu
tiên dùng cột `trajectory_id` làm khóa dedupe — nhưng trong codebase này
`trajectory_id` thực ra là **tên incident** (`incident_pipeline.py`:
`trajectory_id=incident_id`), dùng CHUNG cho hàng trăm hard-negative
candidate khác nhau của cùng 1 incident (chỉ 16 giá trị distinct trên 525
trajectory vật lý thật — định danh đúng là `source_id`). Dùng nhầm
`trajectory_id` làm dedupe theo (incident, length) thay vì (trajectory vật
lý, length) → gộp lẫn hàng trăm hard-negative khác nhau, kết quả sai
nghiêm trọng (2681→277 dòng). Phát hiện qua smoke-test bất thường (dòng
giảm quá mạnh so với kỳ vọng), sửa lại default `id_col="source_id"`, và
thêm test `test_dedupe_pooled_prefixes_does_not_collapse_different_physical_trajectories`
để bug này không tái diễn.

Test: `tests/test_nested_eval.py` — `test_dedupe_pooled_prefixes_no_duplicate_trajectory_length_pairs`
(không còn 2 dòng cùng `(source_id, prefix_len)`; số dòng distinct-length
của 1 trajectory ngắn = đúng số length THẬT SỰ khác nhau, không cố định 8),
`test_dedupe_pooled_prefixes_preserves_feature_values`,
`test_dedupe_pooled_prefixes_does_not_collapse_different_physical_trajectories`.

Áp dụng: `scripts/run_full_evaluation_v1.py` và `scripts/train_and_save_m1_final.py`
(model cuối cũng pool toàn bộ 8 bucket để train). **KHÔNG** áp dụng cho
`scripts/run_rq2_prefix_evaluation.py` (RQ2 đánh giá từng bucket riêng biệt).

## Bước 2 — Rerun B0-B3+M1 + ceiling sensitivity

Dedupe với khóa đúng (`source_id`): **2681 → 1304 dòng** — **khớp chính
xác** với số dòng của bộ dữ liệu buggy cũ. Điều này xác nhận: bug
`generate_prefixes` chỉ tạo ra các dòng **trùng lặp feature** (do 1 length
có nhiều nhãn), chứ không làm SAI giá trị feature của bất kỳ dòng nào — bug
cũ (`setdefault`) vô tình đã "dedupe" theo đúng cách nhưng gán SAI nhãn cho
người sống sót; dedupe đúng bây giờ khôi phục lại đúng tập 1304 dòng-đặc-trưng
(giá trị feature giống hệt), chỉ khác nhãn `prefix_label` hiển thị trong meta.

**Kết quả: main_table.csv, baseline_results_v2.csv, rq1_answer.md,
oof_predictions_v1.csv — TẤT CẢ giống hệt byte-for-byte** so với bản trước
khi sửa bug (đã diff xác nhận). `m1_final.joblib` cũng **sha256 giống hệt**
(`780f2e75ab75dc24e53efdb7d13bbe69d44e44dcf442624b7affd348cf862193`) — verify
tái tạo được qua 2 lần chạy độc lập.

Ceiling sensitivity (`scripts/diagnose_ceiling_effect_v1.py`) rerun đầy đủ,
kết quả cũng giống hệt: 4/11 fold ceiling thật (cả B3 và M1 đều ≥0.999),
paired comparison 11-fold vs 7-fold-loại-ceiling đều CI chứa 0, **kết luận
độ nhạy: ỔN ĐỊNH** (không đổi khi loại ceiling fold).

## Bước 3 — So sánh v1 (buggy) vs v2 (đã sửa)

| | v1 (buggy, trước sửa) | v2 (đã sửa bug + dedupe đúng) |
|---|---|---|
| Mean PR-AUC M1 | 0.7190 [0.5319, 0.8834] | **0.7190 [0.5319, 0.8834]** (giống hệt) |
| Mean PR-AUC B3 | 0.6890 [0.5254, 0.8581] | **0.6890 [0.5254, 0.8581]** (giống hệt) |
| Paired M1-B3, mean diff | -0.0065 | **-0.0065** (giống hệt) |
| Paired M1-B3, 95% CI | [-0.0883, +0.0813] | **[-0.0883, +0.0813]** (giống hệt) |
| Wilcoxon p | 0.9453 | **0.9453** (giống hệt) |
| Ceiling sensitivity (7-fold, loại ceiling) | CI [-0.1349, +0.1245] | **CI [-0.1349, +0.1245]** (giống hệt) |
| **Kết luận** | KHÔNG ĐỦ BẰNG CHỨNG | **KHÔNG ĐỦ BẰNG CHỨNG** (không đổi) |

**Kết luận không đổi — đúng theo nhánh rẽ đã thống nhất trước:** RQ1 VỮNG
trước và sau khi sửa bug `generate_prefixes`. Đây KHÔNG phải vì bug không
ảnh hưởng gì tới dữ liệu (nó ảnh hưởng thật, đã sửa gốc và có tác động rõ
rệt tới RQ2 — xem `rq2_ratio100_fix_v1.md`), mà vì **cơ chế cụ thể của bug**
(mất nhãn `prefix_label` khi trùng length) tình cờ không ảnh hưởng tới tập
FEATURE mà RQ1 dùng để train/eval, do RQ1 chỉ dùng feature cột (không dùng
`prefix_label` làm feature) và bug cũ đã vô tình "dedupe" theo đúng logic
(chỉ sai ở việc chọn nhãn). Đây là kết quả cần ghi rõ trong paper: **đã
kiểm tra độ nhạy RQ1 với chính bug tầng dữ liệu này, kết luận không đổi.**

**Điểm khác biệt duy nhất, không phải do bug:** trong bản dedupe đầu tiên
(dùng nhầm `trajectory_id`), số liệu SAI khác hẳn (277 dòng, qbridge_qubit_2022
đảo chiều thành M1 THUA B3 0.95 vs 1.0) — đây là bằng chứng gián tiếp cho
thấy nếu dedupe sai cách, kết luận CÓ THỂ đổi giả tạo; may mắn phát hiện và
sửa trước khi dùng số liệu này cho bất kỳ báo cáo nào.

## Bước 4 — Versioning artifact

Do kết quả v2 giống hệt v1 (không phải "kết luận đổi, cần bản mới"), quyết
định versioning: **KHÔNG** dùng hậu tố `_v1`/`_v2` theo nghĩa đen — vì
`baseline_results_v1.csv`/`_v2.csv` và `error_analysis_v1.md` ĐÃ dùng
`_v1`/`_v2` với nghĩa khác từ trước (Tuần 5/6: phân biệt threshold=0.5 cố
định vs nested threshold selection) — thêm 1 tầng `_v1`/`_v2` mới sẽ đụng
tên và gây nhầm lẫn nghiêm trọng hơn là giúp ích. Thay vào đó, giữ nguyên
tên file chính thức (đã là kết quả ĐÚNG sau khi sửa bug) và backup bản
trước khi sửa với hậu tố rõ nghĩa `_PRE_PREFIXFIX_backup` (nhất quán với
quy ước đã dùng cho RQ2 trong `rq2_ratio100_fix_v1.md`):

| File chính thức (v2, đã sửa bug) | Backup lịch sử (v1, buggy) |
|---|---|
| `results/tables/main_table.csv` | `main_table_PRE_PREFIXFIX_backup.csv` |
| `results/tables/baseline_results_v2.csv` | `baseline_results_v2_PRE_PREFIXFIX_backup.csv` |
| `results/reports/rq1_answer.md` | `rq1_answer_PRE_PREFIXFIX_backup.md` |
| `results/reports/rq1_ceiling_sensitivity.md` | `rq1_ceiling_sensitivity_PRE_PREFIXFIX_backup.md` |
| `results/reports/error_analysis_v1.md` | `error_analysis_v1_PRE_PREFIXFIX_backup.md` |
| `results/reports/model_card_m1.md` | `model_card_m1_PRE_PREFIXFIX_backup.md` |
| `results/models/m1_final.joblib` | `m1_final_PRE_PREFIXFIX_backup.joblib` |
| `data/processed/oof_predictions_v1.csv` | `oof_predictions_v1_PRE_PREFIXFIX_backup.csv` |

(Tất cả các cặp trên nội dung **giống hệt nhau** trừ timestamp/commit-hash
trong `model_card_m1.md` — đã diff xác nhận từng cặp.)

**Lưu ý cho `error_analysis_v1.md` (Bước 5 Tuần 6):** `qbridge_qubit_2022`
vẫn là case M1 mạnh vượt trội rõ nhất (M1=1.0 vs B3=0.6899, diff=+0.31,
cao nhất trong 11 incident) — case study interpretability trong
`alert_case_studies_v1.md` (RQ2) vẫn dùng đúng incident này, nhất quán.
`paraluni_2022` vẫn là fold TỆ NHẤT xuyên suốt B2/B3/M1 — không đổi.

`pytest tests/ -v`: **173/173 pass** (170 trước + 3 test mới cho
`dedupe_pooled_prefixes`).
