"""Buoc 3 (Tuan 6) - chay B0-B3 + M1 tren features_v2.parquet voi
evaluate_model_nested (threshold chon tren inner-train, KHONG tren outer
test fold - xem src/evaluation/nested_eval.py), bootstrap CI o muc
incident, so sanh paired M1 vs B3.

Xuat:
- results/tables/baseline_results_v2.csv: per-fold B0-B3 (THAY THE ban Tuan
  5 dung threshold=0.5 co dinh - ban nay dung nested threshold selection
  dung chinh sach).
- results/tables/main_table.csv: mean + 95% CI (bootstrap muc incident) +
  per-incident breakdown cho CA 5 model (B0-B3, M1).
- results/reports/rq1_answer.md: ket luan RQ1 (M1 typed vs B3 untyped) dua
  tren CI co chong lan hay khong - KHONG dua vao so sanh mean don thuan.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

from src.evaluation.metrics import pr_auc
from src.evaluation.nested_eval import (
    bootstrap_incident_level,
    dedupe_pooled_prefixes,
    evaluate_model_nested,
    per_incident_metric,
)
from src.models.baselines import (
    B0MajorityBaseline,
    B1RuleBasedTypologyScore,
    B2BagOfActionsLogisticRegression,
    B3FlatGraphRandomForest,
    M1TypedTemporalMotifModel,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
FEATURES_PATH = REPO_ROOT / "data" / "processed" / "features_v2.parquet"
BASELINE_OUT = REPO_ROOT / "results" / "tables" / "baseline_results_v2.csv"
MAIN_TABLE_OUT = REPO_ROOT / "results" / "tables" / "main_table.csv"
RQ1_ANSWER_OUT = REPO_ROOT / "results" / "reports" / "rq1_answer.md"

META_COLS = ["trajectory_id", "source_id", "group_id", "kind", "chain", "label",
             "prefix_label", "prefix_len", "trajectory_len"]

MODEL_FACTORIES = {
    "B0": B0MajorityBaseline,
    "B1": B1RuleBasedTypologyScore,
    "B2": B2BagOfActionsLogisticRegression,
    "B3": B3FlatGraphRandomForest,
    "M1": M1TypedTemporalMotifModel,
}
FLAGGED_GROUPS = {"wault_finance_2021", "paraluni_2022"}


def main():
    df_raw = pd.read_parquet(FEATURES_PATH)
    n_before = len(df_raw)
    # RQ1 POOL toan bo 8 prefix bucket vao 1 tap train/eval moi fold (khac
    # RQ2 - danh gia TUNG bucket rieng, khong pool). Sau khi sua bug
    # generate_prefixes() (Tuan 7: 1 length co the mang nhieu nhan), giu
    # nguyen ca 4 nhan trung length se dem lap 1 diem quan sat that nhieu
    # lan mot cach gia tao khi pool - PHAI dedupe theo (trajectory_id,
    # prefix_len) TRUOC KHI pool (xem src/evaluation/nested_eval.py::
    # dedupe_pooled_prefixes, results/reports/rq1_v2_prefixfix.md).
    df = dedupe_pooled_prefixes(df_raw)
    n_after = len(df)
    print(f"Dedupe pooled prefixes (RQ1 only): {n_before} -> {n_after} dong "
          f"(loai {n_before - n_after} dong trung (trajectory_id, prefix_len))", flush=True)

    feature_cols = [c for c in df.columns if c not in META_COLS]
    X = df[feature_cols]
    y = df["label"]
    groups = df["group_id"]
    print(f"Tong {len(df)} prefix row, {len(feature_cols)} feature, {groups.nunique()} group", flush=True)

    all_fold_rows = []
    oof_by_model = {}
    for model_name, factory in MODEL_FACTORIES.items():
        print(f"\n=== {model_name}: nested leave-one-incident-out (threshold tren inner-train) ===", flush=True)
        result = evaluate_model_nested(factory, X, y, groups, target_fpr=0.01)
        oof_by_model[model_name] = result["oof_prob"]
        for r in result["fold_rows"]:
            r2 = dict(r)
            r2["model"] = model_name
            r2["flagged_data_limitation"] = r["held_out_group"] in FLAGGED_GROUPS
            all_fold_rows.append(r2)
            flag = " *** FLAGGED ***" if r2["flagged_data_limitation"] else ""
            print(f"  held_out={r['held_out_group']:32s} n_val={r['n_val_rows']:4d} "
                  f"threshold={r['threshold_chosen_on_inner_train_oof']:.4f} "
                  f"pr_auc={r['pr_auc']:.4f} macro_f1={r['macro_f1']:.4f}{flag}", flush=True)

    fold_df = pd.DataFrame(all_fold_rows)

    # --- baseline_results_v2.csv: chi B0-B3 (per-fold), THAY THE ban threshold=0.5 co dinh ---
    b0_b3 = fold_df[fold_df["model"] != "M1"].copy()
    BASELINE_OUT.parent.mkdir(parents=True, exist_ok=True)
    b0_b3.to_csv(BASELINE_OUT, index=False)
    print(f"\nDa luu {BASELINE_OUT} ({len(b0_b3)} dong, B0-B3, nested threshold)")

    # --- main_table.csv: mean + 95% CI (bootstrap muc incident) + per-incident, CA 5 model ---
    main_rows = []
    per_incident_praucs = {}
    for model_name in MODEL_FACTORIES:
        oof = oof_by_model[model_name]
        valid = oof.notna()
        y_valid = y[valid].to_numpy()
        prob_valid = oof[valid].to_numpy()
        g_valid = groups[valid].to_numpy()

        ci = bootstrap_incident_level(y_valid, prob_valid, g_valid, pr_auc, n_boot=2000)
        per_inc = per_incident_metric(y_valid, prob_valid, g_valid, pr_auc)
        per_incident_praucs[model_name] = per_inc

        main_rows.append({
            "model": model_name, "metric": "pr_auc",
            "mean_point_estimate": ci["point"], "ci_low_95": ci["ci_low"], "ci_high_95": ci["ci_high"],
            "n_incidents": len(per_inc), "n_boot_valid": ci["n_boot_valid"],
        })
        for inc, val in per_inc.items():
            main_rows.append({
                "model": model_name, "metric": f"pr_auc_incident_{inc}",
                "mean_point_estimate": val, "ci_low_95": np.nan, "ci_high_95": np.nan,
                "n_incidents": np.nan, "n_boot_valid": np.nan,
            })

    main_df = pd.DataFrame(main_rows)
    MAIN_TABLE_OUT.parent.mkdir(parents=True, exist_ok=True)
    main_df.to_csv(MAIN_TABLE_OUT, index=False)
    print(f"\nDa luu {MAIN_TABLE_OUT} ({len(main_df)} dong)")

    # --- So sanh paired M1 vs B3 (tra loi RQ1) ---
    m1_per_inc = per_incident_praucs["M1"]
    b3_per_inc = per_incident_praucs["B3"]
    common_incidents = sorted(set(m1_per_inc) & set(b3_per_inc))
    m1_scores = np.array([m1_per_inc[i] for i in common_incidents])
    b3_scores = np.array([b3_per_inc[i] for i in common_incidents])
    diffs = m1_scores - b3_scores

    valid_mask = ~(np.isnan(m1_scores) | np.isnan(b3_scores))
    m1_valid, b3_valid = m1_scores[valid_mask], b3_scores[valid_mask]
    diffs_valid = diffs[valid_mask]
    inc_valid = [common_incidents[i] for i in range(len(common_incidents)) if valid_mask[i]]

    print(f"\n=== So sanh paired M1 vs B3 tren {len(inc_valid)} incident (PR-AUC per-incident) ===")
    for inc, m1v, b3v, d in zip(inc_valid, m1_valid, b3_valid, diffs_valid):
        print(f"  {inc:32s} M1={m1v:.4f} B3={b3v:.4f} diff={d:+.4f}")

    # Bootstrap CI tren HIEU SO (paired, resample incident)
    rng = np.random.default_rng(42)
    n = len(diffs_valid)
    boot_diffs = []
    for _ in range(2000):
        idx = rng.integers(0, n, size=n)
        boot_diffs.append(diffs_valid[idx].mean())
    boot_diffs = np.array(boot_diffs)
    diff_ci_low, diff_ci_high = np.percentile(boot_diffs, [2.5, 97.5])
    mean_diff = float(diffs_valid.mean())

    try:
        wilcoxon_stat, wilcoxon_p = wilcoxon(m1_valid, b3_valid)
    except ValueError as e:  # vd tat ca hieu so = 0
        wilcoxon_stat, wilcoxon_p = float("nan"), float("nan")
        print(f"  (Wilcoxon khong tinh duoc: {e})")

    print(f"\nMean diff (M1 - B3) = {mean_diff:+.4f}, 95% bootstrap CI = [{diff_ci_low:+.4f}, {diff_ci_high:+.4f}]")
    print(f"Wilcoxon signed-rank: statistic={wilcoxon_stat}, p={wilcoxon_p}")

    ci_excludes_zero = (diff_ci_low > 0) or (diff_ci_high < 0)
    if ci_excludes_zero and mean_diff > 0:
        verdict = "H1 ĐƯỢC ỦNG HỘ: M1 (typed) vượt B3 (untyped) có ý nghĩa thống kê (95% CI của hiệu số không chứa 0, và M1 > B3)."
    elif ci_excludes_zero and mean_diff < 0:
        verdict = "H1 BỊ BÁC BỎ: B3 (untyped) vượt M1 (typed) có ý nghĩa thống kê — typed semantics KHÔNG giúp ích, thậm chí gây hại (theo PR-AUC)."
    else:
        verdict = "KHÔNG ĐỦ BẰNG CHỨNG: 95% CI của hiệu số (M1 - B3) chứa 0 — không thể kết luận M1 vượt hay thua B3 có ý nghĩa thống kê với mẫu 11 incident hiện tại."

    print(f"\n=== KẾT LUẬN RQ1 ===\n{verdict}")

    rq1_md = [
        "# RQ1: So sánh M1 (typed) vs B0-B3, đặc biệt B3 (untyped/flat)\n",
        "\n## Phương pháp\n",
        "- Leave-one-incident-out (11 fold), threshold chọn qua inner leave-one-group-out "
        "TRÊN TRAIN (không bao giờ dùng test fold) — xem src/evaluation/nested_eval.py.\n",
        "- Bootstrap CI 95% ở MỨC INCIDENT (resample 11 incident có hoàn lại, 2000 lần) — "
        "không phải mức prefix row (các prefix cùng 1 incident không độc lập).\n",
        "- So sánh paired M1 vs B3: PR-AUC riêng từng incident (11 giá trị), bootstrap CI trên "
        "hiệu số + Wilcoxon signed-rank.\n",
        "\n## Bảng PR-AUC mean (95% CI) theo model\n",
        "\n| Model | Mean PR-AUC | 95% CI |\n|---|---|---|\n",
    ]
    for model_name in MODEL_FACTORIES:
        row = main_df[(main_df["model"] == model_name) & (main_df["metric"] == "pr_auc")].iloc[0]
        rq1_md.append(f"| {model_name} | {row['mean_point_estimate']:.4f} | [{row['ci_low_95']:.4f}, {row['ci_high_95']:.4f}] |\n")

    rq1_md += [
        "\n## So sánh paired M1 vs B3 (per-incident PR-AUC)\n",
        "\n| Incident | M1 | B3 | Diff (M1-B3) |\n|---|---|---|---|\n",
    ]
    for inc, m1v, b3v, d in zip(inc_valid, m1_valid, b3_valid, diffs_valid):
        rq1_md.append(f"| {inc} | {m1v:.4f} | {b3v:.4f} | {d:+.4f} |\n")
    rq1_md += [
        f"\n**Mean diff (M1 - B3) = {mean_diff:+.4f}, 95% bootstrap CI (paired, mức incident) = "
        f"[{diff_ci_low:+.4f}, {diff_ci_high:+.4f}]**\n",
        f"\nWilcoxon signed-rank: statistic={wilcoxon_stat}, p-value={wilcoxon_p}\n",
        f"\n## KẾT LUẬN\n\n{verdict}\n",
    ]
    RQ1_ANSWER_OUT.parent.mkdir(parents=True, exist_ok=True)
    RQ1_ANSWER_OUT.write_text("".join(rq1_md), encoding="utf-8")
    print(f"\nDa luu {RQ1_ANSWER_OUT}")

    # Luu OOF predictions (dung cho error analysis Buoc 5)
    oof_export = df[META_COLS].copy()
    for model_name, oof in oof_by_model.items():
        oof_export[f"oof_prob_{model_name}"] = oof
    oof_export.to_csv(REPO_ROOT / "data" / "processed" / "oof_predictions_v1.csv", index=False)
    print(f"Da luu {REPO_ROOT / 'data' / 'processed' / 'oof_predictions_v1.csv'} (dung cho error analysis)")


if __name__ == "__main__":
    main()
