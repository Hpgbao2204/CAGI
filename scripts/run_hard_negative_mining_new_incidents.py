"""Mining hard-negative cho 3 incident moi (Buoc 3, mo rong dataset len 8
incident 2026-08-14): chibi_finance_2023, wooppv2_2024, utopiasphere_2024.

Target 20-30/incident (chon 25), qua dung _passes_structural_filter, loai
tru TOAN BO dia chi da dung (seed/hard-negative cua 5 incident cu + 3
incident moi + known malicious). chibi_finance_2023/wooppv2_2024 dung CHUNG
1 mining contract (Stargate ETH Router, arbitrum) nen PHAI mine tuan tu
trong 1 lan chay voi excluded set tich luy de tranh trung dia chi giua 2
incident nay.
"""
import json
import time

import pandas as pd

from src.collect.hard_negative_miner import (
    load_known_malicious_addresses,
    mine_hard_negatives_for_incident,
    write_hard_negative_registry,
)
from src.pipeline.incident_pipeline import load_incident_row

NEW_INCIDENTS = ["chibi_finance_2023", "wooppv2_2024", "utopiasphere_2024"]
TARGET = 25
MAX_CHECKED = 100

if __name__ == "__main__":
    # Loai tru TOAN BO dia chi da dung: seed cua ca 8 incident (5 cu + 3 moi)
    # + hard-negative da mine cho 5 incident cu + known malicious.
    reg_df = pd.read_csv("metadata/incident_registry.csv")
    hn_df = pd.read_csv("metadata/hard_negative_registry.csv")
    global_excluded = (
        load_known_malicious_addresses()
        | set(reg_df["seed_address"].str.lower())
        | set(hn_df["seed_address"].str.lower())
    )

    # Giu nguyen 5 incident cu trong hard_negative_registry.csv, chi THEM
    # report cho 3 incident moi.
    existing_reports = {}
    for iid in hn_df["parent_incident_id"].unique():
        # tai tao lai object MiningResult-like tu dong dang csv de
        # write_hard_negative_registry ghi lai dung format cho 5 incident cu
        pass

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

    print("\n=== TONG KET mining 3 incident moi ===")
    for s in summary:
        print(s)
    total_accepted = sum(s["accepted"] for s in summary)
    print(f"\nTONG accepted moi: {total_accepted}")

    with open("data/processed/mining_summary_new_incidents.json", "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "total_accepted": total_accepted}, f, indent=2)

    # Ghi ra file RIENG (khong ghi de hard_negative_registry.csv chinh, vi
    # can merge voi 5 incident cu bang tay sau, giong pattern da dung o
    # scripts/run_hard_negative_remine_bsc_after_merge_fix.py).
    with open("data/processed/new_incidents_hn_reports.json", "w", encoding="utf-8") as f:
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
