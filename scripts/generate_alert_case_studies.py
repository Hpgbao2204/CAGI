"""Tuan 7 (RQ2) Buoc 6 - 2 case study cu the: 1 true positive (uu tien
qbridge_qubit_2022, phat hien SOM) + 1 false positive. Voi moi case: prefix
length, risk probability, top-3 motif dong gop, top-5 feature contribution
(XGBoost SHAP-like, tinh tren model CUNG FOLD da dung de sinh oof_prob -
khong dung model final de tranh leak), link tx_hash.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.models.baselines import M1TypedTemporalMotifModel

REPO_ROOT = Path(__file__).resolve().parents[1]
FEATURES_PATH = REPO_ROOT / "data" / "processed" / "features_v2.parquet"
OOF_PATH = REPO_ROOT / "data" / "processed" / "rq2_oof_predictions.csv"
OUT_MD = REPO_ROOT / "results" / "reports" / "alert_case_studies_v1.md"

META_COLS = ["trajectory_id", "source_id", "group_id", "kind", "chain", "label",
             "prefix_label", "prefix_len", "trajectory_len"]

# (source_id, group_id, prefix_label, prefix_len) cho 2 case da chon (xem
# ket qua truy van thu cong tu rq2_oof_predictions.csv):
TP_CASE = {"source_id": "qbridge_qubit_2022", "group_id": "qbridge_qubit_2022",
           "prefix_label": "ratio_25", "prefix_len": 13}
# CHON LAI sau khi sua bug generate_prefixes (Tuan 7, xem
# rq2_ratio100_diagnostic.md): hn005/k_3 KHONG con la false positive that
# nua (prob=0.9510 < threshold=1.0000 tren du lieu da sua, khong con kich
# hoat alert) - chon lai tu rq2_oof_predictions.csv (label=0, oof_prob >=
# oof_threshold, THAT su la false positive), uu tien paraluni_2022 (van
# la incident yeu nhat, xem error_analysis_v1.md) de giu tinh nhat quan
# narrative voi bao cao truoc.
FP_CASE = {"source_id": "paraluni_2022__hn013", "group_id": "paraluni_2022",
           "prefix_label": "ratio_50", "prefix_len": 5}


def _rebuild_hard_negative_events(hard_negative_id: str) -> list:
    import pandas as pd

    from src.pipeline.incident_pipeline import expand_and_build_trajectory
    from src.trajectories.builder import load_trajectory_config

    hn_df = pd.read_csv(REPO_ROOT / "metadata" / "hard_negative_registry.csv")
    hn2_path = REPO_ROOT / "metadata" / "hard_negative_registry_v2_complexity.csv"
    if hn2_path.exists():
        hn_df = pd.concat([hn_df, pd.read_csv(hn2_path)], ignore_index=True)
    row = hn_df[hn_df["hard_negative_id"] == hard_negative_id].iloc[0]

    config = load_trajectory_config()
    traj, _, _ = expand_and_build_trajectory(
        row["chain"], row["seed_address"], int(row["start_block"]), row["parent_incident_id"], 0,
        config=config, do_collect=False, max_iterations=2,
    )
    return [json.loads(a.model_dump_json()) for a in traj.actions]


def fit_fold_model(df, feature_cols, held_out_group, prefix_label):
    # PHAI loc dung bucket prefix_label TRUOC (giong het
    # run_rq2_prefix_evaluation.py: moi bucket la 1 dataset RIENG, khong
    # gop chung cac prefix_label khac nhau) roi moi loai held_out_group.
    bucket_df = df[df["prefix_label"] == prefix_label]
    train = bucket_df[bucket_df["group_id"] != held_out_group]
    model = M1TypedTemporalMotifModel()
    model.fit(train[feature_cols], train["label"], train["group_id"])
    return model


def get_contribs(model, row_df):
    """XGBoost pred_contribs (SHAP-like, xap xi Shapley value that su cho
    tree ensemble) - tra ve Series feature->contribution cho DUNG 1 dong."""
    booster = model.model.get_booster()
    import xgboost as xgb
    dmat = xgb.DMatrix(row_df[model.feature_cols_])
    contribs = booster.predict(dmat, pred_contribs=True)[0]  # [..., bias] o cuoi
    feature_names = model.feature_cols_ + ["bias"]
    return pd.Series(contribs, index=feature_names)


def describe_case(df, feature_cols, case, label_expected, oof_df):
    sub = df[
        (df["group_id"] == case["group_id"]) & (df["source_id"] == case["source_id"]) &
        (df["prefix_label"] == case["prefix_label"]) & (df["prefix_len"] == case["prefix_len"])
    ]
    assert len(sub) == 1, f"khong tim thay dung 1 dong cho case {case}: {len(sub)} dong"
    row = sub.iloc[0]
    assert row["label"] == label_expected

    oof_row = oof_df[
        (oof_df["group_id"] == case["group_id"]) & (oof_df["source_id"] == case["source_id"]) &
        (oof_df["prefix_label"] == case["prefix_label"]) & (oof_df["prefix_len"] == case["prefix_len"])
    ].iloc[0]

    model = fit_fold_model(df, feature_cols, case["group_id"], case["prefix_label"])
    prob = model.predict_proba(sub[feature_cols])[0]
    assert abs(prob - oof_row["oof_prob"]) < 1e-6, "prob tinh lai KHONG khop OOF (fold sai)"

    contribs = get_contribs(model, sub)
    top_features = contribs.drop("bias").abs().sort_values(ascending=False).head(5)
    motif_contribs = contribs[[c for c in contribs.index if c.startswith("motif_")]]
    top_motifs = motif_contribs.abs().sort_values(ascending=False).head(3)

    events_path = REPO_ROOT / "data" / "processed" / f"{case['source_id']}_events.json"
    if events_path.exists():
        events = json.loads(events_path.read_text(encoding="utf-8"))
    else:
        # Hard-negative (khong phai incident goc trong incident_registry.csv)
        # khong co san file processed - rebuild truc tiep tu cache that.
        events = _rebuild_hard_negative_events(case["source_id"])
    events_sorted = sorted(events, key=lambda a: a["timestamp"])
    prefix_events = events_sorted[: case["prefix_len"]]

    return {
        "case": case, "row": row, "prob": prob, "threshold": oof_row["oof_threshold"],
        "contribs": contribs, "top_features": top_features, "top_motifs": top_motifs,
        "prefix_events": prefix_events, "model_feature_cols": model.feature_cols_,
    }


EXPLORER_BASE_URL = {"eth": "https://etherscan.io/tx/", "bsc": "https://bscscan.com/tx/", "arbitrum": "https://arbiscan.io/tx/"}


def format_case_md(title, info, note=None):
    row, prob, threshold = info["row"], info["prob"], info["threshold"]
    explorer = EXPLORER_BASE_URL.get(row["chain"], "https://etherscan.io/tx/")
    lines = [
        f"## {title}\n",
        f"\n- **Incident/candidate:** `{info['case']['source_id']}` (group `{info['case']['group_id']}`, "
        f"label thật = {int(row['label'])})\n",
        f"- **Prefix:** `{info['case']['prefix_label']}` — {info['case']['prefix_len']}/{int(row['trajectory_len'])} action\n",
        f"- **Xác suất model (fold held-out={info['case']['group_id']}):** {prob:.4f} "
        f"(threshold fold này = {threshold:.4f} → {'VƯỢT threshold, alert được kích hoạt' if prob >= threshold else 'DƯỚI threshold'})\n",
    ]
    if note:
        lines.append(f"\n> {note}\n")
    lines += [
        "\n**Top-3 motif đóng góp (|SHAP-like value|, XGBoost pred_contribs):**\n",
        "\n| Motif feature | Giá trị feature | Đóng góp |\n|---|---|---|\n",
    ]
    for feat, contrib in info["top_motifs"].items():
        val = info["row"][feat] if feat in info["row"].index else float("nan")
        lines.append(f"| {feat} | {val:.4f} | {info['contribs'][feat]:+.4f} |\n")
    lines += [
        "\n**Top-5 feature đóng góp (toàn bộ, không chỉ motif):**\n",
        "\n| Feature | Giá trị feature | Đóng góp |\n|---|---|---|\n",
    ]
    for feat, _ in info["top_features"].items():
        val = info["row"][feat] if feat in info["row"].index else float("nan")
        lines.append(f"| {feat} | {val:.4f} | {info['contribs'][feat]:+.4f} |\n")
    lines.append(f"\n(bias term = {info['contribs']['bias']:+.4f})\n")
    lines += [
        f"\n**{info['case']['prefix_len']} action trong prefix (tx_hash link):**\n\n",
    ]
    for a in info["prefix_events"]:
        lines.append(
            f"- `{a['timestamp']}` {a['event_type']} {a['src'][:10]}…→{a['dst'][:10]}… "
            f"{a['token']} (amount_norm={a['amount_norm']:.3f}) — tx [`{a['tx_hash'][:16]}…`]"
            f"({explorer}{a['tx_hash']})\n"
        )
    return "".join(lines)


def main():
    df = pd.read_parquet(FEATURES_PATH)
    feature_cols = [c for c in df.columns if c not in META_COLS]
    oof_df = pd.read_csv(OOF_PATH)

    print("=== Case 1: True positive SOM (qbridge_qubit_2022) ===")
    tp_info = describe_case(df, feature_cols, TP_CASE, label_expected=1, oof_df=oof_df)
    print(f"prob={tp_info['prob']:.4f} threshold={tp_info['threshold']:.4f}")
    print("Top motif:", tp_info["top_motifs"].to_dict())
    print("Top feature:", tp_info["top_features"].to_dict())

    print("\n=== Case 2: False positive (paraluni_2022 hard-negative) ===")
    fp_info = describe_case(df, feature_cols, FP_CASE, label_expected=0, oof_df=oof_df)
    print(f"prob={fp_info['prob']:.4f} threshold={fp_info['threshold']:.4f}")
    print("Top motif:", fp_info["top_motifs"].to_dict())
    print("Top feature:", fp_info["top_features"].to_dict())

    md = (
        "# Alert explanation — 2 case study cụ thể (Tuần 7, Bước 6)\n"
        "\nGiải thích bằng XGBoost `pred_contribs` (SHAP-like, xấp xỉ chính xác Shapley value cho "
        "tree ensemble) — tính trên MODEL CỦA ĐÚNG FOLD đã sinh ra xác suất out-of-fold tương ứng "
        "(không dùng model cuối cùng train-trên-toàn-bộ, tránh leak).\n\n"
        + format_case_md("Case 1 — True Positive, phát hiện SỚM (qbridge_qubit_2022)", tp_info)
        + "\n---\n\n"
        + format_case_md(
            f"Case 2 — False Positive ({FP_CASE['source_id']})", fp_info,
            note=(
                "**Nguyên nhân đã điều tra kỹ (Tuần 10)**: candidate này chính là "
                "hard-negative gây nhiễu nhiều nhất trong toàn bộ đánh giá per-incident của "
                "`paraluni_2022` (incident khó nhất xuyên suốt B2/B3/M1) — xem "
                "`results/reports/paraluni_2022_reinvestigation.md`. Nguyên nhân KHÔNG phải "
                "đặc điểm tổng thể (độ dài/motif/volume band của toàn incident đều bình "
                "thường so với 10 incident khác), mà là `log_amount_mean` của CHÍNH candidate "
                "này ở prefix ngắn tương đối cao (đóng góp SHAP dương lớn, xem bảng dưới), "
                "khiến model tự tin nhầm ở giai đoạn quan sát sớm — trùng khớp với `log_amount_mean` "
                "thấp bất thường ở prefix ngắn của chính positive `paraluni_2022`, làm 2 tín hiệu "
                "\"đối lập nhau\" bị model xếp hạng sai."
            ),
        )
    )
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(md, encoding="utf-8")
    print(f"\nDa luu {OUT_MD}")


if __name__ == "__main__":
    main()
