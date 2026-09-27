#!/usr/bin/env bash
# reproduce_main.sh — Tuần 10, tái tạo TOÀN BỘ kết quả chính từ dataset đã
# freeze v1.0, HOÀN TOÀN OFFLINE (không gọi API on-chain nào).
#
# GIẢ ĐỊNH: bạn có repo NÀY + cache dữ liệu đã có trên đĩa
# (data/raw/, data/processed/*.parquet) — 2 thư mục này KHÔNG được commit
# lên git (.gitignore: *.parquet, data/raw/*) vì quá lớn. Nếu bạn `git
# clone` một bản SẠCH (không có 2 thư mục trên), script này KHÔNG chạy
# được từ đầu — bạn cần: (a) copy data/raw/ + data/processed/ từ máy đã
# chạy trước (out-of-band, vd archive/shared drive), HOẶC (b) chạy lại
# toàn bộ pipeline thu thập (scripts/run_incident_pipeline*.py,
# scripts/run_hard_negative_mining*.py — CẦN BSCTRACE_API_KEY/
# ETHERSCAN_API_KEY trong .env, ngoài phạm vi script này).
#
# Nếu features_v2.parquet đã có sẵn (thường vậy trong 1 checkout đang làm
# việc), script SKIP bước rebuild (--force-rebuild-features để ép build lại
# — vẫn OFFLINE, chỉ đọc lại data/raw/ cache, không gọi API).
#
# Output chính (đúng yêu cầu Tuần 10 Bước 2):
#   results/tables/main_table.csv              (RQ1)
#   results/tables/rq2_prefix_evaluation_folds.csv + results/figures/rq2_*.png  (RQ2)
#     (LƯU Ý: research_questions.md's bảng tóm tắt cũ ghi "prefix_curve.csv" -
#      TÊN FILE THẬT khác, đã sửa lại tham chiếu trong tài liệu, xem
#      results/reports/reproduction_v1.0.md)
#   results/tables/ablation_table.csv           (E4/E5 ablation)
#   results/tables/robustness_table.csv         (E6 robustness)
#   results/figures/calibration_curve.png       (calibration)
#   results/tables/runtime_table.csv            (RQ4 — HARDWARE-DEPENDENT,
#     xem cảnh báo cuối script)
#
# Thời gian dự kiến: ~15-25 phút (đo lúc viết script, CPU 8 core vật lý,
# xem results/reports/runtime_v1.md mục hardware) — chủ yếu do nested
# leave-one-incident-out (nhiều model fit) ở RQ1/RQ2/ablation/E6.
#
# pytest tests/ -v PHẢI chạy RIÊNG sau script này (Bước 5 Tuần 10) - không
# gộp vào đây để tách rõ "tái tạo kết quả" và "xác nhận code đúng".
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

FORCE_REBUILD_FEATURES=0
if [[ "${1:-}" == "--force-rebuild-features" ]]; then
  FORCE_REBUILD_FEATURES=1
fi

export PYTHONPATH="$REPO_ROOT"
# QUAN TRONG (loi that gap khi test Tuan 10): tren Windows, console mac
# dinh dung codepage cp1252 - script in tieng Viet co dau se crash voi
# UnicodeEncodeError ('charmap' codec can't encode...) neu KHONG dat bien
# nay. Day la loi tai lap THAT, khong phai gia dinh - da xac nhan bang
# reproduce_main.sh chay that tren moi truong sach.
export PYTHONIOENCODING=utf-8
export PYTHONUTF8=1
PY="${PYTHON:-python}"

step() { echo; echo "=========================================================="; echo ">>> $1"; echo "=========================================================="; }

START_TS=$(date +%s)

step "0/12 Kiểm tra features_v2.parquet (offline — không gọi API)"
if [[ ! -f data/processed/features_v2.parquet || "$FORCE_REBUILD_FEATURES" == "1" ]]; then
  echo "features_v2.parquet thiếu (hoặc --force-rebuild-features) — build lại từ data/raw/ cache (do_collect=False, không gọi API)."
  "$PY" scripts/build_features_v2.py
else
  echo "features_v2.parquet đã có sẵn — SKIP rebuild (dùng --force-rebuild-features nếu muốn build lại)."
fi

step "1/12 RQ1 — B0-B3 + M1, main_table.csv, rq1_answer.md"
"$PY" scripts/run_full_evaluation_v1.py

step "2/12 RQ1 — ceiling-effect sensitivity check"
"$PY" scripts/diagnose_ceiling_effect_v1.py

step "3/12 RQ1 — train M1 cuối (m1_final.joblib) + model card"
"$PY" scripts/train_and_save_m1_final.py

step "4/12 RQ1 — error analysis (Bước 5 Tuần 6)"
"$PY" scripts/run_error_analysis_v1.py

step "5/12 RQ2 — đánh giá M1 theo từng mốc prefix (ratio_25/50/75/100, k_2/3/5/7)"
"$PY" scripts/run_rq2_prefix_evaluation.py

step "6/12 RQ2 — leakage check (bắt buộc, xác nhận sạch trước khi dùng số liệu)"
"$PY" scripts/run_rq2_leakage_check.py

step "7/12 RQ2 — lead time"
"$PY" scripts/compute_lead_time.py

step "8/12 RQ2 — vẽ 3 biểu đồ (PR curve/detection-rate/lead-time)"
"$PY" scripts/plot_rq2_figures.py

step "9/12 Ablation E4 (no-temporal) + E5 (no-motif) + no-bridge-context"
"$PY" scripts/run_ablation_e4_e5.py

step "10/12 E6 — robustness (matched hard-negative vs unmatched negative, offline — cache đã có, không API mới)"
"$PY" scripts/run_e6_robustness.py

step "11/12 Calibration (Platt/isotonic, Brier/ECE)"
"$PY" scripts/run_calibration.py

step "12/12 Efficiency benchmark (RQ4) — ⚠️ KẾT QUẢ PHỤ THUỘC HARDWARE, xem cảnh báo dưới"
"$PY" scripts/run_efficiency_benchmark.py

END_TS=$(date +%s)
ELAPSED=$((END_TS - START_TS))

echo
echo "=========================================================="
echo "HOÀN TẤT reproduce_main.sh trong ${ELAPSED}s ($((ELAPSED/60)) phút)"
echo "=========================================================="
echo
echo "File output chính:"
for f in \
  results/tables/main_table.csv \
  results/tables/rq2_prefix_evaluation_folds.csv \
  results/figures/rq2_pr_curve_by_prefix.png \
  results/figures/rq2_detection_rate_vs_prefix.png \
  results/figures/rq2_lead_time_distribution.png \
  results/tables/ablation_table.csv \
  results/tables/robustness_table.csv \
  results/figures/calibration_curve.png \
  results/tables/runtime_table.csv \
  results/models/m1_final.joblib \
; do
  if [[ -f "$f" ]]; then
    echo "  [OK]     $f"
  else
    echo "  [THIẾU]  $f"
  fi
done

echo
echo "⚠️  runtime_table.csv (RQ4) đo LATENCY THẬT trên máy đang chạy — con số"
echo "    này SẼ KHÁC hardware gốc (xem results/reports/runtime_v1.md mục"
echo "    Hardware). Đây KHÔNG phải lỗi tái lập — chỉ so sánh XU HƯỚNG"
echo "    (sub-linear theo n_events, không cần GPU), KHÔNG so trực tiếp số ms."
echo
echo "Bước tiếp theo: 'python -m pytest tests/ -v' để xác nhận code đúng"
echo "(tách riêng khỏi việc tái tạo số liệu, xem Tuần 10 Bước 5)."
