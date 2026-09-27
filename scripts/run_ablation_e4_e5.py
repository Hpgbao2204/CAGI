"""Tuan 9 - E4 (ablation temporal), E5 (ablation motif), + tuy chon
"no-bridge-context" (Buoc 3, luu y overlap). Dung CHINH XAC pipeline RQ1
(pool 8 prefix bucket + dedupe_pooled_prefixes theo source_id, leave-one-
incident-out qua evaluate_model_nested, bootstrap CI muc incident) - quyet
dinh da chot voi nguoi dung, KHONG dung kieu per-bucket cua RQ2.

M1 "full" (baseline so sanh) TAI SU DUNG oof_prob_M1 co san trong
data/processed/oof_predictions_v1.csv (sinh tu scripts/run_full_evaluation_v1.py,
CUNG deduped dataset) - khong train lai de tiet kiem thoi gian, nhung co
XAC NHAN (assert) khop 1-1 voi df da dedupe o day truoc khi dung, tranh
gia dinh sai.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

from src.evaluation.metrics import pr_auc
from src.evaluation.nested_eval import bootstrap_incident_level, dedupe_pooled_prefixes, evaluate_model_nested, per_incident_metric
from src.models.baselines import M1TypedTemporalMotifModel

REPO_ROOT = Path(__file__).resolve().parents[1]
FEATURES_PATH = REPO_ROOT / "data" / "processed" / "features_v2.parquet"
OOF_M1_FULL_PATH = REPO_ROOT / "data" / "processed" / "oof_predictions_v1.csv"
OUT_TABLE = REPO_ROOT / "results" / "tables" / "ablation_table.csv"
OUT_MD = REPO_ROOT / "results" / "reports" / "ablation_e4_e5_v1.md"

META_COLS = ["trajectory_id", "source_id", "group_id", "kind", "chain", "label",
             "prefix_label", "prefix_len", "trajectory_len"]

# Cot THAT lay tu features_v2.parquet (48 cot, khong suy doan tu configs/features.yaml)
TEMPORAL_COLS = ["time_to_first_bridge", "inter_action_gap_mean", "inter_action_gap_std",
                  "burstiness", "active_duration_sec"]
MOTIF_COLS = ["motif_split", "motif_merge", "motif_peel_like_chain", "motif_bridge_then_swap",
              "motif_swap_then_split", "motif_nested_bridge", "motif_rapid_token_pivot"]
BRIDGE_CONTEXT_COLS = ["time_to_first_bridge", "action_count_bridge_deposit", "action_count_bridge_deposit_ratio",
                        "action_count_bridge_withdraw", "action_count_bridge_withdraw_ratio",
                        "num_bridge_families", "swap_after_bridge", "motif_bridge_then_swap", "motif_nested_bridge"]

# 2026-08-28: sau khi xac nhan bridge_context gay hai (xem
# results/reports/bridge_context_ablation_investigation.md), M1 CHINH THUC
# da loai bo 9 cot nay noi bo (src/models/baselines.py::BRIDGE_CONTEXT_COLS_EXCLUDED).
# "M1_no_bridge_context" (drop cot khoi X) gio la NO-OP (trung M1_full tuyet
# doi) vi M1 da tu loai roi, bat ke X co cot do hay khong - doi thanh
# "M1_with_bridge_context" (THEM LAI qua include_bridge_context=True) de
# tiep tuc kiem chung phat hien nay trong baseline MOI (M1 = khong bridge_context).
ABLATIONS = {
    "M1_no_temporal": (TEMPORAL_COLS, M1TypedTemporalMotifModel),
    "M1_no_motif": (MOTIF_COLS, M1TypedTemporalMotifModel),
    "M1_with_bridge_context": ([], lambda: M1TypedTemporalMotifModel(include_bridge_context=True)),
}


def paired_bootstrap(diffs: np.ndarray, n_boot: int = 2000, seed: int = 42):
    rng = np.random.default_rng(seed)
    n = len(diffs)
    boot = np.array([rng.choice(diffs, size=n, replace=True).mean() for _ in range(n_boot)])
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return float(diffs.mean()), float(lo), float(hi)


def main():
    df_raw = pd.read_parquet(FEATURES_PATH)
    df = dedupe_pooled_prefixes(df_raw)
    print(f"Dedupe pooled prefixes: {len(df_raw)} -> {len(df)} dong", flush=True)

    all_feature_cols = [c for c in df.columns if c not in META_COLS]
    y = df["label"]
    groups = df["group_id"]

    # --- Xac nhan M1-full OOF co san khop 1-1 voi df da dedupe o day (KHONG gia dinh) ---
    oof_full_df = pd.read_csv(OOF_M1_FULL_PATH)
    key_cols = ["source_id", "prefix_len"]
    merged_check = df[key_cols].merge(oof_full_df[key_cols + ["oof_prob_M1"]], on=key_cols, how="left")
    assert merged_check["oof_prob_M1"].notna().all(), "M1-full OOF khong khop 1-1 voi df da dedupe - PHAI train lai, khong tai su dung"
    assert len(merged_check) == len(df)
    df = df.merge(oof_full_df[key_cols + ["oof_prob_M1"]], on=key_cols, how="left")
    m1_full_oof = df["oof_prob_M1"]
    print("Xac nhan: M1-full OOF khop 1-1 voi dataset dedupe o day (dung lai, khong train lai).", flush=True)

    m1_full_per_inc = per_incident_metric(y.to_numpy(), m1_full_oof.to_numpy(), groups.to_numpy(), pr_auc)
    m1_full_ci = bootstrap_incident_level(y.to_numpy(), m1_full_oof.to_numpy(), groups.to_numpy(), pr_auc, n_boot=2000)

    summary_rows = [{
        "model": "M1_full", "mean_pr_auc": m1_full_ci["point"], "ci_low_95": m1_full_ci["ci_low"],
        "ci_high_95": m1_full_ci["ci_high"], "n_incidents": len(m1_full_per_inc),
        "paired_diff_vs_full": 0.0, "paired_ci_low": 0.0, "paired_ci_high": 0.0,
        "wilcoxon_p": np.nan, "n_cols_dropped": 0, "n_cols_used": len(all_feature_cols),
    }]
    per_incident_rows = [{"model": "M1_full", "incident_id": k, "pr_auc": v} for k, v in m1_full_per_inc.items()]

    for name, (drop_cols, model_factory) in ABLATIONS.items():
        drop_cols_present = [c for c in drop_cols if c in all_feature_cols]
        missing = [c for c in drop_cols if c not in all_feature_cols]
        if missing:
            print(f"CANH BAO: {name} - cot khong ton tai trong du lieu: {missing}")
        keep_cols = [c for c in all_feature_cols if c not in drop_cols_present]
        print(f"\n=== {name}: loai {len(drop_cols_present)} cot, con lai {len(keep_cols)} cot ===", flush=True)

        X = df[keep_cols]
        result = evaluate_model_nested(model_factory, X, y, groups, target_fpr=0.01)
        oof = result["oof_prob"]
        for r in result["fold_rows"]:
            print(f"  held_out={r['held_out_group']:32s} pr_auc={r['pr_auc']:.4f}", flush=True)

        valid = oof.notna()
        ci = bootstrap_incident_level(y[valid].to_numpy(), oof[valid].to_numpy(), groups[valid].to_numpy(), pr_auc, n_boot=2000)
        per_inc = per_incident_metric(y[valid].to_numpy(), oof[valid].to_numpy(), groups[valid].to_numpy(), pr_auc)
        for k, v in per_inc.items():
            per_incident_rows.append({"model": name, "incident_id": k, "pr_auc": v})

        common = sorted(set(per_inc) & set(m1_full_per_inc))
        ablation_scores = np.array([per_inc[i] for i in common])
        full_scores = np.array([m1_full_per_inc[i] for i in common])
        valid_mask = ~(np.isnan(ablation_scores) | np.isnan(full_scores))
        diffs = (ablation_scores - full_scores)[valid_mask]  # ablation - full: am = ablation TE HON
        mean_diff, ci_lo, ci_hi = paired_bootstrap(diffs)
        try:
            _, wp = wilcoxon(ablation_scores[valid_mask], full_scores[valid_mask])
        except ValueError:
            wp = float("nan")

        print(f"  Mean PR-AUC = {ci['point']:.4f} [{ci['ci_low']:.4f}, {ci['ci_high']:.4f}]")
        print(f"  Paired diff ({name} - M1_full) = {mean_diff:+.4f} [{ci_lo:+.4f}, {ci_hi:+.4f}], Wilcoxon p={wp}")

        summary_rows.append({
            "model": name, "mean_pr_auc": ci["point"], "ci_low_95": ci["ci_low"], "ci_high_95": ci["ci_high"],
            "n_incidents": len(per_inc), "paired_diff_vs_full": mean_diff,
            "paired_ci_low": ci_lo, "paired_ci_high": ci_hi, "wilcoxon_p": wp,
            "n_cols_dropped": len(drop_cols_present), "n_cols_used": len(keep_cols),
        })

    summary_df = pd.DataFrame(summary_rows)
    OUT_TABLE.parent.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(OUT_TABLE, index=False)
    print(f"\nDa luu {OUT_TABLE}")

    # --- Overlap check (Buoc 3) ---
    overlap_temporal_bridge = set(TEMPORAL_COLS) & set(BRIDGE_CONTEXT_COLS)
    overlap_motif_bridge = set(MOTIF_COLS) & set(BRIDGE_CONTEXT_COLS)

    md = [
        "# Ablation E4 (no-temporal) + E5 (no-motif) + with-bridge-context — cập nhật 2026-08-28\n",
        "\n**Lưu ý quan trọng**: kể từ 2026-08-28, M1 CHÍNH THỨC đã loại bỏ 9 cột "
        "`bridge_context` nội bộ (xem `src/models/baselines.py::BRIDGE_CONTEXT_COLS_EXCLUDED` "
        "và `results/reports/bridge_context_ablation_investigation.md` — xác nhận gây hại có ý "
        "nghĩa thống kê qua ablation trên 15 incident). Vì vậy **`M1_full` ở đây ĐÃ KHÔNG có "
        "bridge_context** — ablation `no-bridge-context` (loại thêm khỏi X) giờ là NO-OP (trùng "
        "tuyệt đối M1_full). Ablation thay thế: **`M1_with_bridge_context`** (THÊM LẠI 9 cột qua "
        "`include_bridge_context=True`) để tiếp tục kiểm chứng phát hiện này trong baseline mới.\n",
        "\nPhương pháp: **giống hệt RQ1** — pool 8 prefix bucket, dedupe theo "
        "`(source_id, prefix_len)`, leave-one-incident-out (`evaluate_model_nested`), "
        "bootstrap CI mức incident, paired bootstrap trên hiệu số per-incident "
        "(ablation - M1_full) + Wilcoxon signed-rank. M1_full tái sử dụng OOF có sẵn "
        "từ `oof_predictions_v1.csv` (đã xác nhận khớp 1-1 với dataset dedupe ở đây).\n",
        "\n## Bảng tổng hợp\n",
        "\n| Model | Mean PR-AUC | 95% CI | Diff vs M1_full | Paired 95% CI | Wilcoxon p | Cột loại/thêm |\n|---|---|---|---|---|---|---|\n",
    ]
    for _, r in summary_df.iterrows():
        md.append(f"| {r['model']} | {r['mean_pr_auc']:.4f} | [{r['ci_low_95']:.4f}, {r['ci_high_95']:.4f}] | "
                   f"{r['paired_diff_vs_full']:+.4f} | [{r['paired_ci_low']:+.4f}, {r['paired_ci_high']:+.4f}] | "
                   f"{r['wilcoxon_p']:.4f} | {int(r['n_cols_dropped'])} |\n")

    md += [
        "\n## Cột liên quan từng ablation (chính xác, từ dữ liệu thật)\n",
        f"\n- **no-temporal** ({len(TEMPORAL_COLS)} cột LOẠI): `{TEMPORAL_COLS}`\n",
        f"- **no-motif** ({len(MOTIF_COLS)} cột LOẠI): `{MOTIF_COLS}`\n",
        f"- **with-bridge-context** ({len(BRIDGE_CONTEXT_COLS)} cột THÊM LẠI vào M1_full): `{BRIDGE_CONTEXT_COLS}`\n",
        "\n## ⚠️ Lưu ý OVERLAP (bắt buộc đọc trước khi diễn giải)\n",
        f"\n`bridge_context` **KHÔNG trực giao** với 2 nhóm kia:\n",
        f"- Trùng với `temporal`: `{sorted(overlap_temporal_bridge)}`\n",
        f"- Trùng với `motif`: `{sorted(overlap_motif_bridge)}`\n",
        "\n3 ablation này KHÔNG phải 3 thí nghiệm độc lập cộng dồn được — diễn giải riêng "
        "từng ablation là hợp lệ; so sánh/cộng dồn giữa `with-bridge-context` và "
        "`no-temporal`/`no-motif` thì không, vì cột trùng nhau.\n",
    ]
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("".join(md), encoding="utf-8")
    print(f"Da luu {OUT_MD}")

    pd.DataFrame(per_incident_rows).to_csv(REPO_ROOT / "results" / "tables" / "ablation_per_incident.csv", index=False)


if __name__ == "__main__":
    main()
