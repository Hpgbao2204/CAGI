# Model Card — M1 (typed temporal + motif + XGBoost/RF)

**Ngày train:** 2026-08-27T06:43:43.655021+00:00
**Commit hash (lúc train):** `26be7dc1321653fe078f4edd0c7226b0928e2b07`
**File model:** `results\models\m1_final.joblib` (joblib, tái tạo qua `python scripts/train_and_save_m1_final.py`)

## Dữ liệu train
- Nguồn: `data\processed\features_v2.parquet` (freeze v0.9 + mining bổ sung độ phức tạp, Tuần 5 đợt 2)
- Tổng 1304 prefix row, 11 incident/group (leave-one-incident-out — model NÀY train trên TOÀN BỘ, không phải 1 fold riêng).
- Positive: 75 dòng, Negative: 1229 dòng (tỉ lệ ~1:16.4).

## Feature
- Tổng 30/48 cột dùng (đã loại 10 cột action_count thô + 8 cột coverage thấp <2 incident positive).
- Cột action_count thô bị loại: ['action_count_transfer', 'action_count_bridge_deposit', 'action_count_bridge_withdraw', 'action_count_lending_deposit', 'action_count_lending_withdraw', 'action_count_swap', 'action_count_split', 'action_count_merge', 'action_count_mixer_or_exit', 'action_count_other']
- Cột coverage thấp bị loại (tính trên TOÀN BỘ dataset — model cuối cùng, không phải per-fold): ['action_count_bridge_withdraw_ratio', 'action_count_lending_deposit_ratio', 'action_count_lending_withdraw_ratio', 'action_count_split_ratio', 'action_count_mixer_or_exit_ratio', 'action_count_other_ratio', 'motif_swap_then_split', 'motif_nested_bridge']
- Danh sách đầy đủ feature cột dùng:
```
['time_to_first_bridge', 'inter_action_gap_mean', 'inter_action_gap_std', 'burstiness', 'active_duration_sec', 'fan_out', 'fan_in', 'unique_counterparties', 'local_ego_density', 'path_depth', 'branch_count', 'log_amount_mean', 'outgoing_incoming_ratio', 'value_retention', 'token_category_diversity', 'action_count_transfer_ratio', 'action_count_bridge_deposit_ratio', 'action_count_swap_ratio', 'action_count_merge_ratio', 'num_distinct_bigrams', 'num_distinct_trigrams', 'num_bridge_families', 'swap_after_bridge', 'stablecoin_pivot', 'motif_split', 'motif_merge', 'motif_bridge_then_swap', 'motif_peel_like_chain', 'motif_rapid_token_pivot', 'prefix_ratio']
```

## Feature importance (top 15, từ model cuối cùng — chỉ mang tính minh họa, KHÔNG dùng để suy diễn causal)

```
num_distinct_bigrams           0.214328
log_amount_mean                0.214162
action_count_swap_ratio        0.143827
path_depth                     0.118118
prefix_ratio                   0.052561
inter_action_gap_mean          0.049669
value_retention                0.038247
active_duration_sec            0.029616
stablecoin_pivot               0.023938
num_distinct_trigrams          0.021410
burstiness                     0.016344
motif_rapid_token_pivot        0.014615
action_count_transfer_ratio    0.014060
branch_count                   0.014015
inter_action_gap_std           0.010673
```

## Hyperparameter (cố định trước, không tuning rộng — configs/model.yaml)
- Loại model: XGBoost
- n_estimators=200, max_depth=4, learning_rate=0.1, random_state=42
- scale_pos_weight=16.3867 (bù mất cân bằng lớp, tính từ n_neg/n_pos của toàn bộ train)
- min_positive_incident_coverage=2 (loại feature coverage thấp)

## Môi trường (để tái tạo)
- Python: 3.13.0 (Windows 11)
- scikit-learn: 1.9.0
- xgboost: 3.4.0
- pandas: 3.0.2
- numpy: 2.2.4
- scipy: 1.17.1

## Đánh giá (KHÔNG phải model này — xem kết quả cross-validation trung thực)
Model trong file này train trên TOÀN BỘ 11 incident, dùng để lưu/deploy/diễn giải feature importance — KHÔNG dùng để báo cáo hiệu năng (sẽ overfit/lạc quan giả vì không có held-out data). Hiệu năng THẬT (leave-one-incident-out, threshold chọn đúng cách) xem `results/tables/main_table.csv` và `results/reports/rq1_answer.md`.

## Cách tái tạo
```bash
python scripts/build_features_v2.py   # dung features_v2.parquet (neu chua co)
python scripts/train_and_save_m1_final.py
```
Với CÙNG commit + CÙNG features_v2.parquet, kết quả (hệ số/importance) phải GIỐNG HỆT (random_state cố định trong toàn bộ pipeline).
