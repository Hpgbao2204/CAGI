"""Tuan 9 (bo sung) - probe M1 tren benign entity fan-out cao CO NHAN CONG
KHAI XAC NHAN (market maker/exchange hot wallet - metadata/
high_fanout_benign_candidates.csv, 4 candidate, xem
results/reports/high_fanout_benign_probe.md cho nguon xac minh).

QUAN TRONG: dung max_iterations=0 (CHI fetch chinh dia chi candidate, KHONG
mo rong frontier nhieu hop) - vi day la entity fan-out SIEU CAO
(vd Binance Hot Wallet co hang nghin counterparty/ngay), mo rong frontier
binh thuong (max_iterations=2 nhu hard-negative) se bung no so luong API
call. fan_out/branch_count van tinh dung tu hanh dong TRUC TIEP cua chinh
candidate (khong can multi-hop de do "co fan-out cao hay khong").

KHONG train lai M1 - chi load m1_final.joblib (da freeze Tuan 6/7) va
predict_proba.
"""
from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd

from src.features.extractor import extract_features
from src.pipeline.incident_pipeline import expand_and_build_trajectory
from src.trajectories.builder import load_trajectory_config
from scripts.run_e6_robustness import collect_unmatched_negative_candidates

REPO_ROOT = Path(__file__).resolve().parents[1]
CANDIDATES_PATH = REPO_ROOT / "metadata" / "high_fanout_benign_candidates.csv"
M1_MODEL_PATH = REPO_ROOT / "results" / "models" / "m1_final.joblib"
OUT_TABLE = REPO_ROOT / "results" / "tables" / "high_fanout_benign_probe.csv"
OUT_MD = REPO_ROOT / "results" / "reports" / "high_fanout_benign_probe.md"
OOF_M1_FULL_PATH = REPO_ROOT / "data" / "processed" / "oof_predictions_v1.csv"
FEATURES_V2_PATH = REPO_ROOT / "data" / "processed" / "features_v2.parquet"


def main():
    print("=== Nap 4 candidate co nhan cong khai xac nhan ===", flush=True)
    cand_df = pd.read_csv(CANDIDATES_PATH)
    print(cand_df[["candidate_id", "entity_name", "entity_type", "chain"]].to_string(index=False), flush=True)

    config = load_trajectory_config()
    model = joblib.load(M1_MODEL_PATH)
    print(f"\nDa load m1_final.joblib (KHONG train lai) - {len(model.feature_cols_)} feature.", flush=True)

    rows = []
    print("\n=== Buoc 2: build trajectory (do_collect=True, max_iterations=0 - CHI dia chi candidate) ===", flush=True)
    for _, r in cand_df.iterrows():
        print(f"\n--- {r['candidate_id']} ({r['entity_name']}, {r['chain']}) ---", flush=True)
        traj, _, processed = expand_and_build_trajectory(
            r["chain"], r["address"], int(r["start_block"]), r["candidate_id"], 0,
            config=config, do_collect=True, max_iterations=0,
        )
        n = len(traj)
        print(f"  n_actions={n}, addresses_processed={processed}", flush=True)
        if n == 0:
            print("  CANH BAO: trajectory rong - khong co hoat dong trong cua so, bo qua candidate nay.")
            continue

        feats = extract_features(traj, n, include_endpoint_context=False)
        fan_out = feats["fan_out"]
        print(f"  fan_out={fan_out}, branch_count={feats['branch_count']}, "
              f"unique_counterparties={feats['unique_counterparties']}", flush=True)

        row_df = pd.DataFrame([feats])
        for c in model.feature_cols_:
            if c not in row_df.columns:
                row_df[c] = 0.0
        prob = model.predict_proba(row_df[model.feature_cols_])[0]
        flagged = "FALSE POSITIVE (model gan nhan positive)" if prob >= 0.5 else "dung (negative)"
        print(f"  M1 prob={prob:.4f} -> {flagged}", flush=True)

        rows.append({
            "candidate_id": r["candidate_id"], "entity_name": r["entity_name"], "entity_type": r["entity_type"],
            "chain": r["chain"], "public_label": r["public_label"], "n_actions": n, "fan_out": fan_out,
            "branch_count": feats["branch_count"], "unique_counterparties": feats["unique_counterparties"],
            "m1_prob": float(prob), "m1_flagged_positive_at_0.5": bool(prob >= 0.5),
        })

    result_df = pd.DataFrame(rows)
    OUT_TABLE.parent.mkdir(parents=True, exist_ok=True)
    result_df.to_csv(OUT_TABLE, index=False)
    print(f"\nDa luu {OUT_TABLE}")

    n_ok = len(result_df)
    n_flagged = int(result_df["m1_flagged_positive_at_0.5"].sum()) if n_ok else 0
    print(f"\n=== TOM TAT ===")
    print(f"Candidate co trajectory hop le: {n_ok}/{len(cand_df)}")
    print(f"Bi M1 gan nhan positive (false positive, vi tat ca deu benign): {n_flagged}/{n_ok}")

    # --- Buoc 3: so sanh 3 nhom, CUNG 1 MODEL (m1_final.joblib) + CUNG
    # threshold=0.5, tren FULL-LENGTH trajectory cua tung nhom - cong bang,
    # khong tron model khac nhau tung fold (OOF) voi model co dinh. ---
    print("\n=== Buoc 3: so sanh 3 nhom (CUNG m1_final.joblib, threshold=0.5) ===", flush=True)

    def _predict_full_length_rows(feat_rows: list) -> pd.Series:
        if not feat_rows:
            return pd.Series([], dtype=float)
        df_feats = pd.DataFrame(feat_rows)
        for c in model.feature_cols_:
            if c not in df_feats.columns:
                df_feats[c] = 0.0
        return pd.Series(model.predict_proba(df_feats[model.feature_cols_].fillna(0.0)))

    # Nhom 1: matched hard-negative (fan_out<=3, chinh thuc) - dung lai
    # features_v2.parquet, prefix_label=="ratio_100" (full trajectory).
    feat_v2 = pd.read_parquet(FEATURES_V2_PATH)
    matched_100 = feat_v2[(feat_v2["kind"].isin(["hard_negative_mined", "hard_negative_mined_v2_complexity"])) &
                           (feat_v2["prefix_label"] == "ratio_100")]
    matched_probs = model.predict_proba(matched_100[model.feature_cols_].fillna(0.0))
    matched_fan_out_mean = float(matched_100["fan_out"].mean())

    # Nhom 2: unmatched-negative (E6, fan_out>3 nhung chua xac nhan danh
    # tinh) - tai su dung candidate list DA CACHE (nhanh, khong API moi),
    # build lai trajectory FULL (max_iterations=2, giong het E6 goc).
    print("  Dang build lai trajectory unmatched-negative (cache, khong API moi)...", flush=True)
    unmatched_candidates = collect_unmatched_negative_candidates()
    unmatched_feat_rows = []
    unmatched_fan_outs = []
    for c in unmatched_candidates:
        traj, _, _ = expand_and_build_trajectory(
            c["chain"], c["address"], int(c["start_block"]), c["parent_incident_id"], 0,
            config=config, do_collect=False, max_iterations=2,
        )
        if len(traj) == 0:
            continue
        feats = extract_features(traj, len(traj), include_endpoint_context=False)
        unmatched_feat_rows.append(feats)
        unmatched_fan_outs.append(feats["fan_out"])
    unmatched_probs = _predict_full_length_rows(unmatched_feat_rows)
    unmatched_fan_out_mean = float(pd.Series(unmatched_fan_outs).mean()) if unmatched_fan_outs else float("nan")
    print(f"  Unmatched-negative: {len(unmatched_feat_rows)} trajectory du doan duoc.", flush=True)

    comparison_rows = [
        {"group": "matched_hard_negative (fan_out<=3, chinh thuc)", "n": len(matched_100),
         "mean_fan_out": matched_fan_out_mean,
         "pct_flagged_positive_at_0.5": float((matched_probs >= 0.5).mean() * 100)},
        {"group": "unmatched_negative (E6, fan_out>3, danh tinh CHUA xac nhan)", "n": len(unmatched_feat_rows),
         "mean_fan_out": unmatched_fan_out_mean,
         "pct_flagged_positive_at_0.5": float((unmatched_probs >= 0.5).mean() * 100) if len(unmatched_probs) else float("nan")},
        {"group": "high_fanout_benign_labeled (nhom moi, nhan cong khai xac nhan)", "n": n_ok,
         "mean_fan_out": float(result_df["fan_out"].mean()) if n_ok else float("nan"),
         "pct_flagged_positive_at_0.5": float(n_flagged / n_ok * 100) if n_ok else float("nan")},
    ]
    comparison_df = pd.DataFrame(comparison_rows)
    OUT_COMPARISON = REPO_ROOT / "results" / "tables" / "three_group_comparison.csv"
    comparison_df.to_csv(OUT_COMPARISON, index=False)
    print(f"\nDa luu {OUT_COMPARISON}")
    print(comparison_df.to_string(index=False))

    md = [
        "# Probe: M1 trên benign entity fan-out cao có nhãn công khai xác nhận\n",
        "\n(Tuần 9 bổ sung — theo yêu cầu sau khi E6 phát hiện M1 làm tệ hơn trên "
        "\"unmatched negative\" mà danh tính KHÔNG được xác nhận công khai. Bài test này "
        "dùng 4 candidate market maker/exchange hot wallet có **nhãn công khai xác nhận** "
        "— evidence mạnh hơn hẳn nhóm unmatched-negative.)\n",
        "\n## Bước 1 — 4 candidate đã xác minh (KHÔNG dùng contract router/aggregator)\n",
        "\n| Entity | Loại | Chain | Nhãn công khai | Nguồn xác minh |\n|---|---|---|---|---|\n",
    ]
    for _, r in cand_df.iterrows():
        md.append(f"| {r['entity_name']} | {r['entity_type']} | {r['chain']} | `{r['public_label']}` | "
                   f"{r['source_verification'][:80]}… |\n")
    md += [
        "\nXác minh qua blockscan.com (multichain explorer độc lập, không bị chặn bot như "
        "Etherscan/BscScan trực tiếp — đã thử fetch trực tiếp Etherscan/BscScan, bị "
        "HTTP 403) — cả 4 địa chỉ đều được xác nhận là **EOA** (không phải smart contract) "
        "và **entity thật có nhãn công khai**, không suy đoán từ tên ví. Chi tiết đầy đủ "
        "từng nguồn trong `metadata/high_fanout_benign_candidates.csv`.\n",
        "\n## Bước 2 — Build trajectory\n",
        "\n`max_iterations=0` (CHỈ hoạt động trực tiếp của chính candidate, KHÔNG mở rộng "
        "frontier nhiều hop) — vì đây là entity fan-out SIÊU cao, mở rộng như hard-negative "
        "(max_iterations=2) sẽ bùng nổ số lượng API call. fan_out vẫn tính đúng từ hành động "
        "TRỰC TIẾP của candidate.\n",
        "\n| Entity | n_actions | fan_out | branch_count | unique_counterparties |\n|---|---|---|---|---|\n",
    ]
    for _, r in result_df.iterrows():
        md.append(f"| {r['entity_name']} | {int(r['n_actions'])} | {r['fan_out']:.0f} | "
                   f"{r['branch_count']:.0f} | {r['unique_counterparties']:.0f} |\n")
    n_high_fanout = int((result_df["fan_out"] > 3).sum()) if n_ok else 0
    md.append(f"\n**Xác nhận mục tiêu:** {n_high_fanout}/{n_ok} candidate có fan_out THẬT > 3 "
              f"(đúng nhóm cần test).\n")

    md += [
        "\n## Bước 3 — Kết quả M1 (m1_final.joblib, KHÔNG train lại) + so sánh 3 nhóm\n",
        "\n| Entity | M1 prob | Kết luận |\n|---|---|---|\n",
    ]
    for _, r in result_df.iterrows():
        verdict = "❌ FALSE POSITIVE (benign nhưng bị gắn nhãn positive)" if r["m1_flagged_positive_at_0.5"] else "✅ đúng (negative)"
        md.append(f"| {r['entity_name']} | {r['m1_prob']:.4f} | {verdict} |\n")
    md += [
        f"\n**{n_flagged}/{n_ok} candidate benign fan-out cao bị M1 gắn nhãn positive "
        f"(false positive) ở threshold=0.5.**\n",
        "\n### Bảng so sánh 3 nhóm (cùng model `m1_final.joblib`, cùng threshold=0.5, "
        "cùng full-length trajectory)\n\n",
        comparison_df.to_string(index=False),
        "\n",
    ]
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("".join(md), encoding="utf-8")
    print(f"\nDa luu {OUT_MD}")


if __name__ == "__main__":
    main()
