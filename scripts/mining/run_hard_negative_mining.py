"""Chạy mining hard-negative thật cho toàn bộ incident positive, lưu kết quả."""
import json
import time

from src.collect.hard_negative_miner import (
    INCIDENT_MINING_CONTRACTS,
    load_known_malicious_addresses,
    mine_hard_negatives_for_incident,
    write_hard_negative_registry,
)
from src.pipeline.incident_pipeline import load_incident_row

TARGET_PER_INCIDENT = 45
MAX_CANDIDATES_CHECKED = 100

if __name__ == "__main__":
    global_excluded = load_known_malicious_addresses()
    reports = {}
    summary = []

    for incident_id in INCIDENT_MINING_CONTRACTS:
        row = load_incident_row(incident_id)
        t0 = time.time()
        print(f"=== Mining {incident_id} ===", flush=True)
        report = mine_hard_negatives_for_incident(
            incident_id, row, target_count=TARGET_PER_INCIDENT,
            max_candidates_checked=MAX_CANDIDATES_CHECKED,
            excluded_addresses=global_excluded, do_collect=True,
        )
        elapsed = time.time() - t0
        reports[incident_id] = report
        global_excluded |= {r.address for r in report.accepted}
        print(f"{incident_id}: accepted={len(report.accepted)} checked={report.candidates_checked} "
              f"rejected={len(report.rejected)} elapsed={elapsed:.1f}s", flush=True)
        summary.append({
            "incident_id": incident_id, "accepted": len(report.accepted),
            "checked": report.candidates_checked, "rejected": len(report.rejected),
            "elapsed_sec": round(elapsed, 1),
        })

    write_hard_negative_registry(reports)

    total_accepted = sum(s["accepted"] for s in summary)
    print("\n=== TỔNG KẾT ===")
    for s in summary:
        print(s)
    print(f"\nTỔNG hard-negative mới đạt được: {total_accepted}")

    with open("data/processed/mining_summary.json", "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "total_accepted": total_accepted}, f, indent=2)
