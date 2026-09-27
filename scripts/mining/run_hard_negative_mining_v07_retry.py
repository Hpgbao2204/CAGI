"""Retry mining cho wault_finance_2021/circulate_2023 sau khi them
PancakeSwap V2 lam nguon fallback (contract goc het candidate, checked=0
o lan chay dau)."""
import json
import time

import pandas as pd

from src.collect.hard_negative_miner import (
    load_known_malicious_addresses,
    mine_hard_negatives_for_incident,
)
from src.pipeline.incident_pipeline import load_incident_row

INCIDENTS = ["wault_finance_2021", "circulate_2023"]
TARGET = 22
MAX_CHECKED = 100

if __name__ == "__main__":
    reg_df = pd.read_csv("metadata/incident_registry.csv")
    hn_df = pd.read_csv("metadata/hard_negative_registry.csv")
    with open("data/processed/v07_new_incidents_hn_reports.json", encoding="utf-8") as f:
        prior = json.load(f)
    prior_addrs = {r["address"].lower() for lst in prior.values() for r in lst}

    global_excluded = (
        load_known_malicious_addresses()
        | set(reg_df["seed_address"].str.lower())
        | set(hn_df["seed_address"].str.lower())
        | prior_addrs
    )

    reports = {}
    summary = []
    for incident_id in INCIDENTS:
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

        # Ghi NGAY sau moi incident (khong doi den cuoi) - tranh mat ket qua
        # neu incident sau bi loi (bug thuc gap: BSCTrace API het retry giua
        # chung, lam mat ket qua incident truoc do vi file JSON chi ghi 1
        # lan cuoi cung).
        with open("data/processed/v07_retry_hn_reports.json", "w", encoding="utf-8") as f:
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

    print("\n=== TONG KET retry mining ===")
    for s in summary:
        print(s)
