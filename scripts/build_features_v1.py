"""Buoc 2+3 (Tuan 5) - sinh prefix that + tinh feature that cho toan bo tap
RQ1 (11 positive + 408 hard-negative), luu data/processed/features_v1.parquet
+ configs/features_v1_computed.json (version hoa feature schema).

Buoc 2: generate_prefixes tren tung trajectory that -> xac nhan tong so
prefix row dung ~1002 (KHONG gia dinh, tinh that).
Buoc 3: extract_all_prefixes (6 nhom feature: temporal/structural/economic/
semantic_action/motif — context group LOAI BO mac dinh vi muc tieu la early
detection, khop anti_leakage_rules trong configs/features.yaml) tren tung
prefix. Kiem tra lai invariant chong leakage TREN DU LIEU THAT (khong chi
tren fixture gia): voi moi prefix row, tong action_count_* phai == prefix_len.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.features.extractor import extract_all_prefixes, generate_prefixes
from src.pipeline.dataset_builder import load_rq1_trajectories

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_PARQUET = REPO_ROOT / "data" / "processed" / "features_v1.parquet"
OUT_SCHEMA = REPO_ROOT / "configs" / "features_v1_computed.json"


def main():
    print("=== Buoc 2: build trajectory that + sinh prefix ===", flush=True)
    items = load_rq1_trajectories(verbose=False)
    print(f"Tong trajectory: {len(items)} (positive={sum(1 for i in items if i.label==1)}, "
          f"negative={sum(1 for i in items if i.label==0)})", flush=True)

    total_specs = sum(len(generate_prefixes(i.trajectory)) for i in items)
    print(f"Tong prefix row (chi dem, chua tinh feature) = {total_specs}", flush=True)
    if total_specs != 1002:
        print(f"*** CANH BAO: {total_specs} != 1002 (con so tai freeze v0.9) — can dieu tra truoc khi tiep tuc ***")

    print("\n=== Buoc 3: tinh feature that (6 nhom) cho tung prefix ===", flush=True)
    rows = []
    meta_rows = []
    leakage_violations = []
    for item in items:
        for spec, feats in extract_all_prefixes(item.trajectory, include_endpoint_context=False):
            # Kiem tra invariant chong leakage TREN DU LIEU THAT (khong chi
            # fixture gia trong tests/test_no_future_leakage.py): tong
            # action_count_* phai dung bang prefix_len — neu sai, co nghia
            # extract_features dang doc vuot qua prefix (bug that).
            action_count_keys = [k for k in feats if k.startswith("action_count_")]
            total_counted = sum(feats[k] for k in action_count_keys)
            if total_counted != spec.length:
                leakage_violations.append((item.source_id, spec.label, spec.length, total_counted))

            # extract_features() tu them "prefix_len" trung voi meta_rows'
            # prefix_len (cung gia tri) - bo cot trung, giu "prefix_ratio"
            # (feature that, khong trung meta).
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
        print(f"\n*** DUNG LAI: phat hien {len(leakage_violations)} vi pham invariant chong leakage TREN DU LIEU THAT ***")
        for v in leakage_violations[:20]:
            print("  ", v)
        raise SystemExit(1)
    print(f"Kiem tra leakage tren {len(rows)} prefix row THAT: SACH (0 vi pham action_count == prefix_len).", flush=True)

    X = pd.DataFrame(rows).fillna(0.0)
    meta = pd.DataFrame(meta_rows)
    full = pd.concat([meta, X], axis=1)

    assert len(full) == total_specs == 1002, f"So dong cuoi cung ({len(full)}) khong khop {total_specs}/1002"

    OUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    full.to_parquet(OUT_PARQUET, index=False)
    print(f"\nDa luu {OUT_PARQUET} ({len(full)} dong, {len(X.columns)} feature column)", flush=True)

    feature_cols = sorted(X.columns)
    schema = {
        "version": "v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "n_rows": int(len(full)),
        "n_positive_trajectories": int(sum(1 for i in items if i.label == 1)),
        "n_negative_trajectories": int(sum(1 for i in items if i.label == 0)),
        "feature_groups_used": ["temporal", "structural", "economic", "semantic_action", "motif"],
        "feature_groups_excluded": ["context"],
        "exclude_reason": "context group (known_mixer_interaction, public_exit_service_label, protocol_category) lien quan endpoint - loai theo anti_leakage_rules trong configs/features.yaml vi muc tieu la early detection (canh bao TRUOC endpoint).",
        "feature_columns": feature_cols,
        "n_feature_columns": len(feature_cols),
        "leakage_check": "PASS - tong action_count_* == prefix_len cho tat ca {} prefix row that (khong chi fixture gia)".format(len(full)),
        "source_dataset_freeze": "v0.9",
        "generate_prefixes_params": {"ratios": [0.25, 0.5, 0.75, 1.0], "k_values": [2, 3, 5, 7]},
    }
    OUT_SCHEMA.write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Da luu {OUT_SCHEMA}", flush=True)


if __name__ == "__main__":
    main()
