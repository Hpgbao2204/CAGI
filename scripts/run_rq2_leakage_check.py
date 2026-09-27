"""Tuan 7 (RQ2) Buoc 4 (BAT BUOC, chay TRUOC Buoc 3 lead time - theo dung
noi dung yeu cau, du danh so sau Buoc 3 trong de bai) - xac nhan feature
dua vao M1 KHONG chua thong tin endpoint (mixer/CEX label), chay THAT tren
du lieu prefix dang dung cho RQ2 (features_v2.parquet, khong phai fixture
gia cua test_no_future_leakage.py).

Neu phat hien leakage: DUNG LAI, khong tinh lead time (ket qua se vo nghia).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from src.models.baselines import M1TypedTemporalMotifModel

REPO_ROOT = Path(__file__).resolve().parents[1]
FEATURES_PATH = REPO_ROOT / "data" / "processed" / "features_v2.parquet"
META_COLS = ["trajectory_id", "source_id", "group_id", "kind", "chain", "label",
             "prefix_label", "prefix_len", "trajectory_len"]
ENDPOINT_FEATURES = {"known_mixer_interaction", "public_exit_service_label", "protocol_category_diversity"}


def main():
    df = pd.read_parquet(FEATURES_PATH)
    feature_cols = [c for c in df.columns if c not in META_COLS]

    print("=== Kiem tra 1: features_v2.parquet KHONG co cot endpoint-context ===")
    present = ENDPOINT_FEATURES & set(feature_cols)
    print(f"  Cot endpoint-context xuat hien trong feature_cols: {present or '(khong co)'}")
    check1 = not present

    print("\n=== Kiem tra 2: M1.feature_cols_ (sau fit that tren du lieu RQ2) KHONG dung endpoint-context ===")
    X = df[feature_cols]
    y = df["label"]
    groups = df["group_id"]
    model = M1TypedTemporalMotifModel()
    model.fit(X, y, groups)
    present2 = ENDPOINT_FEATURES & set(model.feature_cols_)
    print(f"  Cot endpoint-context trong model.feature_cols_: {present2 or '(khong co)'}")
    check2 = not present2

    print("\n=== Kiem tra 3: invariant chong leakage (sum action_count_tho == prefix_len) TREN DU LIEU THAT ===")
    action_cols = [c for c in feature_cols if c.startswith("action_count_") and not c.endswith("_ratio")]
    totals = df[action_cols].sum(axis=1)
    violations = df[totals != df["prefix_len"]]
    check3 = len(violations) == 0
    print(f"  So dong vi pham (tong action_count_tho != prefix_len): {len(violations)}/{len(df)}")

    print("\n=== Kiem tra 4: prefix_len khong bao gio > trajectory_len (khong doc vuot tuong lai) ===")
    violations4 = df[df["prefix_len"] > df["trajectory_len"]]
    check4 = len(violations4) == 0
    print(f"  So dong vi pham (prefix_len > trajectory_len): {len(violations4)}/{len(df)}")

    all_pass = check1 and check2 and check3 and check4
    print(f"\n=== KET LUAN: {'SACH - khong phat hien endpoint leakage, TIEP TUC Buoc 3' if all_pass else 'PHAT HIEN VAN DE - DUNG LAI'} ===")
    if not all_pass:
        sys.exit(1)


if __name__ == "__main__":
    main()
