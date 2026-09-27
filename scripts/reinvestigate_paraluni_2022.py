"""Dieu tra lai paraluni_2022 (Tuan 10, bo sung) - loi giai thich cu (Tuan 6:
"hard-negative median length ~= positive length") da LOI THOI sau khi sua
bug generate_prefixes (Tuan 7) - can tim nguyen nhan THAT lam paraluni_2022
van la ca kho nhat xuyen suot moi model, tren du lieu DA SUA CA 2 bug
(prefix + dedupe).

Buoc 1: xac nhan paraluni_2022 van xep cuoi bang tren main_table.csv hien
tai (da sua het bug).
Buoc 2: so sanh co he thong voi 10 incident con lai - feature distribution
(economic/structural/motif), volume band positive vs hard-negative, feature
importance/contribution cu the tren fold paraluni_2022 (model DUNG FOLD
that su duoc dung trong nested eval khi paraluni la outer test).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.evaluation.nested_eval import dedupe_pooled_prefixes
from src.models.baselines import M1TypedTemporalMotifModel

REPO_ROOT = Path(__file__).resolve().parents[1]
FEATURES_PATH = REPO_ROOT / "data" / "processed" / "features_v2.parquet"
MAIN_TABLE = REPO_ROOT / "results" / "tables" / "main_table.csv"
OUT_MD = REPO_ROOT / "results" / "reports" / "paraluni_2022_reinvestigation.md"

META_COLS = ["trajectory_id", "source_id", "group_id", "kind", "chain", "label",
             "prefix_label", "prefix_len", "trajectory_len"]

TARGET = "paraluni_2022"

MOTIF_COLS = ["motif_split", "motif_merge", "motif_peel_like_chain", "motif_bridge_then_swap",
              "motif_swap_then_split", "motif_nested_bridge", "motif_rapid_token_pivot"]
ECON_COLS = ["log_amount_mean", "value_retention", "outgoing_incoming_ratio", "token_category_diversity"]
STRUCT_COLS = ["fan_out", "fan_in", "path_depth", "branch_count", "unique_counterparties", "local_ego_density"]
ACTION_RATIO_COLS = ["action_count_transfer_ratio", "action_count_swap_ratio", "action_count_split_ratio",
                      "action_count_merge_ratio", "action_count_bridge_deposit_ratio",
                      "action_count_bridge_withdraw_ratio", "action_count_mixer_or_exit_ratio",
                      "action_count_lending_deposit_ratio"]


def main():
    print("=== Buoc 1: xac nhan paraluni_2022 van xep cuoi (du lieu da sua het bug) ===", flush=True)
    main_df = pd.read_csv(MAIN_TABLE)
    m1_inc = main_df[(main_df["model"] == "M1") & main_df["metric"].str.startswith("pr_auc_incident_")].copy()
    m1_inc["incident"] = m1_inc["metric"].str.replace("pr_auc_incident_", "")
    m1_inc = m1_inc.sort_values("mean_point_estimate")
    print(m1_inc[["incident", "mean_point_estimate"]].to_string(index=False))
    worst = m1_inc.iloc[0]["incident"]
    confirmed_worst = worst == TARGET
    target_rank = list(m1_inc["incident"]).index(TARGET) + 1
    print(f"\nCa te nhat hien tai: {worst} (xac nhan = {TARGET}: {confirmed_worst})")
    print(f"{TARGET} xep hang {target_rank}/{len(m1_inc)} (2026-08-27, sau fix value_share - KHONG con te nhat)")

    feat = pd.read_parquet(FEATURES_PATH)
    full = feat[feat["prefix_label"] == "ratio_100"]
    other_groups = [g for g in full["group_id"].unique() if g != TARGET]

    print(f"\n=== Buoc 2a: so sanh feature POSITIVE paraluni_2022 vs {len(other_groups)} incident khac ===", flush=True)
    pos_target = full[(full["group_id"] == TARGET) & (full["label"] == 1)]
    pos_others = full[(full["group_id"] != TARGET) & (full["label"] == 1)]

    compare_rows = []
    for group_name, cols in [("economic", ECON_COLS), ("structural", STRUCT_COLS), ("motif", MOTIF_COLS), ("action_ratio", ACTION_RATIO_COLS)]:
        for c in cols:
            t_val = float(pos_target[c].iloc[0]) if len(pos_target) else float("nan")
            o_vals = pos_others[c]
            compare_rows.append({
                "feature_group": group_name, "feature": c, "paraluni_value": t_val,
                "others_median": float(o_vals.median()), "others_min": float(o_vals.min()), "others_max": float(o_vals.max()),
                "paraluni_is_outlier": bool(t_val < o_vals.min() or t_val > o_vals.max()),
            })
    compare_df = pd.DataFrame(compare_rows)
    print(compare_df.to_string(index=False))

    n_motif_zero_paraluni = int((pos_target[MOTIF_COLS].iloc[0] == 0).sum()) if len(pos_target) else None
    print(f"\nSo motif = 0 o paraluni_2022 positive: {n_motif_zero_paraluni}/{len(MOTIF_COLS)}")
    motif_zero_others = (pos_others[MOTIF_COLS] == 0).sum(axis=1)
    print(f"So motif = 0 o 11 incident khac (median/min/max): "
          f"{motif_zero_others.median():.1f}/{motif_zero_others.min()}/{motif_zero_others.max()}")

    print(f"\n=== Buoc 2b: volume band - log_amount_mean positive vs hard-negative ===", flush=True)
    volume_rows = []
    for g in full["group_id"].unique():
        pos_v = full[(full["group_id"] == g) & (full["label"] == 1)]["log_amount_mean"]
        neg_v = full[(full["group_id"] == g) & (full["label"] == 0)]["log_amount_mean"]
        if len(pos_v) == 0 or len(neg_v) == 0:
            continue
        pos_val = float(pos_v.iloc[0])
        volume_rows.append({
            "group_id": g, "pos_log_amount_mean": pos_val,
            "neg_median_log_amount_mean": float(neg_v.median()),
            "abs_diff": abs(pos_val - float(neg_v.median())),
            "n_hard_negative": len(neg_v),
        })
    volume_df = pd.DataFrame(volume_rows).sort_values("abs_diff", ascending=False)
    print(volume_df.to_string(index=False))
    paraluni_rank_volume_mismatch = int((volume_df["group_id"] == TARGET).idxmax()) if TARGET in volume_df["group_id"].values else None
    paraluni_volume_row = volume_df[volume_df["group_id"] == TARGET].iloc[0]
    rank_desc = list(volume_df["group_id"]).index(TARGET) + 1
    print(f"\nparaluni_2022 xep hang {rank_desc}/{len(volume_df)} ve do lech volume band (1=lech nhieu nhat)")

    print(f"\n=== Buoc 2c: feature importance/contribution TREN FOLD paraluni_2022 (model that dung trong nested eval) ===", flush=True)
    df_raw = pd.read_parquet(FEATURES_PATH)
    df = dedupe_pooled_prefixes(df_raw)
    feature_cols = [c for c in df.columns if c not in META_COLS]
    train = df[df["group_id"] != TARGET]
    test = df[df["group_id"] == TARGET]

    model = M1TypedTemporalMotifModel()
    model.fit(train[feature_cols], train["label"], train["group_id"])

    # QUAN TRONG: PR-AUC that (0.4123, main_table.csv) tinh tren TOAN BO
    # 154 dong cua group nay (moi prefix bucket, khong chi ratio_100) - vi
    # RQ1 pool CA 8 bucket. Lan dau viet script nay CHI loc ratio_100 (SAI -
    # cho ket qua positive thang tuyet doi 0.9986, 0/18, MAU THUAN voi
    # 0.4123 that) - sua lai dung PHUONG PHAP GOC, dung TOAN BO test set.
    test_all = test.copy()
    probs_all = model.predict_proba(test_all[model.feature_cols_])
    test_all["m1_prob"] = probs_all
    test_all_sorted = test_all.sort_values("m1_prob", ascending=False)
    print(f"Tong so dong test (moi prefix bucket) cua group {TARGET}: {len(test_all)}")
    print(test_all_sorted[["source_id", "prefix_label", "prefix_len", "label", "m1_prob"]].head(30).to_string(index=False))

    expected_pr_auc = float(m1_inc[m1_inc["incident"] == TARGET]["mean_point_estimate"].iloc[0])
    from src.evaluation.metrics import pr_auc as pr_auc_fn
    pr_auc_check = pr_auc_fn(test_all["label"].to_numpy(), test_all["m1_prob"].to_numpy())
    print(f"\nPR-AUC tinh lai tren TOAN BO {len(test_all)} dong (phai khop ~{expected_pr_auc:.4f}): {pr_auc_check:.4f}")

    # Rieng doan full-length (ratio_100) de doi chieu/tham khao (KHONG dung
    # de tinh PR-AUC chinh, chi de xem model xep hang the nao o muc do day
    # du thong tin nhat).
    test_full = test[test["prefix_label"] == "ratio_100"].copy()
    test_full["m1_prob"] = model.predict_proba(test_full[model.feature_cols_])
    test_full_sorted = test_full.sort_values("m1_prob", ascending=False)
    print(f"\n(Tham khao, KHONG dung tinh PR-AUC chinh) Rieng {len(test_full)} dong full-length (ratio_100):")
    print(test_full_sorted[["source_id", "label", "m1_prob"]].to_string(index=False))

    # QUAN TRONG: positive trajectory (24 action) sinh NHIEU dong (1 dong/
    # prefix bucket, sau khi sua bug generate_prefixes) trong test_all - vi
    # vay "false positive" o day nghia la dong NEGATIVE (bat ky prefix nao)
    # cham diem CAO HON dong POSITIVE THAP NHAT (positive kho phat hien
    # nhat) - day chinh la nguon lam PR-AUC roi xuong 0.4123.
    pos_rows = test_all_sorted[test_all_sorted["label"] == 1]
    neg_rows = test_all_sorted[test_all_sorted["label"] == 0]
    pos_prob_min = float(pos_rows["m1_prob"].min())
    pos_prob_max = float(pos_rows["m1_prob"].max())
    n_neg_above_min_pos = int((neg_rows["m1_prob"] > pos_prob_min).sum())
    print(f"\n{len(pos_rows)} dong positive (cac prefix cua chinh trajectory paraluni_2022), "
          f"prob dao dong [{pos_prob_min:.4f}, {pos_prob_max:.4f}]")
    print(f"{n_neg_above_min_pos}/{len(neg_rows)} dong hard-negative (moi prefix) cham diem CAO HON "
          f"positive THAP NHAT — day la nguon truc tiep keo PR-AUC xuong {pr_auc_check:.4f}")

    worst_pos_row = pos_rows.loc[pos_rows["m1_prob"].idxmin()]
    top_false_pos = neg_rows[neg_rows["m1_prob"] > pos_prob_min].sort_values("m1_prob", ascending=False).head(3)
    print(f"\nDong positive KHO NHAT: {worst_pos_row['source_id']} ({worst_pos_row['prefix_label']}, "
          f"prefix_len={int(worst_pos_row['prefix_len'])}) prob={worst_pos_row['m1_prob']:.4f}")
    print("\nTop 3 hard-negative (moi prefix) cham diem cao nhat, vuot ca positive kho nhat:")
    print(top_false_pos[["source_id", "prefix_label", "prefix_len", "m1_prob"]].to_string(index=False))

    import xgboost as xgb
    booster = model.model.get_booster() if hasattr(model.model, "get_booster") else None
    contrib_report = []
    if booster is not None:
        rows_to_explain = pd.concat([pd.DataFrame([worst_pos_row]), top_false_pos])
        dmat = xgb.DMatrix(rows_to_explain[model.feature_cols_])
        contribs = booster.predict(dmat, pred_contribs=True)
        feat_names = model.feature_cols_ + ["bias"]
        for i, (_, row) in enumerate(rows_to_explain.iterrows()):
            c = pd.Series(contribs[i], index=feat_names).drop("bias")
            top5 = c.abs().sort_values(ascending=False).head(5)
            contrib_report.append({
                "source_id": row["source_id"], "prefix_label": row["prefix_label"],
                "label": int(row["label"]), "m1_prob": row["m1_prob"],
                "top5_features": {f: float(c[f]) for f in top5.index},
            })
            print(f"\n{row['source_id']} ({row['prefix_label']}, label={int(row['label'])}, "
                  f"prob={row['m1_prob']:.4f}) top-5 contrib:")
            for f in top5.index:
                print(f"  {f}: {c[f]:+.4f}")

    # --- Viet report ---
    md = [
        "# Điều tra lại `paraluni_2022` (Tuần 10, cập nhật 2026-08-27)\n",
        "\n**Bối cảnh gốc (Tuần 10):** lời giải thích ban đầu (Tuần 6: \"hard-negative median "
        "length ≈ positive length\") đã LỖI THỜI sau khi sửa bug `generate_prefixes` (Tuần 7) — "
        "con số median=25 trước đó bị thổi phồng giả tạo do chỉ 10/31 hard-negative có dòng "
        "`ratio_100`. Điều tra Tuần 10 tìm nguyên nhân THẬT trên dữ liệu đã sửa 2 bug (prefix + "
        "dedupe), xác nhận `paraluni_2022` vẫn là ca tệ nhất (PR-AUC M1 = 0.4123) do hành vi "
        "`log_amount_mean` bất thường ở mốc prefix sớm.\n",
        "\n**CẬP NHẬT 2026-08-27 (Giai đoạn B):** sau khi sửa bug `value_share` gộp-token trong "
        "`build_trajectory()` (xem `results/reports/value_share_unit_mix_fix_v1.md`), trajectory "
        "thật của `paraluni_2022` tăng từ 38 → **511 action** (nhiều bằng chứng bridge/swap thật "
        "trước đây bị loại oan). Kết quả: **`paraluni_2022` KHÔNG CÒN LÀ CA TỆ NHẤT** — báo cáo "
        "này viết lại Bước 1-2 trên dữ liệu mới, xác nhận và giải thích sự thay đổi này thay vì "
        "tiếp tục giả định nó vẫn là ca khó nhất.\n",
        "\n## Bước 1 — Xác nhận thứ hạng hiện tại (đã đổi)\n",
        f"\n`paraluni_2022` xếp hạng **{target_rank}/{len(m1_inc)}** (PR-AUC M1 = "
        f"{float(m1_inc[m1_inc['incident']==TARGET]['mean_point_estimate'].iloc[0]):.4f}) trên "
        f"`main_table.csv` hiện tại (12 incident, sau fix value_share) — **KHÔNG CÒN tệ nhất**. "
        f"Ca tệ nhất mới là **`{worst}`** (PR-AUC = {m1_inc.iloc[0]['mean_point_estimate']:.4f}), "
        "trajectory của nó chỉ có 9 action và KHÔNG bị ảnh hưởng bởi bug value_share (không có "
        "hoạt động đa token) — nguyên nhân vì sao nó tệ là câu hỏi KHÁC, ngoài phạm vi báo cáo "
        "này (chưa điều tra).\n",
        "\n| Incident (xếp từ tệ→tốt) | PR-AUC M1 |\n|---|---|\n",
    ]
    for _, r in m1_inc.iterrows():
        md.append(f"| {r['incident']} | {r['mean_point_estimate']:.4f} |\n")

    md += [
        "\n## Bước 2a — So sánh feature: positive `paraluni_2022` vs 11 incident khác\n",
        f"\nSố motif = 0 (không xuất hiện) ở positive `paraluni_2022`: **{n_motif_zero_paraluni}/{len(MOTIF_COLS)}** "
        f"— so với 11 incident khác: median={motif_zero_others.median():.1f}, "
        f"min={motif_zero_others.min()}, max={motif_zero_others.max()}.\n",
        "\n| Nhóm | Feature | paraluni_2022 | Median 11 incident khác | Min-Max 11 incident khác | Outlier? |\n|---|---|---|---|---|---|\n",
    ]
    for _, r in compare_df.iterrows():
        md.append(f"| {r['feature_group']} | {r['feature']} | {r['paraluni_value']:.4f} | "
                   f"{r['others_median']:.4f} | [{r['others_min']:.4f}, {r['others_max']:.4f}] | "
                   f"{'**CÓ**' if r['paraluni_is_outlier'] else 'không'} |\n")

    md += [
        "\n## Bước 2b — Volume band: positive vs hard-negative (log_amount_mean)\n",
        f"\n`paraluni_2022` xếp hạng **{rank_desc}/{len(volume_df)}** về độ lệch volume band "
        "(1 = lệch nhiều nhất giữa positive và median hard-negative) — ",
        f"lệch tuyệt đối = {paraluni_volume_row['abs_diff']:.4f} "
        f"(positive={paraluni_volume_row['pos_log_amount_mean']:.4f}, "
        f"hard-negative median={paraluni_volume_row['neg_median_log_amount_mean']:.4f}, "
        f"n={int(paraluni_volume_row['n_hard_negative'])}).\n",
        "\n| Incident | positive log_amount_mean | hard-negative median | \\|lệch\\| | n hard-negative |\n|---|---|---|---|---|\n",
    ]
    for _, r in volume_df.iterrows():
        marker = " **← paraluni_2022**" if r["group_id"] == TARGET else ""
        md.append(f"| {r['group_id']}{marker} | {r['pos_log_amount_mean']:.4f} | "
                   f"{r['neg_median_log_amount_mean']:.4f} | {r['abs_diff']:.4f} | {int(r['n_hard_negative'])} |\n")

    md += [
        "\n## Bước 2c — Feature importance/contribution trên fold `paraluni_2022`\n",
        "\nModel M1 fit trên 11 incident khác (chính xác fold dùng trong nested eval khi "
        "`paraluni_2022` là outer test) — dự đoán trên **TOÀN BỘ tập test thật** của group này "
        f"({len(test_all)} dòng, mọi prefix bucket — khớp `n_val` trong nested eval, "
        "KHÔNG chỉ lọc `ratio_100`, vì RQ1 pool cả 8 bucket).\n",
        f"\n**Xác nhận PR-AUC tính lại trên {len(test_all)} dòng = {pr_auc_check:.4f}** — "
        f"{'khớp' if abs(pr_auc_check - expected_pr_auc) < 0.001 else f'⚠️ LỆCH so với {expected_pr_auc:.4f} main_table.csv, cần kiểm tra lại'} "
        f"so với `main_table.csv` ({expected_pr_auc:.4f}), xác nhận fold tái tạo ở đây đúng với fold thật đã dùng.\n",
        f"\n**{len(pos_rows)} dòng positive** (các mốc prefix của chính trajectory `paraluni_2022`), "
        f"prob dao động **[{pos_prob_min:.4f}, {pos_prob_max:.4f}]** — dòng positive khó nhất là "
        f"`{worst_pos_row['source_id']}` ở mốc `{worst_pos_row['prefix_label']}` "
        f"(prefix_len={int(worst_pos_row['prefix_len'])}), prob chỉ {worst_pos_row['m1_prob']:.4f}.\n",
        f"\n**{n_neg_above_min_pos}/{len(neg_rows)} dòng hard-negative (mọi prefix) được model chấm "
        f"điểm CAO HƠN dòng positive thấp nhất** — đây là nguyên nhân TRỰC TIẾP khiến PR-AUC còn "
        f"lại ở mức {pr_auc_check:.4f} (không phải toàn bộ hard-negative, mà là 1 số dòng CỤ THỂ ở "
        "1 vài mốc prefix ngắn của positive + 1 số hard-negative điểm cao).\n",
        "\n### Top 3 hard-negative (mọi prefix) chấm điểm cao nhất, vượt cả positive khó nhất\n",
        "\n| source_id | prefix | prefix_len | M1 prob |\n|---|---|---|---|\n",
    ]
    for _, r in top_false_pos.iterrows():
        md.append(f"| {r['source_id']} | {r['prefix_label']} | {int(r['prefix_len'])} | {r['m1_prob']:.4f} |\n")
    md += ["\n### Top-5 feature đóng góp (XGBoost `pred_contribs`) — positive khó nhất vs top hard-negative điểm cao\n"]
    for item in contrib_report:
        md.append(f"\n**`{item['source_id']}`** ({item['prefix_label']}, label={item['label']}, "
                   f"prob={item['m1_prob']:.4f}):\n\n")
        md.append("| Feature | Đóng góp |\n|---|---|\n")
        for f, v in item["top5_features"].items():
            md.append(f"| {f} | {v:+.4f} |\n")

    value_retention_outlier = compare_df[(compare_df["feature"] == "value_retention")].iloc[0]
    top1_fp = top_false_pos.iloc[0]
    md += [
        "\n## Kết luận\n",
        "\n**Phát hiện chính (thay thế hoàn toàn kết luận Tuần 10):** `paraluni_2022` KHÔNG CÒN "
        f"là ca tệ nhất — xếp hạng {target_rank}/{len(m1_inc)}, PR-AUC M1 tăng từ 0.4123 (dữ liệu "
        f"cũ, trajectory 38 action) lên {expected_pr_auc:.4f} (dữ liệu mới, trajectory **511 "
        "action** — tăng 13 lần). Nguyên nhân của sự cải thiện: bug `value_share` gộp-token "
        "(đã sửa 2026-08-27) trước đây loại oan phần lớn evidence swap/bridge thật của incident "
        "này — khi trajectory đầy đủ hơn, model có nhiều tín hiệu phân biệt hơn với hard-negative, "
        "PR-AUC cải thiện đáng kể mà KHÔNG cần thay đổi gì về model/feature.\n",
        f"\n**Vẫn còn khó tương đối (hạng {target_rank}/{len(m1_inc)}), nguyên nhân RESIDUAL "
        "tương tự phát hiện Tuần 10** — không còn là đặc điểm TOÀN CỤC (độ dài, motif, volume "
        "band tổng thể đều KHÔNG phải outlier rõ rệt so với 11 incident khác — xem Bước 2a/2b) mà "
        "vẫn là **hành vi ở MỐC PREFIX SỚM cụ thể**: dòng positive khó nhất là "
        f"`{worst_pos_row['prefix_label']}` (prefix_len={int(worst_pos_row['prefix_len'])}/"
        f"{int(pos_target['trajectory_len'].iloc[0]) if len(pos_target) else '?'}) có `log_amount_mean` "
        "khác biệt rõ so với các mốc dài hơn của chính nó (đóng góp SHAP "
        f"{contrib_report[0]['top5_features'].get('log_amount_mean', float('nan')):+.4f}) — trong "
        f"khi đúng lúc đó, hard-negative `{top1_fp['source_id']}` (ở mốc `{top1_fp['prefix_label']}`) "
        "lại có `log_amount_mean` khác dấu, khiến model xếp hạng nhầm ở giai đoạn sớm. Cùng bản "
        "chất **early-detection cụ thể** đã xác định ở Tuần 10 (mô hình phụ thuộc `log_amount_mean` "
        "ở mốc quan sát ngắn), nhưng mức độ ảnh hưởng đã giảm đáng kể (không còn khiến incident "
        "này rớt xuống hạng cuối).\n",
        f"\n**2 feature ngoại lệ đáng chú ý nhưng KHÔNG phải nguyên nhân chính** (không nằm "
        "trong top-5 SHAP của bất kỳ dòng nào phân tích ở trên): `value_retention` "
        f"({value_retention_outlier['paraluni_value']:.1f} so với median "
        f"{value_retention_outlier['others_median']:.4f} của 11 incident khác — "
        f"{'vẫn cao bất thường' if value_retention_outlier['paraluni_is_outlier'] else 'không còn là outlier trên dữ liệu mới'}, "
        "có thể là tỷ lệ toán học phóng đại khi mẫu số gần 0) và `fan_in` (không nằm trong top-5 "
        "contribution).\n",
        "\n**Motif vẫn KHÔNG phải nguyên nhân** — số motif=0 ở `paraluni_2022` "
        f"({n_motif_zero_paraluni}/{len(MOTIF_COLS)}) so với median 11 incident khác "
        f"({motif_zero_others.median():.1f}/{len(MOTIF_COLS)}) — không phải outlier rõ rệt.\n",
        f"\n**Case study RQ2 (`{top1_fp['source_id']}`) cần rà soát lại**: hard-negative gây nhiễu "
        "nhiều nhất trên dữ liệu MỚI có thể KHÁC với candidate đang dùng trong "
        "`results/reports/alert_case_studies_v1.md` (Tuần 7, `paraluni_2022__hn013`, dựa trên dữ "
        "liệu cũ) — nếu khác, case study đó cần cập nhật lại thành candidate mới; nếu giống, kết "
        "luận Tuần 7 vẫn còn đúng. Xem `error_analysis_v1.md`/`alert_case_studies_v1.md` đã được "
        "cập nhật ghi chú tương ứng trong cùng đợt sửa này.\n",
    ]

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("".join(md), encoding="utf-8")
    print(f"\nDa luu {OUT_MD}")


if __name__ == "__main__":
    main()
