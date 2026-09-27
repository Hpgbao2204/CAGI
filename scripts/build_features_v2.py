"""Buoc 4 (Tuan 5, dot 2 - sua shortcut) - rebuild features_v2.parquet SAU
khi: (1) mine bo sung hard-negative theo tieu chi do phuc tap (Buoc 2), (2)
them action_count_*_ratio + coverage filter trong B2 (Buoc 3).

Khac build_features_v1.py: include_v2_complexity=True (nap ca hard-negative
moi), va ghi them thong ke coverage (GLOBAL, chi de bao cao/doi chieu - viec
loai feature THAT su dien ra trong B2.fit() tren tung train fold, xem
src/models/baselines.py).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.features.extractor import extract_all_prefixes, generate_prefixes
from src.pipeline.dataset_builder import load_rq1_trajectories

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_PARQUET = REPO_ROOT / "data" / "processed" / "features_v2.parquet"
OUT_SCHEMA = REPO_ROOT / "configs" / "features_v2_computed.json"


def main():
    print("=== Buoc 4a: build trajectory that (KE CA hard-negative v2 do phuc tap) ===", flush=True)
    items = load_rq1_trajectories(verbose=True, include_v2_complexity=True)
    n_pos = sum(1 for i in items if i.label == 1)
    n_neg = sum(1 for i in items if i.label == 0)
    n_neg_v2 = sum(1 for i in items if i.kind == "hard_negative_mined_v2_complexity")
    print(f"\nTong trajectory: {len(items)} (positive={n_pos}, negative={n_neg}, "
          f"trong do hard-negative v2 moi={n_neg_v2})", flush=True)

    total_specs = sum(len(generate_prefixes(i.trajectory)) for i in items)
    print(f"Tong prefix row = {total_specs}", flush=True)

    print("\n=== Buoc 4b: tinh feature (bao gom action_count_*_ratio moi) ===", flush=True)
    rows = []
    meta_rows = []
    leakage_violations = []
    for item in items:
        for spec, feats in extract_all_prefixes(item.trajectory, include_endpoint_context=False):
            action_count_keys = [k for k in feats if k.startswith("action_count_") and not k.endswith("_ratio")]
            total_counted = sum(feats[k] for k in action_count_keys)
            if total_counted != spec.length:
                leakage_violations.append((item.source_id, spec.label, spec.length, total_counted))

            feats = dict(feats)
            feats.pop("prefix_len", None)
            rows.append(feats)
            meta_rows.append({
                "trajectory_id": item.trajectory.trajectory_id,
                "source_id": item.source_id,
                "group_id": item.group_id,
                "kind": item.kind,
                "chain": item.chain,
                "label": item.label,
                "prefix_label": spec.label,
                "prefix_len": spec.length,
                "trajectory_len": len(item.trajectory),
            })

    if leakage_violations:
        print(f"\n*** DUNG LAI: {len(leakage_violations)} vi pham invariant chong leakage ***")
        for v in leakage_violations[:20]:
            print("  ", v)
        raise SystemExit(1)
    print(f"Kiem tra leakage tren {len(rows)} prefix row: SACH (0 vi pham).", flush=True)

    X = pd.DataFrame(rows).fillna(0.0)
    meta = pd.DataFrame(meta_rows)
    full = pd.concat([meta, X], axis=1)
    assert len(full) == total_specs

    OUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    full.to_parquet(OUT_PARQUET, index=False)
    print(f"\nDa luu {OUT_PARQUET} ({len(full)} dong, {len(X.columns)} feature column)", flush=True)

    # Thong ke coverage GLOBAL (chi de bao cao/doi chieu - viec loai feature
    # THAT SU dien ra trong B2.fit() tren tung train fold, khong phai o day).
    action_ratio_cols = [c for c in X.columns if c.startswith("action_count_") and c.endswith("_ratio")]
    pos_rows = full[full["label"] == 1]
    coverage_report = {}
    for c in action_ratio_cols:
        n_groups = pos_rows[pos_rows[c] > 0]["group_id"].nunique()
        coverage_report[c] = {"n_positive_groups_nonzero": int(n_groups), "total_positive_groups": int(pos_rows["group_id"].nunique())}
    low_coverage = [c for c, v in coverage_report.items() if v["n_positive_groups_nonzero"] < 2]

    feature_cols = sorted(X.columns)
    schema = {
        "version": "v2",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "n_rows": int(len(full)),
        "n_positive_trajectories": n_pos,
        "n_negative_trajectories": n_neg,
        "n_negative_trajectories_v2_complexity_supplement": n_neg_v2,
        "feature_groups_used": ["temporal", "structural", "economic", "semantic_action", "motif"],
        "feature_groups_excluded": ["context"],
        "exclude_reason": "context group lien quan endpoint - loai theo anti_leakage_rules (early detection).",
        "feature_columns": feature_cols,
        "n_feature_columns": len(feature_cols),
        "leakage_check": f"PASS - tong action_count_* (ban tho) == prefix_len cho tat ca {len(full)} prefix row",
        "source_dataset_freeze": "v0.9 + mining bo sung do phuc tap (Tuan 5 dot 2)",
        "generate_prefixes_params": {"ratios": [0.25, 0.5, 0.75, 1.0], "k_values": [2, 3, 5, 7]},
        "v2_changes_vs_v1": [
            "Them action_count_{type}_ratio (chuan hoa theo prefix_len) - dung lam feature CHINH cho B2, giam tuong quan truc tiep voi do dai (xem leakage_audit_v1_findings.md: r=1.000 o ban tho).",
            "B2BagOfActionsLogisticRegression them min_positive_incident_coverage=2 (tinh TREN TRAIN FOLD trong fit(), khong tinh truoc o day) - loai feature chi xuat hien o <2 incident positive (bug thuc: action_count_lending_deposit chi o bsc_token_hub_2022).",
            "Mine bo sung hard-negative theo tieu chi do phuc tap (compute_min_candidate_events, log-scale theo do dai positive tuong ung) - xem metadata/hard_negative_registry_v2_complexity.csv.",
        ],
        "action_count_ratio_coverage_global_report_only": coverage_report,
        "low_coverage_features_global_note": low_coverage,
        "note_coverage": "Bao cao GLOBAL o tren CHI de doi chieu/tai lieu hoa - viec loai feature thuc su dien ra RIENG cho tung train fold trong B2.fit() (xem src/models/baselines.py) de tranh ro ri thong ke tu fold validation.",
    }
    OUT_SCHEMA.write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Da luu {OUT_SCHEMA}", flush=True)
    print(f"\nFeature co coverage < 2 incident positive (bao cao GLOBAL): {low_coverage}")


if __name__ == "__main__":
    main()
