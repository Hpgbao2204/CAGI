"""Giai doan A, Buoc 2 (Tuan 11) - tinh 4 nhom feature ung vien MOI tren
toan bo 11 incident + hard-negative HIEN CO (KHONG mining them), chay lai
M1 (pool + dedupe + leave-one-incident-out) voi 6 nhom cu + 4 nhom moi, so
sanh voi M1 chinh thuc (features_v2.parquet, main_table.csv da freeze),
leakage/coverage check, ablation tung nhom.

KHONG doi RQ1/RQ2 chinh thuc - day la thu nghiem RIENG (Giai doan A),
khong ghi de main_table.csv/features_v2.parquet.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

from src.evaluation.metrics import pr_auc
from src.evaluation.nested_eval import bootstrap_incident_level, dedupe_pooled_prefixes, evaluate_model_nested, per_incident_metric
from src.features.extractor import extract_all_prefixes, extract_v3_candidate_features, percentile_rank_against_reference
from src.models.baselines import M1TypedTemporalMotifModel
from src.pipeline.dataset_builder import load_rq1_trajectories

REPO_ROOT = Path(__file__).resolve().parents[1]
FEATURES_V3_PATH = REPO_ROOT / "data" / "processed" / "features_v3_candidate.parquet"
MAIN_TABLE_OFFICIAL = REPO_ROOT / "results" / "tables" / "main_table.csv"
OUT_TABLE = REPO_ROOT / "results" / "tables" / "feature_candidates_v3_ablation.csv"
OUT_MD = REPO_ROOT / "results" / "reports" / "feature_candidates_v3_evaluation.md"

META_COLS = ["trajectory_id", "source_id", "group_id", "kind", "chain", "label",
             "prefix_label", "prefix_len", "trajectory_len"]

CROSS_CHAIN_COLS = ["cross_chain_distinct_count", "cross_chain_expansion_rate"]
TOKEN_DIV_COLS = ["token_category_diversity_filtered", "token_value_entropy_filtered"]
CENTRALITY_COLS = ["seed_betweenness_centrality", "seed_closeness_centrality",
                    "mean_betweenness_centrality", "local_centrality_capped"]
V3_GROUP_COLS = {
    "cross_chain": CROSS_CHAIN_COLS,
    "token_diversity_filtered": TOKEN_DIV_COLS,
    "local_centrality": CENTRALITY_COLS,
}
PERCENTILE_BASE_FEATURES = ["log_amount_mean", "fan_out"]


class M1WithPercentileFeatures:
    """Wrapper quanh M1TypedTemporalMotifModel them 2 cot percentile-
    normalized (nhom 4). Quan trong: quan the tham chieu (hard-negative)
    CHI tinh tu X_train dua vao fit() - vi evaluate_model_nested() luon
    goi fit(X_train,...) roi predict_proba(X_test) DUNG THEO THU TU cho ca
    outer VA inner fold, wrapper nay tu dong duoc fold-scope DUNG CACH ma
    khong can sua evaluate_model_nested()."""
    name = "M1_v3_with_percentile"

    def __init__(self, **kwargs):
        self._inner = M1TypedTemporalMotifModel(**kwargs)
        self._reference: dict = {}

    def _augment(self, X: pd.DataFrame) -> pd.DataFrame:
        X = X.copy()
        for feat in PERCENTILE_BASE_FEATURES:
            ref = self._reference.get(feat, [])
            col = f"{feat}_percentile_vs_hard_negative"
            X[col] = [percentile_rank_against_reference(v, ref) for v in X[feat]]
        return X

    def fit(self, X_train: pd.DataFrame, y_train, groups_train=None):
        y_arr = pd.Series(y_train).reset_index(drop=True)
        Xr = X_train.reset_index(drop=True)
        neg_mask = (y_arr == 0)
        for feat in PERCENTILE_BASE_FEATURES:
            self._reference[feat] = Xr.loc[neg_mask, feat].tolist()
        X_aug = self._augment(X_train)
        self._inner.fit(X_aug, y_train, groups_train)
        return self

    def predict_proba(self, X: pd.DataFrame):
        return self._inner.predict_proba(self._augment(X))

    @property
    def feature_cols_(self):
        return self._inner.feature_cols_


def build_features_v3(verbose: bool = True) -> pd.DataFrame:
    print("=== Buoc 2a: build trajectory (cache local, KHONG API moi) ===", flush=True)
    items = load_rq1_trajectories(verbose=False, include_v2_complexity=True)
    n_pos = sum(1 for i in items if i.label == 1)
    print(f"Tong {len(items)} trajectory (positive={n_pos}, negative={len(items) - n_pos})", flush=True)

    rows, meta_rows = [], []
    leakage_violations = []
    for item in items:
        for spec, feats_old in extract_all_prefixes(item.trajectory, include_endpoint_context=False):
            action_count_keys = [k for k in feats_old if k.startswith("action_count_") and not k.endswith("_ratio")]
            total_counted = sum(feats_old[k] for k in action_count_keys)
            if total_counted != spec.length:
                leakage_violations.append((item.source_id, spec.label, spec.length, total_counted))

            feats_new = extract_v3_candidate_features(item.trajectory, spec.length)
            feats = dict(feats_old)
            feats.pop("prefix_len", None)
            feats.update(feats_new)
            rows.append(feats)
            meta_rows.append({
                "trajectory_id": item.trajectory.trajectory_id, "source_id": item.source_id,
                "group_id": item.group_id, "kind": item.kind, "chain": item.chain, "label": item.label,
                "prefix_label": spec.label, "prefix_len": spec.length, "trajectory_len": len(item.trajectory),
            })

    if leakage_violations:
        print(f"*** DUNG LAI: {len(leakage_violations)} vi pham invariant chong leakage (nhom CU) ***")
        for v in leakage_violations[:20]:
            print("  ", v)
        raise SystemExit(1)
    print(f"Leakage check (nhom cu, action_count == prefix_len): SACH, 0/{len(rows)} vi pham.", flush=True)

    X_df = pd.DataFrame(rows).fillna(0.0)
    meta_df = pd.DataFrame(meta_rows)
    full = pd.concat([meta_df, X_df], axis=1)

    # Leakage/sanity check rieng cho nhom moi
    n_capped = int((full["local_centrality_capped"] == 1.0).sum())
    n_nan_betweenness = int(full["seed_betweenness_centrality"].isna().sum())
    print(f"local_centrality: {n_capped} dong bi capped (graph qua lon), "
          f"{n_nan_betweenness} dong NaN (phai == so dong capped).", flush=True)
    assert n_nan_betweenness == n_capped, "NaN betweenness phai khop dung so dong capped - co bug"
    assert (full["cross_chain_distinct_count"] >= 1).all(), "moi trajectory phai co it nhat 1 chain"

    FEATURES_V3_PATH.parent.mkdir(parents=True, exist_ok=True)
    full.to_parquet(FEATURES_V3_PATH, index=False)
    print(f"Da luu {FEATURES_V3_PATH} ({len(full)} dong, {len(X_df.columns)} feature column)", flush=True)
    return full


def run_nested(model_factory, X, y, groups, label):
    result = evaluate_model_nested(model_factory, X, y, groups, target_fpr=0.01)
    oof = result["oof_prob"]
    valid = oof.notna()
    ci = bootstrap_incident_level(y[valid].to_numpy(), oof[valid].to_numpy(), groups[valid].to_numpy(), pr_auc, n_boot=2000)
    per_inc = per_incident_metric(y[valid].to_numpy(), oof[valid].to_numpy(), groups[valid].to_numpy(), pr_auc)
    print(f"  {label}: mean PR-AUC = {ci['point']:.4f} [{ci['ci_low']:.4f}, {ci['ci_high']:.4f}]", flush=True)
    return ci, per_inc


def paired_bootstrap(diffs: np.ndarray, n_boot=2000, seed=42):
    rng = np.random.default_rng(seed)
    n = len(diffs)
    boot = np.array([rng.choice(diffs, size=n, replace=True).mean() for _ in range(n_boot)])
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return float(diffs.mean()), float(lo), float(hi)


def main():
    df_raw = build_features_v3()
    df = dedupe_pooled_prefixes(df_raw)
    print(f"\nDedupe pooled prefixes: {len(df_raw)} -> {len(df)} dong", flush=True)

    feature_cols_v2 = [c for c in df.columns if c not in META_COLS and c not in
                        (CROSS_CHAIN_COLS + TOKEN_DIV_COLS + CENTRALITY_COLS)]
    feature_cols_v3_full = [c for c in df.columns if c not in META_COLS]

    y = df["label"]
    groups = df["group_id"]

    # --- Coverage check nhanh cho nhom moi (chan doan, KHONG enforce rieng -
    # M1's _filter_low_coverage_columns da tu dong loai cot coverage thap
    # tren TUNG TRAIN FOLD) ---
    print("\n=== Coverage nhanh (bao cao, tren TOAN BO dataset - chi de tham khao) ===")
    pos_rows = df[df["label"] == 1]
    for group_name, cols in V3_GROUP_COLS.items():
        for c in cols:
            n_groups_nonzero = pos_rows[pos_rows[c] > 0]["group_id"].nunique()
            print(f"  {c}: xuat hien (>0) o {n_groups_nonzero}/11 incident positive")

    print("\n=== M1_v2_official (6 nhom cu, sanity check phai khop main_table.csv) ===")
    ci_v2, per_inc_v2 = run_nested(M1TypedTemporalMotifModel, df[feature_cols_v2], y, groups, "M1_v2_official")

    if MAIN_TABLE_OFFICIAL.exists():
        official = pd.read_csv(MAIN_TABLE_OFFICIAL)
        official_m1 = official[(official["model"] == "M1") & (official["metric"] == "pr_auc")].iloc[0]
        diff_vs_official = abs(ci_v2["point"] - official_m1["mean_point_estimate"])
        print(f"  Doi chieu main_table.csv (freeze v1.0): official={official_m1['mean_point_estimate']:.4f}, "
              f"tai tao o day={ci_v2['point']:.4f}, |lech|={diff_vs_official:.6f} "
              f"({'KHOP' if diff_vs_official < 1e-6 else 'CANH BAO: LECH'})", flush=True)

    print("\n=== M1_v3_full (6 nhom cu + 3 nhom moi cot-tinh-truc-tiep, qua wrapper them percentile) ===")
    ci_v3_full, per_inc_v3_full = run_nested(M1WithPercentileFeatures, df[feature_cols_v3_full], y, groups, "M1_v3_full")

    ablation_results = {"M1_v2_official": (ci_v2, per_inc_v2), "M1_v3_full": (ci_v3_full, per_inc_v3_full)}

    print("\n=== Ablation: M1_v3_full tru tung nhom moi ===")
    for group_name, cols in V3_GROUP_COLS.items():
        cols_present = [c for c in cols if c in feature_cols_v3_full]
        keep_cols = [c for c in feature_cols_v3_full if c not in cols_present]
        ci, per_inc = run_nested(M1WithPercentileFeatures, df[keep_cols], y, groups, f"M1_v3_no_{group_name}")
        ablation_results[f"M1_v3_no_{group_name}"] = (ci, per_inc)

    print("\n=== Ablation: M1_v3_full tru percentile (bo wrapper, dung M1 thuong tren cung cot con lai) ===")
    ci_no_pct, per_inc_no_pct = run_nested(M1TypedTemporalMotifModel, df[feature_cols_v3_full], y, groups, "M1_v3_no_percentile")
    ablation_results["M1_v3_no_percentile"] = (ci_no_pct, per_inc_no_pct)

    # --- Paired comparison tung ablation vs M1_v3_full ---
    summary_rows = []
    for name, (ci, per_inc) in ablation_results.items():
        row = {"model": name, "mean_pr_auc": ci["point"], "ci_low_95": ci["ci_low"], "ci_high_95": ci["ci_high"],
               "n_incidents": len(per_inc)}
        if name not in ("M1_v3_full",):
            common = sorted(set(per_inc) & set(per_inc_v3_full))
            full_scores = np.array([per_inc_v3_full[i] for i in common])
            this_scores = np.array([per_inc[i] for i in common])
            diffs = this_scores - full_scores  # am = thieu nhom nay LAM GIAM PR-AUC -> nhom co dong gop
            mean_diff, lo, hi = paired_bootstrap(diffs)
            if np.allclose(diffs, 0.0):
                # predictions byte-identical (vd cot hang so, cay khong bao gio split) -
                # wilcoxon khong xac dinh duoc (khong co bien thien) - ghi ro NaN, khong
                # de scipy phat RuntimeWarning chia 0/0.
                wp = float("nan")
            else:
                try:
                    _, wp = wilcoxon(this_scores, full_scores)
                except ValueError:
                    wp = float("nan")
            row.update({"paired_diff_vs_v3_full": mean_diff, "paired_ci_low": lo, "paired_ci_high": hi, "wilcoxon_p": wp})
            print(f"  {name} vs M1_v3_full: diff={mean_diff:+.4f} [{lo:+.4f},{hi:+.4f}] p={wp}")
        summary_rows.append(row)

    summary_df = pd.DataFrame(summary_rows)
    OUT_TABLE.parent.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(OUT_TABLE, index=False)
    print(f"\nDa luu {OUT_TABLE}")

    # --- Bao cao ---
    md = [
        "# Feature ứng viên v3 — đánh giá Giai đoạn A (Tuần 11, Bước 2-3)\n",
        "\n**KHÔNG mining thêm dữ liệu** — dùng đúng 11 incident + hard-negative đã có "
        "(cùng tập trajectory sinh ra `features_v2.parquet`). **KHÔNG ảnh hưởng RQ1/RQ2 "
        "chính thức** (main_table.csv freeze v1.0 giữ nguyên, không ghi đè).\n",
        "\n## Sanity check: tái tạo M1 chính thức (6 nhóm cũ)\n",
    ]
    if MAIN_TABLE_OFFICIAL.exists():
        md.append(f"\nMean PR-AUC tái tạo = {ci_v2['point']:.4f} vs official = "
                   f"{official_m1['mean_point_estimate']:.4f} (|lệch|={diff_vs_official:.6f}) — "
                   f"{'✅ KHỚP' if diff_vs_official < 1e-6 else '⚠️ LỆCH, cần kiểm tra lại pipeline'}.\n")
    md += [
        "\n## Bảng tổng hợp (Mean PR-AUC, 95% CI, paired diff vs M1_v3_full)\n",
        "\n| Model | Mean PR-AUC | 95% CI | Diff vs v3_full | Paired 95% CI | Wilcoxon p |\n|---|---|---|---|---|---|\n",
    ]
    for _, r in summary_df.iterrows():
        diff_str = f"{r['paired_diff_vs_v3_full']:+.4f}" if pd.notna(r.get("paired_diff_vs_v3_full")) else "—"
        ci_str = f"[{r['paired_ci_low']:+.4f}, {r['paired_ci_high']:+.4f}]" if pd.notna(r.get("paired_ci_low")) else "—"
        wp_str = f"{r['wilcoxon_p']:.4f}" if pd.notna(r.get("wilcoxon_p")) else "—"
        md.append(f"| {r['model']} | {r['mean_pr_auc']:.4f} | [{r['ci_low_95']:.4f}, {r['ci_high_95']:.4f}] | "
                   f"{diff_str} | {ci_str} | {wp_str} |\n")

    md += [
        "\n**Cách đọc bảng ablation:** `M1_v3_no_{group}` càng TỆ HƠN (PR-AUC thấp hơn, "
        "diff âm rõ rệt, CI không chứa 0) so với `M1_v3_full` thì nhóm đó càng ĐÓNG GÓP THẬT. "
        "Nếu `M1_v3_no_{group}` gần bằng hoặc TỐT HƠN `M1_v3_full`, nhóm đó KHÔNG đóng góp "
        "(có thể chỉ thêm nhiễu).\n",
        "\n## Coverage nhanh (nhóm feature mới, toàn bộ dataset)\n\n",
    ]
    for group_name, cols in V3_GROUP_COLS.items():
        for c in cols:
            n_groups_nonzero = pos_rows[pos_rows[c] > 0]["group_id"].nunique()
            md.append(f"- `{c}`: xuất hiện (>0) ở {n_groups_nonzero}/11 incident positive\n")

    # --- Ket luan/de xuat tung nhom (Buoc 3) - TINH DONG tu ket qua that,
    # khong hardcode, de ben vung qua rerun (bai hoc Tuan 10). ---
    def _verdict(name, ablation_row_name):
        row = summary_df[summary_df["model"] == ablation_row_name].iloc[0]
        diff = row["paired_diff_vs_v3_full"]
        ci_lo, ci_hi = row["paired_ci_low"], row["paired_ci_high"]
        excludes_zero = (ci_lo > 0) or (ci_hi < 0)
        if diff == 0 and ci_lo == 0 and ci_hi == 0:
            return "DEAD — bo nhom nay cho ket qua GIONG HET (predictions byte-identical), khong dong gop gi."
        if excludes_zero and diff < 0:
            return "CO TIN HIEU THAT — bo nhom nay lam PR-AUC GIAM co y nghia thong ke (CI khong chua 0)."
        return ("KHONG CO BANG CHUNG DONG GOP — bo nhom nay PR-AUC bang hoac TOT HON "
                f"(diff={diff:+.4f}, CI {'chua' if not excludes_zero else 'khong chua'} 0).")

    md += [
        "\n## Kết luận từng nhóm (Bước 3)\n",
        f"\n- **cross_chain**: {_verdict('cross_chain', 'M1_v3_no_cross_chain')}\n",
        f"- **token_diversity_filtered**: {_verdict('token_diversity_filtered', 'M1_v3_no_token_diversity_filtered')}\n",
        f"- **local_centrality**: {_verdict('local_centrality', 'M1_v3_no_local_centrality')}\n",
        f"- **percentile_normalized**: {_verdict('percentile', 'M1_v3_no_percentile')}\n",
    ]

    all_dead_or_no_evidence = all(
        "DEAD" in _verdict(g, f"M1_v3_no_{k}") or "KHONG CO BANG CHUNG" in _verdict(g, f"M1_v3_no_{k}")
        for g, k in [("cross_chain", "cross_chain"), ("token_diversity_filtered", "token_diversity_filtered"),
                     ("local_centrality", "local_centrality")]
    ) and ("DEAD" in _verdict("percentile", "M1_v3_no_percentile") or "KHONG CO BANG CHUNG" in _verdict("percentile", "M1_v3_no_percentile"))

    md += [
        "\n## Đề xuất (Bước 3 — KHÔNG tự ý sang Giai đoạn B)\n",
    ]
    if all_dead_or_no_evidence:
        md.append(
            f"\n**CẢ 4 NHÓM đều KHÔNG có bằng chứng đóng góp thật trên dataset hiện tại "
            f"(11 incident)** — thậm chí `M1_v3_full` ({ci_v3_full['point']:.4f}) còn THẤP HƠN "
            f"`M1_v2_official` ({ci_v2['point']:.4f}), dù không có ý nghĩa thống kê (CI 2 model "
            "chồng lấn nhiều). Khuyến nghị: **KHÔNG mang bất kỳ nhóm nào trong 4 nhóm này sang "
            "Giai đoạn B as-is**. Diễn giải riêng từng nhóm:\n\n"
            "1. `cross_chain` — DEAD do giới hạn KIẾN TRÚC (mọi trajectory chỉ có 1 chain, xác "
            "nhận thực nghiệm đúng như dự đoán trong `features_v3_candidate.yaml`) — chỉ có thể "
            "sống lại nếu thay đổi cách thu thập dữ liệu (fetch chain đích của bridge event), "
            "NGOÀI PHẠM VI Giai đoạn A/B hiện tại.\n"
            "2. `token_diversity_filtered` — không đóng góp đo được trên N=11, nhưng vẫn PHÁT "
            "HIỆN đúng 1 hạn chế/bug tiềm ẩn thật của `token_category_diversity` cũ (không lọc "
            "dust) — đáng sửa độc lập với quyết định carry-forward nhóm mới, khi dataset đủ lớn "
            "để dust thực sự gây nhiễu đo được.\n"
            "3. `local_centrality` — CI paired sát ranh giới 0 (không loại trừ khả năng có tín "
            "hiệu thật bị che khuất bởi phương sai mẫu nhỏ, giống pattern đã thấy ở toàn bộ RQ1) "
            "— có thể đáng thử lại SAU KHI mở rộng dataset (Giai đoạn B), không kết luận dứt "
            "khoát \"vô dụng\" chỉ từ N=11.\n"
            "4. `percentile_normalized` — tương tự, CI sát 0 nhưng nghiêng về hướng \"bỏ đi tốt "
            "hơn\" — không đủ bằng chứng ủng hộ.\n\n"
            "**Không có nhóm nào đạt ngưỡng \"bằng chứng đóng góp thật\" (CI loại trừ 0 theo "
            "hướng có lợi)** — nhưng đây CŨNG là 1 phát hiện có giá trị: nhất quán với kết luận "
            "RQ1 (mẫu 11 incident hiện tại có phương sai lớn, khó phân biệt đóng góp feature dù "
            "typed hay flat) — gợi ý rằng vấn đề cốt lõi có thể là THIẾU DỮ LIỆU hơn là thiếu "
            "loại feature, cần cân nhắc khi quyết định trọng tâm Giai đoạn B.\n"
        )
    else:
        md.append("\n(Có ít nhất 1 nhóm cho thấy bằng chứng đóng góp — xem bảng trên để quyết định "
                   "nhóm nào mang sang Giai đoạn B.)\n")
    md.append("\n**KHÔNG tự ý chuyển sang Giai đoạn B** — báo cáo này chờ quyết định người dùng.\n")

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("".join(md), encoding="utf-8")
    print(f"Da luu {OUT_MD}")


if __name__ == "__main__":
    main()
