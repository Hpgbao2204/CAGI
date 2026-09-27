"""Mining bổ sung có buffer cho 3 incident còn margin (Bước 3, phiên sửa lỗi
2026-08-13) — KHÔNG dồn thêm vào qbridge_qubit_2022/feg_bridge_2024 (đã hết
candidate ở max_candidates_checked=100 lần trước).
"""
import json
import time

from src.collect.hard_negative_miner import (
    load_known_malicious_addresses,
    mine_hard_negatives_for_incident,
    write_hard_negative_registry,
)
from src.pipeline.incident_pipeline import load_incident_row

# incident_id -> (target_count, max_candidates_checked)
PLAN = {
    "ronin_bridge_2022": (70, 150),
    "deltaprime_arbitrum_2024": (70, 150),
    "bsc_token_hub_2022": (70, 150),
    "qbridge_qubit_2022": (45, 100),  # KHONG doi - giu nguyen ket qua da max
    "feg_bridge_2024": (45, 100),  # KHONG doi - giu nguyen ket qua da max
}

# 3 address gay leak da phat hien va loai o vong QA truoc - loai tru ngay tu dau
KNOWN_LEAK_ADDRESSES = {
    "0x74de5d4fcbf63e00296fd95d33236b9794016631",
    "0x58f876857a02d6762e0101bb5c46a8c1ed44dc16",
    "0xb4a8d45647445ea9fc3e1058096142390683dbc2",
}

if __name__ == "__main__":
    global_excluded = load_known_malicious_addresses() | KNOWN_LEAK_ADDRESSES
    reports = {}
    summary = []

    for incident_id, (target, max_checked) in PLAN.items():
        row = load_incident_row(incident_id)
        t0 = time.time()
        print(f"=== Mining {incident_id} (target={target}, max_checked={max_checked}) ===", flush=True)
        report = mine_hard_negatives_for_incident(
            incident_id, row, target_count=target, max_candidates_checked=max_checked,
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

    write_hard_negative_registry(reports)

    total_accepted = sum(s["accepted"] for s in summary)
    print("\n=== TONG KET (RAW, chua tinh usable/leak) ===")
    for s in summary:
        print(s)
    print(f"\nTONG raw hard-negative moi: {total_accepted}")

    with open("data/processed/mining_summary_expand.json", "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "total_accepted": total_accepted}, f, indent=2)
