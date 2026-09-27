"""Tuan 7 (RQ2) Buoc 1+2 - danh gia M1 (cung cau hinh da dung o Tuan 6,
KHONG doi hyperparameter) tren TUNG MOC PREFIX rieng (ratio_25/50/75/100,
k_2/3/5/7), leave-one-incident-out giong RQ1 (src/evaluation/nested_eval.py).

Buoc 2 (chon threshold): dung tieu chi FPR<=1% (khong phai "max 10 false
alerts/1000") - ly do: FPR la dai luong chuan hoa theo SO LUONG NEGATIVE
(khong phu thuoc ty le positive/negative cua tung fold/bucket, von dao dong
manh giua cac mien - vd k_7 bucket chi co 7-9 positive nhung so negative
khac han moi bucket) - de so sanh duoc GIUA CAC BUCKET can 1 dai luong bat
bien theo prevalence. "false_alerts_per_1000" van duoc TINH VA BAO CAO
SONG SONG (metric phai sinh, khong can chon rieng) de doc gia thay ro y
nghia van hanh.

Threshold CHI chon tren inner-train (khong dung outer test fold) - dung
evaluate_model_nested() da xay dung + test o Tuan 6.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.evaluation.nested_eval import evaluate_model_nested
from src.models.baselines import M1TypedTemporalMotifModel

REPO_ROOT = Path(__file__).resolve().parents[1]
FEATURES_PATH = REPO_ROOT / "data" / "processed" / "features_v2.parquet"
OUT_FOLD_CSV = REPO_ROOT / "results" / "tables" / "rq2_prefix_evaluation_folds.csv"
OUT_OOF_CSV = REPO_ROOT / "data" / "processed" / "rq2_oof_predictions.csv"

META_COLS = ["trajectory_id", "source_id", "group_id", "kind", "chain", "label",
             "prefix_label", "prefix_len", "trajectory_len"]
PREFIX_BUCKETS = ["ratio_25", "ratio_50", "ratio_75", "ratio_100", "k_2", "k_3", "k_5", "k_7"]
TARGET_FPR = 0.01  # Buoc 2: FPR<=1% - xem ly do trong docstring


def main():
    df = pd.read_parquet(FEATURES_PATH)
    feature_cols = [c for c in df.columns if c not in META_COLS]

    all_fold_rows = []
    all_oof_rows = []

    for bucket in PREFIX_BUCKETS:
        sub = df[df["prefix_label"] == bucket].reset_index(drop=True)
        n_pos = int((sub["label"] == 1).sum())
        n_groups_with_pos = sub[sub["label"] == 1]["group_id"].nunique()
        print(f"\n=== Prefix bucket: {bucket} (n={len(sub)}, positive={n_pos}, "
              f"{n_groups_with_pos} group co positive) ===", flush=True)

        if n_groups_with_pos < 2:
            print(f"  BO QUA: <2 group co positive trong bucket nay, khong the leave-one-group-out co y nghia.")
            continue

        X = sub[feature_cols]
        y = sub["label"]
        groups = sub["group_id"]

        result = evaluate_model_nested(M1TypedTemporalMotifModel, X, y, groups, target_fpr=TARGET_FPR)
        for r in result["fold_rows"]:
            r2 = dict(r)
            r2["prefix_bucket"] = bucket
            all_fold_rows.append(r2)
            print(f"  held_out={r['held_out_group']:32s} n_val={r['n_val_rows']:4d} "
                  f"(pos={r['n_val_positive']}) threshold={r['threshold_chosen_on_inner_train_oof']:.4f} "
                  f"pr_auc={r['pr_auc']:.4f} recall@fpr1%={r[f'recall_at_fpr_{TARGET_FPR}']:.4f} "
                  f"false_alerts/1000={r['false_alerts_per_1000']:.2f}", flush=True)

        sub_oof = sub[META_COLS].copy()
        sub_oof["oof_prob"] = result["oof_prob"].to_numpy()
        sub_oof["oof_threshold"] = result["oof_threshold"].to_numpy()
        all_oof_rows.append(sub_oof)

    fold_df = pd.DataFrame(all_fold_rows)
    OUT_FOLD_CSV.parent.mkdir(parents=True, exist_ok=True)
    fold_df.to_csv(OUT_FOLD_CSV, index=False)
    print(f"\nDa luu {OUT_FOLD_CSV} ({len(fold_df)} dong)")

    oof_df = pd.concat(all_oof_rows, ignore_index=True)
    OUT_OOF_CSV.parent.mkdir(parents=True, exist_ok=True)
    oof_df.to_csv(OUT_OOF_CSV, index=False)
    print(f"Da luu {OUT_OOF_CSV} ({len(oof_df)} dong)")

    # Tom tat mean PR-AUC / recall@FPR1% theo bucket (mean tren cac fold co du lieu)
    print("\n=== TOM TAT theo prefix bucket (mean tren fold hop le) ===")
    summary = fold_df.groupby("prefix_bucket").agg(
        mean_pr_auc=("pr_auc", "mean"),
        mean_recall_at_fpr1=(f"recall_at_fpr_{TARGET_FPR}", "mean"),
        mean_false_alerts_per_1000=("false_alerts_per_1000", "mean"),
        n_folds=("held_out_group", "count"),
    )
    print(summary.reindex(PREFIX_BUCKETS).to_string())


if __name__ == "__main__":
    main()
