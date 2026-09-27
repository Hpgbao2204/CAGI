# Ablation E4 (no-temporal) + E5 (no-motif) + with-bridge-context — cập nhật 2026-08-28

**Lưu ý quan trọng**: kể từ 2026-08-28, M1 CHÍNH THỨC đã loại bỏ 9 cột `bridge_context` nội bộ (xem `src/models/baselines.py::BRIDGE_CONTEXT_COLS_EXCLUDED` và `results/reports/bridge_context_ablation_investigation.md` — xác nhận gây hại có ý nghĩa thống kê qua ablation trên 15 incident). Vì vậy **`M1_full` ở đây ĐÃ KHÔNG có bridge_context** — ablation `no-bridge-context` (loại thêm khỏi X) giờ là NO-OP (trùng tuyệt đối M1_full). Ablation thay thế: **`M1_with_bridge_context`** (THÊM LẠI 9 cột qua `include_bridge_context=True`) để tiếp tục kiểm chứng phát hiện này trong baseline mới.

Phương pháp: **giống hệt RQ1** — pool 8 prefix bucket, dedupe theo `(source_id, prefix_len)`, leave-one-incident-out (`evaluate_model_nested`), bootstrap CI mức incident, paired bootstrap trên hiệu số per-incident (ablation - M1_full) + Wilcoxon signed-rank. M1_full tái sử dụng OOF có sẵn từ `oof_predictions_v1.csv` (đã xác nhận khớp 1-1 với dataset dedupe ở đây).

## Bảng tổng hợp

| Model | Mean PR-AUC | 95% CI | Diff vs M1_full | Paired 95% CI | Wilcoxon p | Cột loại/thêm |
|---|---|---|---|---|---|---|
| M1_full | 0.6624 | [0.5234, 0.8864] | +0.0000 | [+0.0000, +0.0000] | nan | 0 |
| M1_no_temporal | 0.6314 | [0.4828, 0.8837] | -0.0530 | [-0.1535, +0.0079] | 0.2026 | 5 |
| M1_no_motif | 0.6693 | [0.5286, 0.8927] | -0.0277 | [-0.0958, +0.0208] | 0.7213 | 7 |
| M1_with_bridge_context | 0.6325 | [0.4808, 0.8724] | -0.0638 | [-0.1501, -0.0101] | 0.0357 | 0 |

## Cột liên quan từng ablation (chính xác, từ dữ liệu thật)

- **no-temporal** (5 cột LOẠI): `['time_to_first_bridge', 'inter_action_gap_mean', 'inter_action_gap_std', 'burstiness', 'active_duration_sec']`
- **no-motif** (7 cột LOẠI): `['motif_split', 'motif_merge', 'motif_peel_like_chain', 'motif_bridge_then_swap', 'motif_swap_then_split', 'motif_nested_bridge', 'motif_rapid_token_pivot']`
- **with-bridge-context** (9 cột THÊM LẠI vào M1_full): `['time_to_first_bridge', 'action_count_bridge_deposit', 'action_count_bridge_deposit_ratio', 'action_count_bridge_withdraw', 'action_count_bridge_withdraw_ratio', 'num_bridge_families', 'swap_after_bridge', 'motif_bridge_then_swap', 'motif_nested_bridge']`

## ⚠️ Lưu ý OVERLAP (bắt buộc đọc trước khi diễn giải)

`bridge_context` **KHÔNG trực giao** với 2 nhóm kia:
- Trùng với `temporal`: `['time_to_first_bridge']`
- Trùng với `motif`: `['motif_bridge_then_swap', 'motif_nested_bridge']`

3 ablation này KHÔNG phải 3 thí nghiệm độc lập cộng dồn được — diễn giải riêng từng ablation là hợp lệ; so sánh/cộng dồn giữa `with-bridge-context` và `no-temporal`/`no-motif` thì không, vì cột trùng nhau.
