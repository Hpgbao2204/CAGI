"""Mining hard-negative cho 4 incident moi (Buoc 3, mo rong dataset len 12
incident 2026-08-14): xkingdom_2024, wault_finance_2021, paraluni_2022,
circulate_2023.

Target 20-25/incident (chon 22), qua dung _passes_structural_filter, loai
tru TOAN BO dia chi da dung (seed/hard-negative cua 8 incident cu + 4
incident moi + known malicious).
"""
import json
import time

import pandas as pd

from src.collect.hard_negative_miner import (
    load_known_malicious_addresses,
    mine_hard_negatives_for_incident,
)
from src.pipeline.incident_pipeline import load_incident_row

NEW_INCIDENTS = ["xkingdom_2024", "wault_finance_2021", "paraluni_2022", "circulate_2023"]
TARGET = 22
MAX_CHECKED = 100

if __name__ == "__main__":
    reg_df = pd.read_csv("metadata/incident_registry.csv")
    hn_df = pd.read_csv("metadata/hard_negative_registry.csv")
    global_excluded = (
        load_known_malicious_addresses()
        | set(reg_df["seed_address"].str.lower())
        | set(hn_df["seed_address"].str.lower())
    )

    reports = {}
    summary = []
    for incident_id in NEW_INCIDENTS:
        row = load_incident_row(incident_id)
        t0 = time.time()
        print(f"=== Mining {incident_id} (target={TARGET}, max_checked={MAX_CHECKED}) ===", flush=True)
        report = mine_hard_negatives_for_incident(
            incident_id, row, target_count=TARGET, max_candidates_checked=MAX_CHECKED,
            excluded_addresses=global_excluded, do_collect=True,
        )
        elapsed = time.time() - t0
        reports[incident_id] = report
        global_excluded |= {r.address for r in report.accepted}
        print(f"{incident_id}: accepted={len(report.accepted)} checked={report.candidates_checked} "
              f"rejected={len(report.rejected)} elapsed={elapsed:.1f}s", flush=True)
        summary.append({
            "incident_id": incident_id, "accepted": len(report.accepted),
            "checked": report.candidates_checked, "elapsed_sec": round(elapsed, 1),
        })

    print("\n=== TONG KET mining 4 incident moi ===")
    for s in summary:
        print(s)
    total_accepted = sum(s["accepted"] for s in summary)
    print(f"\nTONG accepted moi: {total_accepted}")

    with open("data/processed/mining_summary_v07_new_incidents.json", "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "total_accepted": total_accepted}, f, indent=2)

    with open("data/processed/v07_new_incidents_hn_reports.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                iid: [
                    {"address": r.address, "chain": r.chain, "block_number": r.block_number,
                     "contract_used": r.contract_used, "protocol_name": r.protocol_name}
                    for r in rep.accepted
                ]
                for iid, rep in reports.items()
            },
            f, indent=2,
        )
