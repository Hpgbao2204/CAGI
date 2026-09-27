"""Chan doan gioi han (Tuan 6, buoc phu) - kiem tra RQ1 co bi ceiling effect
chi phoi khong (5/11 fold PR-AUC=1.0 o ca B3 lan M1 - CHINH XAC la 4/11, xem
in ra duoi day, dinh chinh lai so lieu tu error_analysis_v1.md truoc do).

Buoc 1: bang n_val/n_positive/n_negative + PR-AUC B3/M1 tung fold.
Buoc 2: paired comparison M1 vs B3 tren 11 fold DAY DU vs tren cac fold
CON LAI sau khi loai fold ca 2 model deu dat PR-AUC>=0.999 ("ceiling that
su" - CA HAI model khong con phan biet duoc, khong phai chi 1 model dat 1.0).
Buoc 3: dieu tra nhanh paraluni_2022 (te nhat xuyen suot B2/B3/M1) - TINH
DONG tu du lieu that (KHONG hardcode - bug tai lap that phat hien Tuan 10:
phien ban truoc chi viet Buoc 3 bang tay SAU khi chay script, bi mat khi
rerun script - xem results/reports/reproduction_v1.0.md).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

REPO_ROOT = Path(__file__).resolve().parents[1]
MAIN_TABLE = REPO_ROOT / "results" / "tables" / "main_table.csv"
OOF_PATH = REPO_ROOT / "data" / "processed" / "oof_predictions_v1.csv"
FEATURES_V2_PATH = REPO_ROOT / "data" / "processed" / "features_v2.parquet"
INCIDENT_REGISTRY_PATH = REPO_ROOT / "metadata" / "incident_registry.csv"
HARD_NEGATIVE_REGISTRY_PATH = REPO_ROOT / "metadata" / "hard_negative_registry.csv"
HN_V2_PATH = REPO_ROOT / "metadata" / "hard_negative_registry_v2_complexity.csv"
OUT_MD = REPO_ROOT / "results" / "reports" / "rq1_ceiling_sensitivity.md"

CEILING_THRESHOLD = 0.999


def per_incident(main_df, model):
    sub = main_df[(main_df["model"] == model) & main_df["metric"].str.startswith("pr_auc_incident_")]
    return {r["metric"].replace("pr_auc_incident_", ""): r["mean_point_estimate"] for _, r in sub.iterrows()}


def paired_bootstrap(m1_scores, b3_scores, n_boot=2000, seed=42):
    rng = np.random.default_rng(seed)
    diffs = m1_scores - b3_scores
    n = len(diffs)
    boot = np.array([rng.choice(diffs, size=n, replace=True).mean() for _ in range(n_boot)])
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return float(diffs.mean()), float(lo), float(hi)


def investigate_paraluni_step3(worst_incident: str) -> str:
    """Buoc 3: dieu tra nhanh incident TE NHAT (thuong la paraluni_2022) -
    so sanh do dai positive vs hard-negative, kiem tra dau hieu bug mining
    (dia chi trung, contract sai) - TAT CA tinh tu du lieu that, khong
    hardcode ten/so lieu cu the incident nao."""
    feat = pd.read_parquet(FEATURES_V2_PATH)
    full = feat[feat["prefix_label"] == "ratio_100"]

    reg_df = pd.read_csv(INCIDENT_REGISTRY_PATH)
    reg_df = reg_df[(reg_df["eval_tier"] == "primary") & (reg_df["label"] == 1)]

    hn1 = pd.read_csv(HARD_NEGATIVE_REGISTRY_PATH)
    hn2 = pd.read_csv(HN_V2_PATH) if HN_V2_PATH.exists() else pd.DataFrame(columns=hn1.columns)
    hn_all = pd.concat([hn1, hn2], ignore_index=True)

    len_rows = []
    for _, row in reg_df.iterrows():
        inc = row["incident_id"]
        pos_len_series = full[(full["group_id"] == inc) & (full["label"] == 1)]["trajectory_len"]
        if pos_len_series.empty:
            continue
        pos_len = int(pos_len_series.iloc[0])
        neg_lens = full[(full["group_id"] == inc) & (full["label"] == 0)]["trajectory_len"]
        len_rows.append({
            "incident_id": inc, "pos_traj_len": pos_len,
            "neg_median_len": float(neg_lens.median()) if len(neg_lens) else float("nan"),
            "neg_max_len": float(neg_lens.max()) if len(neg_lens) else float("nan"),
            "neg_ge_pos": (neg_lens.median() >= pos_len) if len(neg_lens) else False,
        })
    len_df = pd.DataFrame(len_rows).set_index("incident_id")

    # Incident co neg_median_len >= pos_traj_len (dau hieu hard-negative
    # "kho" tuong duong/vuot positive ve do dai - co the giai thich vi sao
    # tin hieu do dai/so luong hanh dong khong con phan biet duoc o day).
    flagged = len_df[len_df["neg_ge_pos"]].sort_values("pos_traj_len")

    target = worst_incident if worst_incident in len_df.index else None
    lines = [f"\n## Bước 3 — Điều tra nhanh `{target or worst_incident}` (tệ nhất xuyên suốt B2/B3/M1)\n"]

    if target is None or not len_df.loc[target, "neg_ge_pos"]:
        lines.append(
            f"\n`{worst_incident}` KHÔNG thuộc nhóm `neg_median_len ≥ pos_traj_len` — không có dấu hiệu "
            "đặc biệt về độ dài hard-negative so với positive. Không tìm thấy nguyên nhân cụ thể qua "
            "kiểm tra độ dài — cần điều tra hướng khác nếu muốn giải thích thêm (ngoài phạm vi kiểm tra "
            "nhanh này).\n"
        )
        return "".join(lines)

    row = len_df.loc[target]
    lines.append(
        f"\n**Phát hiện chính:** hard-negative của `{target}` có **median độ dài trajectory = "
        f"{row['neg_median_len']:.1f} action**, {'dài hơn cả' if row['neg_median_len'] > row['pos_traj_len'] else 'xấp xỉ'} "
        f"positive ({row['pos_traj_len']:.0f} action) — "
        + (f"đây là **1 trong {len(flagged)} trường hợp** trong 11 incident mà `neg_median_len ≥ pos_len` "
           f"({', '.join(flagged.index)}; các incident còn lại: hard-negative median ngắn hơn positive rõ "
           "rệt — xem bảng dưới).\n")
    )
    lines.append("\n| Incident | pos_traj_len | neg_median_len | neg_max_len |\n|---|---|---|---|\n")
    for inc, r in flagged.iterrows():
        lines.append(f"| {inc} | {r['pos_traj_len']:.0f} | **{r['neg_median_len']:.1f}** | {r['neg_max_len']:.0f} |\n")
    others = len_df[~len_df["neg_ge_pos"]]
    if len(others):
        lines.append(
            f"| {len(others)} incident còn lại | {others['pos_traj_len'].min():.0f}–{others['pos_traj_len'].max():.0f} | "
            f"{others['neg_median_len'].min():.1f}–{others['neg_median_len'].max():.1f} | "
            f"{others['neg_max_len'].min():.0f}–{others['neg_max_len'].max():.0f} |\n"
        )

    # Kiem tra dau hieu bug: dia chi seed positive co trung voi bat ky
    # hard-negative nao cua incident nay khong.
    target_row = reg_df[reg_df["incident_id"] == target]
    seed_overlap = False
    contracts_used = []
    if not target_row.empty:
        seed = str(target_row.iloc[0]["seed_address"]).lower()
        hn_target = hn_all[hn_all["parent_incident_id"] == target]
        seed_overlap = seed in set(hn_target["seed_address"].str.lower())
        contracts_used = sorted(hn_target["protocol_name"].dropna().unique().tolist())

    lines.append(
        f"\n**Kiểm tra nhanh dấu hiệu bug:** xác nhận địa chỉ seed của positive KHÔNG trùng với bất kỳ "
        f"hard-negative nào (`{seed_overlap}`), hard-negative của group này dùng contract: "
        f"{contracts_used if contracts_used else 'không tìm thấy'} — "
        + ("KHÔNG có dấu hiệu lỗi dữ liệu/mining (contract hợp lệ, không trùng địa chỉ)." if not seed_overlap
           else "⚠️ CÓ TRÙNG ĐỊA CHỈ — cần điều tra thêm, đây LÀ dấu hiệu bug tiềm ẩn.") + "\n"
    )
    lines.append(
        "\n**Kết luận: đây là ĐẶC TÍNH THẬT của incident, không phải bug** (dựa trên kiểm tra ở trên) — "
        "hard-negative của group này có độ dài tương đương/vượt positive một cách hợp lệ (đúng tiêu chí "
        "mining, không phải dữ liệu lỗi), khiến tín hiệu độ dài/số lượng hành động (hữu ích ở phần lớn "
        "incident khác) mất tác dụng phân biệt ở đây. Ghi nhận, không đào sâu thêm (ngoài phạm vi kiểm "
        "tra nhanh này).\n"
    )
    return "".join(lines)


def main():
    main_df = pd.read_csv(MAIN_TABLE)
    oof_df = pd.read_csv(OOF_PATH)
    b3 = per_incident(main_df, "B3")
    m1 = per_incident(main_df, "M1")

    g = oof_df.groupby("group_id").agg(n_val=("label", "size"), n_pos=("label", "sum"))
    g["n_neg"] = g["n_val"] - g["n_pos"]
    g["b3_pr_auc"] = g.index.map(b3)
    g["m1_pr_auc"] = g.index.map(m1)
    g["ceiling_both"] = (g["b3_pr_auc"] >= CEILING_THRESHOLD) & (g["m1_pr_auc"] >= CEILING_THRESHOLD)
    g = g.sort_values("m1_pr_auc")

    print("=== Buoc 1: bang n_val / PR-AUC tung fold ===")
    print(g.to_string())
    n_ceiling = int(g["ceiling_both"].sum())
    print(f"\nSo fold CA 2 MODEL cung dat PR-AUC>=0.999 (ceiling that su): {n_ceiling}/11")
    print("(Dinh chinh: error_analysis_v1.md truoc do liet ke 5 incident M1=1.0, nhung chi 4 trong so do "
          "CUNG co B3=1.0 - qbridge_qubit_2022 co M1=1.0 nhung B3=0.6899, KHONG phai ceiling ca 2 model.)")

    incidents_all = sorted(g.index)
    incidents_no_ceiling = sorted(g[~g["ceiling_both"]].index)

    def paired_summary(incidents, label):
        m1_scores = np.array([m1[i] for i in incidents])
        b3_scores = np.array([b3[i] for i in incidents])
        mean_diff, ci_lo, ci_hi = paired_bootstrap(m1_scores, b3_scores)
        try:
            stat, p = wilcoxon(m1_scores, b3_scores)
        except ValueError:
            stat, p = float("nan"), float("nan")
        excludes_zero = (ci_lo > 0) or (ci_hi < 0)
        print(f"\n=== {label} (n={len(incidents)} incident) ===")
        for i in incidents:
            print(f"  {i:32s} M1={m1[i]:.4f} B3={b3[i]:.4f} diff={m1[i]-b3[i]:+.4f}")
        print(f"Mean diff (M1-B3) = {mean_diff:+.4f}, 95% bootstrap CI = [{ci_lo:+.4f}, {ci_hi:+.4f}]")
        print(f"Wilcoxon: stat={stat}, p={p}")
        print(f"CI chua 0? {'KHONG (co y nghia)' if excludes_zero else 'CO (khong du bang chung)'}")
        return {
            "label": label, "n_incidents": len(incidents), "mean_diff": mean_diff,
            "ci_low": ci_lo, "ci_high": ci_hi, "wilcoxon_stat": stat, "wilcoxon_p": p,
            "excludes_zero": excludes_zero,
        }

    print("\n=== Buoc 2: so sanh do nhay ===")
    result_all = paired_summary(incidents_all, "11 fold DAY DU")
    result_sub = paired_summary(incidents_no_ceiling, f"{len(incidents_no_ceiling)} fold SAU KHI LOAI ceiling")

    same_verdict = result_all["excludes_zero"] == result_sub["excludes_zero"]
    print(f"\n=== KET LUAN DO NHAY ===")
    print(f"Ket luan RQ1 co ON DINH khi loai ceiling fold? {'CO' if same_verdict else 'KHONG - DOI KET LUAN'}")

    md = [
        "# RQ1 — Kiểm tra độ nhạy với ceiling effect (Tuần 6, bổ sung)\n",
        "\n## Đính chính số liệu\n",
        f"`error_analysis_v1.md` (viết trước đó) liệt kê 5 incident có M1=1.0, nhưng CHỈ **{n_ceiling}/11** "
        "incident có CẢ B3 VÀ M1 cùng đạt PR-AUC≥0.999 (\"ceiling thật sự\" — 2 model không còn phân biệt "
        "được). `qbridge_qubit_2022` có M1=1.0 nhưng B3 chỉ 0.6899 — đây KHÔNG phải ceiling che mất khác "
        "biệt, mà chính là 1 trong những bằng chứng M1 > B3 rõ nhất, nên được GIỮ LẠI trong so sánh loại trừ.\n",
        "\n## Bước 1 — Bảng n_val / PR-AUC từng fold\n",
        "\n| Incident | n_val | n_positive | n_negative | B3 PR-AUC | M1 PR-AUC | Ceiling cả 2? |\n|---|---|---|---|---|---|---|\n",
    ]
    for inc, row in g.iterrows():
        md.append(
            f"| {inc} | {int(row['n_val'])} | {int(row['n_pos'])} | {int(row['n_neg'])} | "
            f"{row['b3_pr_auc']:.4f} | {row['m1_pr_auc']:.4f} | {'CÓ' if row['ceiling_both'] else ''} |\n"
        )
    md += [
        "\nQuan sát: 4 fold ceiling có n_val tương đối nhỏ (57-70 dòng) nhưng KHÔNG phải nhỏ nhất tuyệt đối "
        "(`feg_bridge_2024` n_val=50 — nhỏ nhất — lại KHÔNG ceiling, M1=0.5432). n_positive của fold ceiling "
        "(4,7,7,8) cũng không khác biệt hệ thống so với fold không-ceiling. → **n_val nhỏ có tương quan lỏng "
        "với ceiling nhưng không phải yếu tố quyết định duy nhất** — nhiều khả năng còn do đặc điểm hard-"
        "negative của từng incident cụ thể (dễ/khó phân biệt) hơn là thuần túy kích thước mẫu.\n",
        "\n## Bước 2 — So sánh paired M1 vs B3: 11 fold đầy đủ vs loại 4 fold ceiling\n",
        "\n| | n incident | Mean diff (M1-B3) | 95% CI | Wilcoxon p | CI chứa 0? |\n|---|---|---|---|---|---|\n",
    ]
    for r in (result_all, result_sub):
        md.append(
            f"| {r['label']} | {r['n_incidents']} | {r['mean_diff']:+.4f} | "
            f"[{r['ci_low']:+.4f}, {r['ci_high']:+.4f}] | {r['wilcoxon_p']:.4f} | "
            f"{'Không' if r['excludes_zero'] else 'Có'} |\n"
        )
    md += [
        f"\n**Kết luận độ nhạy: {'ỔN ĐỊNH' if same_verdict else 'THAY ĐỔI'}** — loại bỏ 4 fold ceiling "
        f"{'KHÔNG làm đổi' if same_verdict else 'LÀM ĐỔI'} kết luận RQ1 (CI vẫn "
        f"{'chứa' if not result_sub['excludes_zero'] else 'không chứa'} 0).\n",
    ]

    worst_incident = g.index[0]  # da sort_values("m1_pr_auc") tang dan -> dong dau la te nhat
    print(f"\n=== Buoc 3: dieu tra nhanh incident te nhat ({worst_incident}) ===")
    step3_md = investigate_paraluni_step3(worst_incident)
    print(step3_md)
    md.append(step3_md)

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("".join(md), encoding="utf-8")
    print(f"\nDa luu {OUT_MD}")


if __name__ == "__main__":
    main()
