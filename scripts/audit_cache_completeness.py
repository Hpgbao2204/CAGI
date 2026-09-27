"""Ra soat he thong loi cache/pagination-incomplete (nhu da phat hien o
qbridge_qubit_2022, xem metadata/annotation_guide.md muc 13) cho 11
incident "primary" con lai. Voi tung dia chi (seed + frontier) cua tung
incident, re-fetch mang that voi cua so RONG HON 3 lan cua so goc (bao
phu ca truoc/sau), roi rebuild lai trajectory (do_collect=False, dung
cache moi) va so sanh voi golden fixture/du lieu processed hien tai.

Chay TUAN TU (khong song song) de kiem soat tai API, dung network that
(do_collect=True cho buoc re-fetch).
"""
import json
import time

import pandas as pd

from src.collect.etherscan_client import EtherscanClient
from src.collect.bsctrace_client import BscTraceClient
from src.pipeline.incident_pipeline import (
    BSC_CHAINS,
    RAW_DIR,
    REGISTRY_PATH,
    collect_address_raw_data,
    compute_end_block,
    expand_and_build_trajectory,
    run_incident_pipeline,
)
from src.trajectories.builder import load_trajectory_config

NULL_ADDR = "0x0000000000000000000000000000000000000000"

config = load_trajectory_config()
reg_df = pd.read_csv(REGISTRY_PATH)
reg_df = reg_df[reg_df["eval_tier"] == "primary"]
reg_df = reg_df[reg_df["incident_id"] != "qbridge_qubit_2022"]  # da fix roi

results = []

for _, row in reg_df.iterrows():
    incident_id = row["incident_id"]
    chain = row["chain_primary"]
    seed = row["seed_address"]
    start_block = int(row["start_block"])
    end_block = compute_end_block(chain, start_block, config)

    # 1. Lay danh sach dia chi processed HIEN TAI (khong goi mang)
    traj_before, _, processed = expand_and_build_trajectory(
        chain, seed, start_block, incident_id, int(row["label"]),
        config=config, do_collect=False, max_iterations=2,
    )
    n_before = len(traj_before)

    # 2. Widen cua so: rong gap 3 lan, can giua window goc
    window_size = end_block - start_block
    widened_start = max(0, start_block - window_size)
    widened_end = end_block + window_size

    print(f"=== {incident_id} ({chain}) === before n_actions={n_before}, "
          f"processed={len(processed)} addr, window goc [{start_block},{end_block}] "
          f"-> widen [{widened_start},{widened_end}]", flush=True)

    client = BscTraceClient(cache_dir=RAW_DIR) if chain in BSC_CHAINS else EtherscanClient(cache_dir=RAW_DIR)
    for addr in processed:
        if addr == NULL_ADDR:
            continue
        try:
            collect_address_raw_data(client, chain, addr, widened_start, widened_end)
            time.sleep(0.3)
        except Exception as exc:  # noqa: BLE001 - ghi nhan loi, khong dung ca script
            print(f"  LOI fetch {addr}: {exc}", flush=True)

    # 3. Rebuild lai (do_collect=False, dung cache moi da refresh)
    traj_after, _, processed_after = expand_and_build_trajectory(
        chain, seed, start_block, incident_id, int(row["label"]),
        config=config, do_collect=False, max_iterations=2,
    )
    n_after = len(traj_after)

    changed = n_after != n_before
    print(f"    -> after n_actions={n_after} {'*** DOI ***' if changed else '(khong doi)'}", flush=True)

    results.append({
        "incident_id": incident_id, "chain": chain,
        "n_actions_before": n_before, "n_actions_after": n_after,
        "changed": changed, "n_processed_before": len(processed),
        "n_processed_after": len(processed_after),
    })

print("\n=== TONG KET RA SOAT ===")
for r in results:
    print(r)

with open("data/processed/cache_audit_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

changed_incidents = [r["incident_id"] for r in results if r["changed"]]
print(f"\nSo incident co thay doi: {len(changed_incidents)} / {len(results)}")
if changed_incidents:
    print("Can dieu tra/rebuild lai:", changed_incidents)
