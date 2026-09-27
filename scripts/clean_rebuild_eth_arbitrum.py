"""Xoa sach cache raw (ca file cu lan file widen do audit_cache_completeness.py
tao ra) cho TAT CA dia chi lien quan toi cac incident chain eth/arbitrum trong
eval_tier=primary, roi fetch lai SACH 1 lan duy nhat dung window goc cua tung
incident (khong widen). Muc dich: loai bo hoan toan tinh trang 2 file cache
chong lan gay sai merge classification (xem annotation_guide.md muc 14).

Chay TUAN TU, dung network that.
"""
import shutil
import time

import pandas as pd

from src.pipeline.incident_pipeline import (
    RAW_DIR, REGISTRY_PATH, expand_and_build_trajectory, run_incident_pipeline,
)
from src.trajectories.builder import load_trajectory_config

config = load_trajectory_config()
reg_df = pd.read_csv(REGISTRY_PATH)
reg_df = reg_df[reg_df["eval_tier"] == "primary"]
reg_df = reg_df[reg_df["chain_primary"].isin(["eth", "arbitrum"])]

results = []
for _, row in reg_df.iterrows():
    incident_id = row["incident_id"]
    chain = row["chain_primary"]
    seed = row["seed_address"]
    start_block = int(row["start_block"])

    # 1. Discover superset dia chi hien co (dung cache CU/nhiem ban de biet
    #    frontier toi da tung duoc kham pha, phuc vu xoa dung cho).
    _, _, processed_dirty = expand_and_build_trajectory(
        chain, seed, start_block, incident_id, int(row["label"]),
        config=config, do_collect=False, max_iterations=2,
    )
    NULL_ADDR = "0x0000000000000000000000000000000000000000"
    for addr in processed_dirty:
        if addr == NULL_ADDR:
            continue
        d = RAW_DIR / chain / addr.lower()
        if d.exists():
            shutil.rmtree(d)

    print(f"=== {incident_id} ({chain}) === da xoa cache cua {len(processed_dirty)} dia chi, fetch lai sach...", flush=True)

    # 2. Fetch lai SACH tu dau (do_collect=True, dung window goc, khong widen).
    traj, _, processed_clean = expand_and_build_trajectory(
        chain, seed, start_block, incident_id, int(row["label"]),
        config=config, do_collect=True, max_iterations=None,
    )
    n_actions = len(traj.actions)
    print(f"    -> n_actions (sach) = {n_actions}, processed = {len(processed_clean)} dia chi", flush=True)

    results.append({
        "incident_id": incident_id, "chain": chain,
        "n_actions_clean": n_actions, "n_processed_clean": len(processed_clean),
    })
    time.sleep(0.5)

print("\n=== TONG KET CLEAN REBUILD (eth/arbitrum) ===")
for r in results:
    print(r)

import json
with open("data/processed/clean_rebuild_eth_arbitrum_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)
