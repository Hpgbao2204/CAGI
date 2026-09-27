"""Cap nhat metadata/split_manifest.json - them cac hard-negative moi mine
(vong do phuc tap, Buoc 2 Tuan 5 dot 2) vao dung group (theo
parent_incident_id trong metadata/hard_negative_registry_v2_complexity.csv).

split_manifest.json la nguon xac thuc DUY NHAT cho group membership (xem
src/pipeline/dataset_builder.py::_load_group_membership) - PHAI cap nhat
o day, khong duoc de dataset_builder tu suy luan group_id theo cach khac.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "metadata" / "split_manifest.json"
V2_REGISTRY_PATH = REPO_ROOT / "metadata" / "hard_negative_registry_v2_complexity.csv"


def main():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    v2_df = pd.read_csv(V2_REGISTRY_PATH)

    n_added = 0
    for g in manifest["groups"]:
        group_id = g["group_id"]
        new_ids = v2_df[v2_df["parent_incident_id"] == group_id]["hard_negative_id"].tolist()
        if not new_ids:
            continue
        existing = set(g["members"].get("mined_hard_negative_ids", []))
        to_add = [i for i in new_ids if i not in existing]
        g["members"].setdefault("mined_hard_negative_ids", []).extend(to_add)
        n_added += len(to_add)
        print(f"{group_id}: +{len(to_add)} hard-negative moi (tong mined = {len(g['members']['mined_hard_negative_ids'])})")

    manifest["n_mined_hard_negatives_raw_v2_complexity"] = len(v2_df)
    manifest["note_v2_complexity"] = (
        "Vong mine bo sung Tuan 5 (sua shortcut do dai) - them tieu chi "
        "min_candidate_events (log-scale theo do dai positive tuong ung), "
        "xem src/collect/hard_negative_miner.py::compute_min_candidate_events. "
        "Ghi trong metadata/hard_negative_registry_v2_complexity.csv (file "
        "RIENG, khong gop vao hard_negative_registry.csv cu)."
    )

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nDa them tong {n_added} hard_negative_id moi vao {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
