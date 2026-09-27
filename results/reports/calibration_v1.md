# Calibration — M1 (Tuần 9, Bước 5)

Hiệu chỉnh trên **inner-train OOF** (cùng dữ liệu dùng chọn threshold, KHÔNG BAO GIỜ dùng outer test — `evaluate_model_nested(calibration=...)`), áp dụng lên outer test. Dataset: pool 8 bucket + dedupe (giống RQ1), 1785 dòng.

## Brier score / ECE (10 bin) trước và sau hiệu chỉnh

| Method | Brier score | ECE | n valid |
|---|---|---|---|
| raw | 0.0410 | 0.0392 | 1785/1785 |
| isotonic | 0.0359 | 0.0198 | 1785/1785 |
| platt | 0.0332 | 0.0106 | 1785/1785 |

**Method tốt nhất theo ECE: `platt`** (ECE=0.0106 vs raw=0.0392).

Biểu đồ reliability diagram: `results/figures/calibration_curve.png`.

## ⚠️ Thay đổi kết luận so với N=11 (2026-08-19)

| Method | Brier N=11 | ECE N=11 | Brier N=15 | ECE N=15 |
|---|---|---|---|---|
| raw | 0.0308 | 0.0332 | 0.0410 | 0.0392 |
| isotonic | 0.0255 | 0.0149 | 0.0359 | 0.0198 |
| platt | 0.0264 | 0.0174 | 0.0332 | **0.0106** |

**Method tốt nhất đã đổi: `isotonic` (N=11) → `platt` (N=15).** Cả 2
phương pháp vẫn cải thiện đáng kể so với raw ở cả 2 lần đo (raw luôn tệ
nhất), nhưng thứ hạng giữa isotonic/platt đảo ngược. Khả năng do isotonic
regression (non-parametric, nhiều bậc tự do hơn) dễ overfit hơn khi phân
phối OOF probability của M1 mới (không bridge_context, N=15) khác — số
incident/fold tăng khiến pooled prefix row tăng (1304→1785) nhưng đồng
thời phân phối theo từng inner-fold train có thể ít đơn điệu hơn cho
isotonic khai thác. **Khuyến nghị**: nếu paper cần chọn 1 phương pháp
calibration chính thức, dùng số liệu N=15 này (`platt`) thay vì N=11
(`isotonic`) — đây là bản mới nhất, khớp đúng M1 hiện tại. Bản N=11 gốc
giữ nguyên tại `results/reports/calibration_v1_N11_PRE_N15FREEZE_backup.md`,
biểu đồ N=11 tại `results/figures/calibration_curve_N11_PRE_N15FREEZE_backup.png`.
