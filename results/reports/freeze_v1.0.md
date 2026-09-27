# Freeze v1.0 — Dataset / Feature / Experiment Config (Tuần 9, Bước 7)

**Thời điểm freeze:** 2026-08-19T14:11:17.997752+00:00
**Git commit hash:** `66c32a2d19069318b103ef0260bc96c662cef97c` (working tree sạch)

## Thành phần dataset (features_v2.parquet)

```
{
  "n_rows_total": 2681,
  "n_positive_rows": 86,
  "n_negative_rows": 2595,
  "n_groups": 11,
  "n_trajectories_distinct": 525,
  "kind_counts": {
    "hard_negative_mined": 403,
    "hard_negative_mined_v2_complexity": 106,
    "positive": 11,
    "hard_negative_control": 5
  }
}
```

## Môi trường

```
python_version: 3.13.0
platform: Windows-11-10.0.26200-SP0
sklearn_version: 1.9.0
xgboost_version: 3.4.0
pandas_version: 3.0.2
scipy_version: 1.17.1
```

## Experiment config đông cứng

```
{
  "M1_hyperparameters": {
    "n_estimators": 200,
    "max_depth": 4,
    "learning_rate": 0.1,
    "random_state": 42,
    "min_positive_incident_coverage": 2,
    "scale_pos_weight": "n_neg/n_pos (tinh tren train fold)"
  },
  "threshold_policy": "FPR<=1% (select_threshold, fallback macro-F1 neu khong dat), chon tren inner-train OOF - KHONG BAO GIO tren outer test",
  "split_methodology": "Leave-one-incident-out (LeaveOneGroupOut, group=parent_incident_id), nested (outer+inner) - src/evaluation/nested_eval.py",
  "pooling_dedupe": "RQ1/ablation/calibration/E6: pool 8 prefix bucket + dedupe_pooled_prefixes(source_id, prefix_len). RQ2: KHONG pool, danh gia tung bucket rieng.",
  "calibration_recommended": "isotonic (ECE 0.0332 -> 0.0149, xem calibration_v1.md) - TUY CHON, chua bat buoc ap dung mac dinh cho RQ1/RQ2 da bao cao",
  "ablation_columns": {
    "no_temporal": [
      "time_to_first_bridge",
      "inter_action_gap_mean",
      "inter_action_gap_std",
      "burstiness",
      "active_duration_sec"
    ],
    "no_motif": [
      "motif_split",
      "motif_merge",
      "motif_peel_like_chain",
      "motif_bridge_then_swap",
      "motif_swap_then_split",
      "motif_nested_bridge",
      "motif_rapid_token_pivot"
    ],
    "no_bridge_context": [
      "time_to_first_bridge",
      "action_count_bridge_deposit",
      "action_count_bridge_deposit_ratio",
      "action_count_bridge_withdraw",
      "action_count_bridge_withdraw_ratio",
      "num_bridge_families",
      "swap_after_bridge",
      "motif_bridge_then_swap",
      "motif_nested_bridge"
    ]
  }
}
```

## Checksum file đông cứng (sha256)

| File | sha256 | size (bytes) |
|---|---|---|
| `data/processed/features_v2.parquet` | `e98577d476c6e9fb…` | 113271 |
| `configs/features_v2_computed.json` | `69252cb071f9dac1…` | 4813 |
| `configs/features.yaml` | `eca03ae0fff4f2c5…` | 1559 |
| `configs/model.yaml` | `6e36df8c7c9b3763…` | 1082 |
| `configs/data.yaml` | `6d8079684b2bde93…` | 4064 |
| `metadata/split_manifest.json` | `0012bdf11d9c43a3…` | 27594 |
| `metadata/incident_registry.csv` | `db08b52e51d06e6d…` | 32621 |
| `metadata/hard_negative_registry.csv` | `f3c3e573fa169466…` | 72242 |
| `metadata/hard_negative_registry_v2_complexity.csv` | `e8b5a327a52867bf…` | 18262 |
| `results/models/m1_final.joblib` | `780f2e75ab75dc24…` | 250996 |
| `results/tables/main_table.csv` | `f475dda669709abe…` | 3692 |
| `results/tables/baseline_results_v2.csv` | `942c6fdea60b76b4…` | 4266 |
| `results/tables/ablation_table.csv` | `cb3a4f0c11913eb4…` | 688 |
| `results/tables/robustness_table.csv` | `1bce0548b408720d…` | 369 |
| `results/tables/calibration_table.csv` | `391f5fdbd8513095…` | 216 |
| `results/tables/runtime_table.csv` | `59fd72c7d6ac3058…` | 1069 |

## Cách xác minh không drift (Tuần 10)

```bash
python scripts/freeze_v1.0.py   # chạy lại, so sánh sha256 với bản ghi ở trên
```
Nếu bất kỳ sha256 nào đổi mà KHÔNG có commit mới giải thích rõ lý do — đây là drift ngoài ý muốn, cần điều tra trước khi tiếp tục Tuần 10 (reproducibility sprint).
