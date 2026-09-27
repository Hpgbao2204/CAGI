"""Tuan 9, Buoc 5 - calibration cho M1. Hieu chinh xac suat bang Platt/
isotonic TREN INNER-TRAIN OOF (khong bao gio dung outer test - xem
evaluate_model_nested(calibration=...) trong src/evaluation/nested_eval.py).
Bao cao Brier score + ECE TRUOC va SAU hieu chinh.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.evaluation.nested_eval import dedupe_pooled_prefixes, evaluate_model_nested
from src.models.baselines import M1TypedTemporalMotifModel

REPO_ROOT = Path(__file__).resolve().parents[1]
FEATURES_PATH = REPO_ROOT / "data" / "processed" / "features_v2.parquet"
OUT_TABLE = REPO_ROOT / "results" / "tables" / "calibration_table.csv"
OUT_FIG = REPO_ROOT / "results" / "figures" / "calibration_curve.png"
OUT_MD = REPO_ROOT / "results" / "reports" / "calibration_v1.md"

META_COLS = ["trajectory_id", "source_id", "group_id", "kind", "chain", "label",
             "prefix_label", "prefix_len", "trajectory_len"]


def brier_score(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    return float(np.mean((y_prob - y_true) ** 2))


def expected_calibration_error(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
    """ECE chuan: chia [0,1] thanh n_bins, moi bin tinh |accuracy - confidence|
    trung binh co trong so theo so mau trong bin."""
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n = len(y_true)
    bin_stats = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (y_prob >= lo) & (y_prob < hi) if hi < 1.0 else (y_prob >= lo) & (y_prob <= hi)
        if mask.sum() == 0:
            bin_stats.append((lo, hi, 0, np.nan, np.nan))
            continue
        acc = y_true[mask].mean()
        conf = y_prob[mask].mean()
        ece += (mask.sum() / n) * abs(acc - conf)
        bin_stats.append((lo, hi, int(mask.sum()), float(acc), float(conf)))
    return float(ece), bin_stats


def main():
    df_raw = pd.read_parquet(FEATURES_PATH)
    df = dedupe_pooled_prefixes(df_raw)
    feature_cols = [c for c in df.columns if c not in META_COLS]
    X = df[feature_cols]
    y = df["label"]
    groups = df["group_id"]
    print(f"Dataset (dedupe pooled, giong RQ1): {len(df)} dong", flush=True)

    results = {}
    for method in [None, "isotonic", "platt"]:
        label = "raw" if method is None else method
        print(f"\n=== evaluate_model_nested calibration={method} ===", flush=True)
        result = evaluate_model_nested(M1TypedTemporalMotifModel, X, y, groups, target_fpr=0.01, calibration=method)
        prob_col = "oof_prob" if method is None else "oof_prob_calibrated"
        prob = result[prob_col]
        valid = prob.notna()
        y_valid = y[valid].to_numpy()
        p_valid = prob[valid].to_numpy()
        brier = brier_score(y_valid, p_valid)
        ece, bin_stats = expected_calibration_error(y_valid, p_valid, n_bins=10)
        print(f"  n_valid={valid.sum()}/{len(prob)}  Brier={brier:.4f}  ECE={ece:.4f}")
        results[label] = {"brier": brier, "ece": ece, "y": y_valid, "p": p_valid, "bin_stats": bin_stats,
                           "n_valid": int(valid.sum()), "n_total": len(prob)}

    table_rows = [{"method": k, "brier_score": v["brier"], "ece": v["ece"],
                    "n_valid": v["n_valid"], "n_total": v["n_total"]} for k, v in results.items()]
    table_df = pd.DataFrame(table_rows)
    OUT_TABLE.parent.mkdir(parents=True, exist_ok=True)
    table_df.to_csv(OUT_TABLE, index=False)
    print(f"\nDa luu {OUT_TABLE}")
    print(table_df.to_string(index=False))

    # --- Ve calibration curve (reliability diagram): raw vs isotonic vs platt ---
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot([0, 1], [0, 1], linestyle="--", color="gray", label="Perfect calibration")
    colors = {"raw": "#e45756", "isotonic": "#4c78a8", "platt": "#72b7b2"}
    for label, res in results.items():
        confs, accs, sizes = [], [], []
        for lo, hi, n, acc, conf in res["bin_stats"]:
            if n == 0:
                continue
            confs.append(conf)
            accs.append(acc)
            sizes.append(n)
        ax.plot(confs, accs, marker="o", color=colors.get(label, "black"),
                 label=f"{label} (Brier={res['brier']:.3f}, ECE={res['ece']:.3f})")
    ax.set_xlabel("Xác suất dự đoán trung bình trong bin (confidence)")
    ax.set_ylabel("Tỷ lệ positive thật trong bin (accuracy)")
    ax.set_title("Calibration curve — M1 (OOF, leave-one-incident-out)")
    ax.legend(loc="upper left", fontsize=9)
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    fig.tight_layout()
    OUT_FIG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_FIG, dpi=150)
    plt.close(fig)
    print(f"Da luu {OUT_FIG}")

    best_method = min(results, key=lambda k: results[k]["ece"])
    md = [
        "# Calibration — M1 (Tuần 9, Bước 5)\n",
        "\nHiệu chỉnh trên **inner-train OOF** (cùng dữ liệu dùng chọn threshold, "
        "KHÔNG BAO GIỜ dùng outer test — `evaluate_model_nested(calibration=...)`), "
        f"áp dụng lên outer test. Dataset: pool 8 bucket + dedupe (giống RQ1), {len(df)} dòng.\n",
        "\n## Brier score / ECE (10 bin) trước và sau hiệu chỉnh\n",
        "\n| Method | Brier score | ECE | n valid |\n|---|---|---|---|\n",
    ]
    for _, r in table_df.iterrows():
        md.append(f"| {r['method']} | {r['brier_score']:.4f} | {r['ece']:.4f} | {int(r['n_valid'])}/{int(r['n_total'])} |\n")
    md += [
        f"\n**Method tốt nhất theo ECE: `{best_method}`** "
        f"(ECE={results[best_method]['ece']:.4f} vs raw={results['raw']['ece']:.4f}).\n",
        "\nBiểu đồ reliability diagram: `results/figures/calibration_curve.png`.\n",
    ]
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("".join(md), encoding="utf-8")
    print(f"Da luu {OUT_MD}")


if __name__ == "__main__":
    main()
