"""Tính số liệu thật cho freeze v0.4 (sau khi sửa bug merge_events_into_semantic_actions
2026-08-13): raw/usable hard-negative, tổng prefix row toàn dataset, tỷ lệ rỗng
theo từng parent_incident_id. Dùng expand_and_build_trajectory + generate_prefixes
thật (KHÔNG suy đoán/đếm dòng thô)."""
import json

import pandas as pd

from src.collect.hard_negative_miner import HARD_NEGATIVE_REGISTRY_PATH
from src.features.extractor import generate_prefixes
from src.pipeline.incident_pipeline import REGISTRY_PATH, expand_and_build_trajectory
from src.trajectories.builder import load_trajectory_config

config = load_trajectory_config()
reg_df = pd.read_csv(REGISTRY_PATH)
hn_df = pd.read_csv(HARD_NEGATIVE_REGISTRY_PATH)

total_prefix_rows = 0
positive_rows = 0
negative_rows = 0
n_empty_by_incident = {}
n_total_by_incident = {}

print("=== POSITIVE + CONTROL GOC (10 dong incident_registry.csv) ===")
for _, row in reg_df.iterrows():
    traj, _, _ = expand_and_build_trajectory(
        row["chain_primary"], row["seed_address"], int(row["start_block"]), row["incident_id"], int(row["label"]),
        config=config, do_collect=False, max_iterations=2,
    )
    n_prefix = len(generate_prefixes(traj))
    total_prefix_rows += n_prefix
    if row["label"] == 1:
        positive_rows += n_prefix
    else:
        negative_rows += n_prefix
    print(f"{row['incident_id']:40s} n_actions={len(traj):4d} n_prefix={n_prefix}")

print("\n=== HARD-NEGATIVE MINING (rebuild that tung dong) ===")
n_empty_total = 0
for _, row in hn_df.iterrows():
    parent = row["parent_incident_id"]
    n_total_by_incident[parent] = n_total_by_incident.get(parent, 0) + 1
    traj, _, _ = expand_and_build_trajectory(
        row["chain"], row["seed_address"], int(row["start_block"]), row["hard_negative_id"], 0,
        config=config, do_collect=False, max_iterations=2,
    )
    if len(traj) == 0:
        n_empty_total += 1
        n_empty_by_incident[parent] = n_empty_by_incident.get(parent, 0) + 1
        continue
    n_prefix = len(generate_prefixes(traj))
    total_prefix_rows += n_prefix
    negative_rows += n_prefix

raw = len(hn_df)
usable_mining = raw - n_empty_total
n_original_controls = len(reg_df[reg_df["label"] == 0])
usable_total = usable_mining + n_original_controls

print(f"\nraw mining = {raw}")
print(f"dùng được (mining, >=1 prefix row) = {usable_mining} (rỗng: {n_empty_total})")
print(f"+ {n_original_controls} hard-negative control gốc (đều dùng được)")
print(f"TỔNG dùng được = {usable_total} (ngưỡng yêu cầu: >=200)")
print(f"\nTổng prefix row toàn dataset = {total_prefix_rows} (positive={positive_rows}, negative={negative_rows})")

print("\n=== Tỷ lệ rỗng theo parent_incident_id ===")
for iid in sorted(n_total_by_incident):
    n_total = n_total_by_incident[iid]
    n_empty = n_empty_by_incident.get(iid, 0)
    print(f"{iid:30s} checked={n_total:3d} empty={n_empty:3d} rate={100*n_empty/n_total:.1f}%")

out = {
    "raw_mining": raw,
    "usable_mining": usable_mining,
    "n_empty_mining": n_empty_total,
    "n_original_controls": n_original_controls,
    "usable_total": usable_total,
    "total_prefix_rows": total_prefix_rows,
    "positive_prefix_rows": positive_rows,
    "negative_prefix_rows": negative_rows,
    "empty_rate_by_incident": {
        iid: {"checked": n_total_by_incident[iid], "empty": n_empty_by_incident.get(iid, 0)}
        for iid in n_total_by_incident
    },
    "per_incident_hn_count": hn_df["parent_incident_id"].value_counts().to_dict(),
}
with open("data/processed/dataset_v0.7_stats.json", "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2, ensure_ascii=False)
