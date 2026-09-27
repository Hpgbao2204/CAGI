"""Buoc 5 (Tuan 5) - leakage audit cuoi tren baseline THAT: xem coefficient
cua B2 (fit tren TOAN BO 1002 prefix row, khong phai 1 fold rieng - muc dich
la nhin tong quan xem feature nao dang "gong ganh" du doan, khong phai danh
gia hieu nang) de kiem tra co shortcut nao dang ngo hay khong.

B2 chi dung action_count_* (bag-of-actions, 10 cot) - nen "shortcut theo
protocol hiem" (vd feature chi xuat hien o dung 5 vu vi trung hop mau nho)
KHONG ap dung truc tiep cho B2 (khong co feature protocol-specific). Nguy co
that su voi B2: action_count_* ty le thuan voi prefix_len -> co the chi la
proxy cho DO DAI trajectory (da canh bao o EDA Buoc 1: IQR do dai 2 lop
KHONG chong lan) chu khong phai tin hieu ve LOAI hanh dong.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.models.baselines import B2BagOfActionsLogisticRegression

REPO_ROOT = Path(__file__).resolve().parents[1]
FEATURES_PATH = REPO_ROOT / "data" / "processed" / "features_v1.parquet"

META_COLS = ["trajectory_id", "source_id", "group_id", "kind", "chain", "label",
             "prefix_label", "prefix_len", "trajectory_len"]


def main():
    df = pd.read_parquet(FEATURES_PATH)
    feature_cols = [c for c in df.columns if c not in META_COLS]
    X = df[feature_cols]
    y = df["label"]

    model = B2BagOfActionsLogisticRegression()
    model.fit(X, y, df["group_id"])

    coefs = model.model.coef_[0]
    coef_df = pd.DataFrame({"feature": model.feature_cols_, "coef": coefs}).sort_values("coef", ascending=False)
    print("=== He so B2 (fit tren TOAN BO 1002 dong, chi de xem xet dinh tinh) ===")
    print(coef_df.to_string(index=False))

    # 1. Tuong quan giua action_count tong (bag-of-actions sum) va prefix_len
    total_action_count = X[[c for c in feature_cols if c.startswith("action_count_")]].sum(axis=1)
    corr_len = np.corrcoef(total_action_count, df["prefix_len"])[0, 1]
    corr_label = np.corrcoef(total_action_count, y)[0, 1]
    print(f"\nTuong quan pearson(tong action_count, prefix_len) = {corr_len:.4f}")
    print(f"Tuong quan pearson(tong action_count, label) = {corr_label:.4f}")

    # 2. Feature co he so duong lon nhat: kiem tra co bi 1 incident don le
    #    "gong ganh" hay khong (dem so group_id KHAC NHAU co gia tri > 0 cho
    #    feature do, trong cac dong label=1).
    top_feat = coef_df.iloc[0]["feature"]
    pos_rows = df[df["label"] == 1]
    n_groups_with_feature = (pos_rows[pos_rows[top_feat] > 0]["group_id"]).nunique()
    n_groups_total_pos = pos_rows["group_id"].nunique()
    print(f"\nFeature co he so cao nhat: '{top_feat}' (coef={coef_df.iloc[0]['coef']:.4f})")
    print(f"  -> xuat hien (>0) o {n_groups_with_feature}/{n_groups_total_pos} group positive "
          f"({'RAI RAC nhieu incident' if n_groups_with_feature >= n_groups_total_pos * 0.5 else 'CHI vai incident - CAN NGHI NGO shortcut mau nho'})")

    # 3. In phan bo top_feat theo tung group positive (de xem co 1 incident
    #    don le chiem uu the hay khong)
    print(f"\nPhan bo '{top_feat}' theo group (chi hang positive):")
    print(pos_rows.groupby("group_id")[top_feat].agg(["count", "mean", "max"]).to_string())

    findings = []
    if abs(corr_len) > 0.5:
        findings.append(
            f"CANH BAO: tong action_count (dung boi B2) tuong quan MANH voi prefix_len "
            f"(pearson r={corr_len:.3f}) — khop voi canh bao o EDA Buoc 1 (IQR do dai 2 lop khong "
            f"chong lan). B2 co nguy co dang hoc PHAN LON tu 'do dai/so luong action' (cardinality) "
            f"hon la NGU NGHIA loai hanh dong — day la 1 dang shortcut, khong phai tin hieu "
            f"typology laundering that su."
        )
    if n_groups_with_feature < n_groups_total_pos * 0.5:
        findings.append(
            f"CANH BAO: feature co he so cao nhat ('{top_feat}') chi xuat hien o "
            f"{n_groups_with_feature}/{n_groups_total_pos} group positive — co the la dac diem "
            f"rieng cua 1-2 incident thay vi tin hieu chung cho ca lop positive."
        )
    if not findings:
        findings.append("Khong phat hien shortcut ro rang nao trong pham vi kiem tra nay (van can them du lieu de ket luan chac chan).")

    print("\n=== KET LUAN BUOC 5 ===")
    for f in findings:
        print("- " + f)

    # Ghi vao file rieng de dinh kem EDA report
    out_path = REPO_ROOT / "results" / "reports" / "leakage_audit_v1_findings.md"
    lines = [
        "# Leakage audit — baseline B2 (Bước 5, Tuần 5)\n",
        "\n## Hệ số B2 (fit trên toàn bộ 1002 dòng)\n",
        "\n```\n" + coef_df.to_string(index=False) + "\n```\n",
        f"\n## Tương quan\n- pearson(tổng action_count, prefix_len) = {corr_len:.4f}\n"
        f"- pearson(tổng action_count, label) = {corr_label:.4f}\n",
        f"\n## Feature hệ số cao nhất: `{top_feat}`\n"
        f"- Xuất hiện ở {n_groups_with_feature}/{n_groups_total_pos} group positive.\n",
        "\n## Phát hiện\n",
    ] + [f"- {f}\n" for f in findings]
    out_path.write_text("".join(lines), encoding="utf-8")
    print(f"\nDa ghi {out_path}")


if __name__ == "__main__":
    main()
