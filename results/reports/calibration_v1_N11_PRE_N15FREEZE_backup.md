# Calibration — M1 (Tuần 9, Bước 5)

Hiệu chỉnh trên **inner-train OOF** (cùng dữ liệu dùng chọn threshold, KHÔNG BAO GIỜ dùng outer test — `evaluate_model_nested(calibration=...)`), áp dụng lên outer test. Dataset: pool 8 bucket + dedupe (giống RQ1), 1304 dòng.

## Brier score / ECE (10 bin) trước và sau hiệu chỉnh

| Method | Brier score | ECE | n valid |
|---|---|---|---|
| raw | 0.0308 | 0.0332 | 1304/1304 |
| isotonic | 0.0255 | 0.0149 | 1304/1304 |
| platt | 0.0264 | 0.0174 | 1304/1304 |

**Method tốt nhất theo ECE: `isotonic`** (ECE=0.0149 vs raw=0.0332).

Biểu đồ reliability diagram: `results/figures/calibration_curve.png`.
