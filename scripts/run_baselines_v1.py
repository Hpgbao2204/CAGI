"""Buoc 4 (Tuan 5) - chay B0/B1/B2 tren features_v1.parquet, split
leave-one-incident-out (11 fold, group_id doc tu metadata/split_manifest.json
qua cot group_id da luu san trong parquet). Luu KET QUA TUNG FOLD (khong chi
mean) vao results/tables/baseline_results_v1.csv.

B3/M1 CHUA chay o Tuan 5 (danh cho Tuan 6) - theo dung yeu cau.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import LeaveOneGroupOut

from src.evaluation.metrics import macro_f1, pr_auc
from src.models.baselines import (
    B0MajorityBaseline,
    B1RuleBasedTypologyScore,
    B2BagOfActionsLogisticRegression,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
FEATURES_PATH = REPO_ROOT / "data" / "processed" / "features_v1.parquet"
OUT_PATH = REPO_ROOT / "results" / "tables" / "baseline_results_v1.csv"

# 2 incident co gioi han nguon du lieu da biet (gan tran phan trang BSCTrace,
# xem data/dataset_card.md muc Gioi han) - can chu y rieng khi fold cua chung
# xuat hien trong ket qua.
FLAGGED_GROUPS = {"wault_finance_2021", "paraluni_2022"}

META_COLS = ["trajectory_id", "source_id", "group_id", "kind", "chain", "label",
             "prefix_label", "prefix_len", "trajectory_len"]


def main():
    df = pd.read_parquet(FEATURES_PATH)
    feature_cols = [c for c in df.columns if c not in META_COLS]
    X_all = df[feature_cols]
    y_all = df["label"]
    groups_all = df["group_id"]

    print(f"Tong {len(df)} prefix row, {len(feature_cols)} feature, {groups_all.nunique()} group "
          f"(leave-one-incident-out -> {groups_all.nunique()} fold)", flush=True)

    models_factory = {
        "B0": B0MajorityBaseline,
        "B1": B1RuleBasedTypologyScore,
        "B2": B2BagOfActionsLogisticRegression,
    }

    logo = LeaveOneGroupOut()
    fold_rows = []

    for model_name, factory in models_factory.items():
        print(f"\n=== {model_name} ===", flush=True)
        for fold_idx, (train_idx, val_idx) in enumerate(logo.split(X_all, y_all, groups=groups_all)):
            held_out_group = groups_all.iloc[val_idx].iloc[0]
            train_groups = set(groups_all.iloc[train_idx])
            val_groups = set(groups_all.iloc[val_idx])
            assert train_groups.isdisjoint(val_groups), "leave-one-group-out leakage: group xuat hien ca train va val"
            assert val_groups == {held_out_group}

            model = factory()
            model.fit(X_all.iloc[train_idx], y_all.iloc[train_idx], groups_all.iloc[train_idx])
            y_val = y_all.iloc[val_idx]
            prob_val = model.predict_proba(X_all.iloc[val_idx])

            n_pos_val = int((y_val == 1).sum())
            n_neg_val = int((y_val == 0).sum())
            fold_pr_auc = pr_auc(y_val, prob_val)
            fold_macro_f1 = macro_f1(y_val, prob_val, threshold=0.5)

            flag = "*** FLAGGED (gioi han pagination BSCTrace) ***" if held_out_group in FLAGGED_GROUPS else ""
            print(f"  fold {fold_idx:2d} held_out={held_out_group:32s} n_val={len(val_idx):4d} "
                  f"(pos={n_pos_val:3d}, neg={n_neg_val:4d}) pr_auc={fold_pr_auc:.4f} "
                  f"macro_f1={fold_macro_f1:.4f} {flag}", flush=True)

            fold_rows.append({
                "model": model_name,
                "fold": fold_idx,
                "held_out_group": held_out_group,
                "n_val_rows": len(val_idx),
                "n_val_positive": n_pos_val,
                "n_val_negative": n_neg_val,
                "pr_auc": fold_pr_auc,
                "macro_f1": fold_macro_f1,
                "flagged_data_limitation": held_out_group in FLAGGED_GROUPS,
            })

        # Mean +- std tren cac fold co PR-AUC hop le (khong NaN)
        model_rows = [r for r in fold_rows if r["model"] == model_name]
        valid_pr = [r["pr_auc"] for r in model_rows if not np.isnan(r["pr_auc"])]
        valid_f1 = [r["macro_f1"] for r in model_rows if not np.isnan(r["macro_f1"])]
        print(f"  --- {model_name} MEAN pr_auc={np.mean(valid_pr):.4f} (std={np.std(valid_pr):.4f}) "
              f"macro_f1={np.mean(valid_f1):.4f} (std={np.std(valid_f1):.4f}) "
              f"tren {len(valid_pr)}/{len(model_rows)} fold hop le ---", flush=True)
        fold_rows.append({
            "model": model_name, "fold": "MEAN", "held_out_group": "ALL_FOLDS",
            "n_val_rows": len(df), "n_val_positive": int((y_all == 1).sum()), "n_val_negative": int((y_all == 0).sum()),
            "pr_auc": float(np.mean(valid_pr)), "macro_f1": float(np.mean(valid_f1)),
            "flagged_data_limitation": False,
        })
        fold_rows.append({
            "model": model_name, "fold": "STD", "held_out_group": "ALL_FOLDS",
            "n_val_rows": len(df), "n_val_positive": int((y_all == 1).sum()), "n_val_negative": int((y_all == 0).sum()),
            "pr_auc": float(np.std(valid_pr)), "macro_f1": float(np.std(valid_f1)),
            "flagged_data_limitation": False,
        })

    result_df = pd.DataFrame(fold_rows)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    result_df.to_csv(OUT_PATH, index=False)
    print(f"\nDa luu {OUT_PATH} ({len(result_df)} dong, gom per-fold + MEAN/STD)")

    # In rieng cac fold FLAGGED de de doi chieu
    flagged = result_df[result_df["flagged_data_limitation"] == True]
    if len(flagged):
        print("\n=== Cac fold FLAGGED (wault_finance_2021 / paraluni_2022) ===")
        print(flagged[["model", "held_out_group", "n_val_rows", "n_val_positive", "n_val_negative", "pr_auc", "macro_f1"]].to_string(index=False))


if __name__ == "__main__":
    main()
