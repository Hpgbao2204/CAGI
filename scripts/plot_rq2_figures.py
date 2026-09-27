"""Tuan 7 (RQ2) Buoc 5 - ve 3 bieu do, luu results/figures/:
1. PR curve theo tung moc prefix (ratio_25/50/75/100).
2. Detection-rate-vs-prefix-ratio (co per-fold points, khong chi duong trung binh).
3. Lead-time distribution (boxplot + histogram).
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_curve

REPO_ROOT = Path(__file__).resolve().parents[1]
OOF_PATH = REPO_ROOT / "data" / "processed" / "rq2_oof_predictions.csv"
FOLD_PATH = REPO_ROOT / "results" / "tables" / "rq2_prefix_evaluation_folds.csv"
LEAD_TIME_PATH = REPO_ROOT / "results" / "tables" / "lead_time_results.csv"
FIG_DIR = REPO_ROOT / "results" / "figures"

RATIO_BUCKETS = ["ratio_25", "ratio_50", "ratio_75", "ratio_100"]
COLORS = {"ratio_25": "#e45756", "ratio_50": "#f2a44c", "ratio_75": "#72b7b2", "ratio_100": "#4c78a8"}


def plot_pr_curves(oof_df: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(6, 5))
    for bucket in RATIO_BUCKETS:
        sub = oof_df[(oof_df["prefix_label"] == bucket) & oof_df["oof_prob"].notna()]
        if sub["label"].nunique() < 2:
            continue
        precision, recall, _ = precision_recall_curve(sub["label"], sub["oof_prob"])
        ax.plot(recall, precision, label=bucket, color=COLORS.get(bucket), linewidth=2)
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_title("PR curve theo mốc prefix (M1, out-of-fold, leave-one-incident-out)")
    ax.legend()
    ax.set_xlim(0, 1.02)
    ax.set_ylim(0, 1.02)
    fig.tight_layout()
    out = FIG_DIR / "rq2_pr_curve_by_prefix.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"Da luu {out}")


def plot_detection_rate_vs_prefix(fold_df: pd.DataFrame):
    ratio_order = {"ratio_25": 25, "ratio_50": 50, "ratio_75": 75, "ratio_100": 100}
    sub = fold_df[fold_df["prefix_bucket"].isin(RATIO_BUCKETS)].copy()
    sub["prefix_pct"] = sub["prefix_bucket"].map(ratio_order)
    # Detection rate xap xi bang recall_at_fpr_0.01 (ty le positive phat hien duoc trong rang buoc FPR<=1%)
    recall_col = [c for c in sub.columns if c.startswith("recall_at_fpr_")][0]

    fig, ax = plt.subplots(figsize=(6, 5))
    # per-fold points (jitter nhe theo truc x de khong chong lan)
    rng = np.random.default_rng(0)
    for bucket, pct in ratio_order.items():
        vals = sub[sub["prefix_bucket"] == bucket][recall_col].dropna()
        jitter = rng.uniform(-1.5, 1.5, size=len(vals))
        ax.scatter(np.full(len(vals), pct) + jitter, vals, alpha=0.5, color="#4c78a8", s=25, zorder=2)

    mean_by_pct = sub.groupby("prefix_pct")[recall_col].mean().reindex(ratio_order.values())
    std_by_pct = sub.groupby("prefix_pct")[recall_col].std().reindex(ratio_order.values())
    ax.plot(mean_by_pct.index, mean_by_pct.values, color="#e45756", linewidth=2.5, marker="o", zorder=3, label="Mean")
    ax.fill_between(
        mean_by_pct.index, (mean_by_pct - std_by_pct).clip(lower=0), (mean_by_pct + std_by_pct).clip(upper=1),
        alpha=0.15, color="#e45756", label="±1 std (giữa 11 fold)",
    )
    ax.set_xlabel("Prefix (% độ dài trajectory)")
    ax.set_ylabel(f"Recall tại FPR≤1% (per-fold, mỗi điểm = 1 incident held-out)")
    ax.set_title("Detection rate theo mốc prefix — M1, leave-one-incident-out")
    ax.set_xticks([25, 50, 75, 100])
    ax.set_ylim(-0.05, 1.05)
    ax.legend()
    fig.tight_layout()
    out = FIG_DIR / "rq2_detection_rate_vs_prefix.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"Da luu {out}")


def plot_lead_time_distribution():
    if not LEAD_TIME_PATH.exists():
        print(f"Bo qua: {LEAD_TIME_PATH} chua ton tai.")
        return
    df = pd.read_csv(LEAD_TIME_PATH)
    detected = df[df["detected_before_endpoint"] == True].copy()
    if detected.empty:
        print("Khong co truong hop phat hien truoc endpoint nao de ve bieu do lead time.")
        return
    detected["lead_time_hours"] = detected["lead_time_sec"] / 3600.0

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    axes[0].boxplot(detected["lead_time_hours"], vert=True, patch_artist=True,
                     boxprops=dict(facecolor="#72b7b2", alpha=0.6))
    axes[0].set_ylabel("Lead time (giờ)")
    axes[0].set_title(f"Boxplot lead time (n={len(detected)})")
    axes[0].set_xticks([1])
    axes[0].set_xticklabels(["Incident phát hiện trước endpoint"])

    axes[1].hist(detected["lead_time_hours"], bins=min(10, len(detected)), color="#4c78a8", edgecolor="white")
    axes[1].set_xlabel("Lead time (giờ)")
    axes[1].set_ylabel("Số incident")
    axes[1].set_title("Histogram lead time")
    fig.tight_layout()
    out = FIG_DIR / "rq2_lead_time_distribution.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"Da luu {out}")


def main():
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    oof_df = pd.read_csv(OOF_PATH)
    fold_df = pd.read_csv(FOLD_PATH)
    plot_pr_curves(oof_df)
    plot_detection_rate_vs_prefix(fold_df)
    plot_lead_time_distribution()


if __name__ == "__main__":
    main()
