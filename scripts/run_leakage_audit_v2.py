"""Buoc 4 (Tuan 5, dot 2) - leakage audit tren B2 v2 (sau khi sua shortcut),
so sanh truc tiep voi v1. Ghi results/reports/leakage_audit_v2_comparison.md.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.models.baselines import B2BagOfActionsLogisticRegression

REPO_ROOT = Path(__file__).resolve().parents[1]
FEATURES_V1 = REPO_ROOT / "data" / "processed" / "features_v1.parquet"
FEATURES_V2 = REPO_ROOT / "data" / "processed" / "features_v2.parquet"
BASELINE_V1 = REPO_ROOT / "results" / "tables" / "baseline_results_v1.csv"
BASELINE_V2 = REPO_ROOT / "results" / "tables" / "baseline_results_v2.csv"
OUT_MD = REPO_ROOT / "results" / "reports" / "leakage_audit_v2_comparison.md"

META_COLS = ["trajectory_id", "source_id", "group_id", "kind", "chain", "label",
             "prefix_label", "prefix_len", "trajectory_len"]


def _fit_global(features_path, use_ratio_only=False):
    df = pd.read_parquet(features_path)
    feature_cols = [c for c in df.columns if c not in META_COLS]
    X = df[feature_cols]
    y = df["label"]
    model = B2BagOfActionsLogisticRegression(min_positive_incident_coverage=0 if not use_ratio_only else 2)
    model.fit(X, y, df["group_id"])
    coefs = model.model.coef_[0]
    coef_df = pd.DataFrame({"feature": model.feature_cols_, "coef": coefs}).sort_values("coef", ascending=False)
    total = X[[c for c in feature_cols if c.startswith("action_count_") and not c.endswith("_ratio")]].sum(axis=1)
    corr_len_raw = np.corrcoef(total, df["prefix_len"])[0, 1] if total.std() > 0 else float("nan")
    return df, coef_df, corr_len_raw, model


def main():
    print("=== v1 (truoc khi sua) ===")
    df1, coef1, corr1, _ = _fit_global(FEATURES_V1)
    print(coef1.to_string(index=False))
    top1 = coef1.iloc[0]
    pos1 = df1[df1["label"] == 1]
    cov1 = pos1[pos1[top1["feature"]] > 0]["group_id"].nunique()
    print(f"corr(raw action_count tong, prefix_len) = {corr1:.4f}")
    print(f"top feature: {top1['feature']} coef={top1['coef']:.4f} coverage={cov1}/{pos1['group_id'].nunique()}")

    print("\n=== v2 (sau khi sua - dung coverage filter that, min_positive_incident_coverage=2) ===")
    df2, coef2, corr2, model2 = _fit_global(FEATURES_V2, use_ratio_only=True)
    print(coef2.to_string(index=False))
    top2 = coef2.iloc[0]
    pos2 = df2[df2["label"] == 1]
    cov2 = pos2[pos2[top2["feature"]] > 0]["group_id"].nunique() if top2["feature"] in pos2.columns else None
    print(f"corr(raw action_count tong, prefix_len) = {corr2:.4f} (v2 van co ban tho, chi B2 khong dung nua)")
    print(f"top feature (B2 v2, dung ratio+coverage filter): {top2['feature']} coef={top2['coef']:.4f}")
    print(f"B2 v2 excluded_low_coverage_ (fit tren TOAN BO, chi minh hoa): {model2.excluded_low_coverage_}")

    # So sanh baseline results (neu da chay ca 2)
    compare_lines = []
    if BASELINE_V1.exists() and BASELINE_V2.exists():
        b1 = pd.read_csv(BASELINE_V1)
        b2 = pd.read_csv(BASELINE_V2)
        compare_lines.append("\n## So sánh PR-AUC/Macro-F1 trước/sau (MEAN ± STD trên 11 fold)\n")
        compare_lines.append("| Model | v1 mean PR-AUC | v1 std | v2 mean PR-AUC | v2 std | v1 mean F1 | v2 mean F1 |\n")
        compare_lines.append("|---|---|---|---|---|---|---|\n")
        for m in ["B0", "B1", "B2"]:
            r1m = b1[(b1["model"] == m) & (b1["fold"] == "MEAN")].iloc[0]
            r1s = b1[(b1["model"] == m) & (b1["fold"] == "STD")].iloc[0]
            r2m = b2[(b2["model"] == m) & (b2["fold"] == "MEAN")].iloc[0]
            r2s = b2[(b2["model"] == m) & (b2["fold"] == "STD")].iloc[0]
            compare_lines.append(
                f"| {m} | {r1m['pr_auc']:.3f} | {r1s['pr_auc']:.3f} | {r2m['pr_auc']:.3f} | {r2s['pr_auc']:.3f} "
                f"| {r1m['macro_f1']:.3f} | {r2m['macro_f1']:.3f} |\n"
            )

    md_lines = [
        "# Leakage audit v2 — so sánh trước/sau sửa shortcut độ dài (Tuần 5, đợt 2)\n",
        "\n## v1 (trước khi sửa)\n",
        f"\n```\n{coef1.to_string(index=False)}\n```\n",
        f"\n- corr(tổng action_count thô, prefix_len) = **{corr1:.4f}**\n",
        f"- Feature hệ số cao nhất: `{top1['feature']}` (coef={top1['coef']:.4f}), coverage={cov1}/{pos1['group_id'].nunique()} incident positive\n",
        "\n## v2 (sau khi sửa: action_count_*_ratio + coverage filter ≥2 incident)\n",
        f"\n```\n{coef2.to_string(index=False)}\n```\n",
        f"\n- Feature hệ số cao nhất: `{top2['feature']}` (coef={top2['coef']:.4f})\n",
        f"- Feature bị loại do coverage <2 (fit trên toàn bộ dataset, chỉ minh họa — thực tế tính per-fold): {model2.excluded_low_coverage_}\n",
    ] + compare_lines
    OUT_MD.write_text("".join(md_lines), encoding="utf-8")
    print(f"\nDa ghi {OUT_MD}")


if __name__ == "__main__":
    main()
