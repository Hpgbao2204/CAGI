"""Giai doan B, Buoc 2 (revisit) - mine hard-negative CHO INCIDENT MOI
radiant_capital_arbitrum_2024 (chua co hard-negative nao truoc do), dung
DUNG tieu chi da sua o Buoc 1 (band fan_out tuong doi qua compute_max_fan_out,
xem src/collect/hard_negative_miner.py) va do phuc tap (compute_min_candidate_events)
- GIU NGUYEN moi tieu chi khac (contract/mixer/volume) y het cac incident cu.

Ghi APPEND vao metadata/hard_negative_registry.csv (file CHINH, khong phai
file _v2_complexity rieng) vi day la lan mine DAU TIEN cho incident nay
(tuong duong vai tro voi 403 hard-negative cua 11 incident cu) - dung pandas
concat de KHONG ghi de 403 dong da co (write_hard_negative_registry() goc
ghi de toan bo file, khong dung truc tiep o day).
"""
from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from src.collect.hard_negative_miner import (
    HARD_NEGATIVE_REGISTRY_PATH,
    compute_max_fan_out,
    compute_min_candidate_events,
    load_known_malicious_addresses,
    mine_hard_negatives_for_incident,
)
from src.pipeline.incident_pipeline import REGISTRY_PATH, expand_and_build_trajectory
from src.trajectories.builder import load_trajectory_config

REPO_ROOT = Path(__file__).resolve().parents[1]
INCIDENT_ID = "radiant_capital_arbitrum_2024"
TARGET_COUNT = 25  # khop quy uoc target_per_incident da dung cho 11 incident cu (vong mine dau tien)
MAX_CANDIDATES_CHECKED = 150


def main():
    reg_df = pd.read_csv(REGISTRY_PATH)
    row = reg_df[reg_df["incident_id"] == INCIDENT_ID].iloc[0].to_dict()
    config = load_trajectory_config()

    traj, _, _ = expand_and_build_trajectory(
        row["chain_primary"], row["seed_address"], int(row["start_block"]),
        INCIDENT_ID, 1, config=config, do_collect=False, max_iterations=None,
    )
    pos_len = len(traj.actions)
    min_events = compute_min_candidate_events(pos_len)

    unique_dst = {a.dst for a in traj.actions}
    pos_fan_out = len(unique_dst)
    max_fo = compute_max_fan_out(pos_fan_out)

    print(f"=== Mining {INCIDENT_ID} ===")
    print(f"positive_len(actions)={pos_len} -> min_candidate_events={min_events}")
    print(f"positive_fan_out={pos_fan_out} -> max_fan_out (band Buoc 1)={max_fo} (nguong co dinh cu=3)")

    existing = pd.read_csv(HARD_NEGATIVE_REGISTRY_PATH)
    existing_addrs = {a.lower() for a in existing["seed_address"]}
    global_excluded = load_known_malicious_addresses() | existing_addrs

    report = mine_hard_negatives_for_incident(
        INCIDENT_ID, row, target_count=TARGET_COUNT,
        max_candidates_checked=MAX_CANDIDATES_CHECKED,
        excluded_addresses=global_excluded, do_collect=True,
        min_candidate_events=min_events, max_fan_out=max_fo,
    )

    n_insufficient = sum(1 for r in report.rejected if r.reject_reason == "insufficient_complexity_vs_positive")
    n_fanout = sum(1 for r in report.rejected if r.reject_reason == "fan_out_split_like_pattern")
    print(f"\naccepted={len(report.accepted)} checked={report.candidates_checked} rejected={len(report.rejected)}")
    print(f"  rejected_insufficient_complexity={n_insufficient}, rejected_fan_out_split_like_pattern={n_fanout}")
    for r in report.rejected:
        if r.reject_reason not in ("insufficient_complexity_vs_positive", "fan_out_split_like_pattern"):
            print(f"  rejected khac: {r.address} reason={r.reject_reason}")

    if not report.accepted:
        print("\n*** KHONG co candidate nao pass — khong ghi gi vao registry. ***")
        return

    start_idx = 0
    existing_ids = existing[existing["parent_incident_id"] == INCIDENT_ID]["hard_negative_id"]
    if len(existing_ids) > 0:
        start_idx = max(int(i.split("hn")[-1]) for i in existing_ids) + 1

    new_rows = []
    for i, result in enumerate(report.accepted):
        new_rows.append({
            "hard_negative_id": f"{INCIDENT_ID}__hn{start_idx + i:03d}",
            "parent_incident_id": INCIDENT_ID,
            "seed_address": result.address,
            "chain": result.chain,
            "start_block": result.block_number,
            "contract_used": result.contract_used,
            "protocol_name": result.protocol_name,
            "label": 0,
        })
    new_df = pd.DataFrame(new_rows)
    combined = pd.concat([existing, new_df], ignore_index=True)
    combined.to_csv(HARD_NEGATIVE_REGISTRY_PATH, index=False)
    print(f"\nDa APPEND {len(new_rows)} dong vao {HARD_NEGATIVE_REGISTRY_PATH} "
          f"(tong {len(combined)} dong, truoc do {len(existing)})")
    print(f"hard_negative_id moi: {[r['hard_negative_id'] for r in new_rows]}")


if __name__ == "__main__":
    main()
