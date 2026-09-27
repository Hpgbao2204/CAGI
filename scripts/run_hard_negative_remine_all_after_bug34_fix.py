"""Re-mine lại TOÀN BỘ 5 incident sau khi sửa bug #3 (pre-merge dedup +
tokentx null logIndex) và bug #4 (swap chỉ hợp lệ khi có self-referencing
address, không nhầm 'merge' 2-token thành 'swap') — 2026-08-13. Cả 2 bug
đều nằm trong merge_events_into_semantic_actions/decode_tokentx_row, dùng
chung bởi _passes_structural_filter (qua load_events_for_addresses) trên
MỌI chain (eth/bsc/arbitrum), không chỉ BSC như bug #2 — nên phải re-mine
TẤT CẢ 5 incident, không chỉ 2 incident BSC như lần trước.

do_collect=False (chỉ dùng cache đã có, không gọi mạng mới) — nếu không đủ
candidate mới xem xét do_collect=True riêng.
"""
import json
import time

from src.collect.hard_negative_miner import (
    load_known_malicious_addresses,
    mine_hard_negatives_for_incident,
    write_hard_negative_registry,
)
from src.pipeline.incident_pipeline import load_incident_row

KNOWN_LEAK_ADDRESSES = {
    "0x74de5d4fcbf63e00296fd95d33236b9794016631",
    "0x58f876857a02d6762e0101bb5c46a8c1ed44dc16",
    "0xb4a8d45647445ea9fc3e1058096142390683dbc2",
}

# target/max_checked = đúng giá trị đã dùng để đạt tập hard-negative cuối
# cùng hiện tại (metadata/hard_negative_registry.csv), giữ nguyên để so
# sánh công bằng trước/sau fix, KHÔNG nới lỏng/mở rộng gì thêm.
PLAN = {
    "ronin_bridge_2022": (70, 150),
    "deltaprime_arbitrum_2024": (70, 150),
    "bsc_token_hub_2022": (70, 150),
    "qbridge_qubit_2022": (45, 100),
    "feg_bridge_2024": (45, 100),
}

if __name__ == "__main__":
    global_excluded = load_known_malicious_addresses() | KNOWN_LEAK_ADDRESSES
    reports = {}
    summary = []

    for incident_id, (target, max_checked) in PLAN.items():
        row = load_incident_row(incident_id)
        t0 = time.time()
        print(f"=== Re-mine {incident_id} (target={target}, max_checked={max_checked}, do_collect=False) ===", flush=True)
        report = mine_hard_negatives_for_incident(
            incident_id, row, target_count=target, max_candidates_checked=max_checked,
            excluded_addresses=global_excluded, do_collect=False,
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

    total_accepted = sum(s["accepted"] for s in summary)
    print("\n=== TONG KET remine-all (do_collect=False, dung cache) ===")
    for s in summary:
        print(s)
    print(f"\nTONG accepted moi (5 incident): {total_accepted}")

    write_hard_negative_registry(reports)

    with open("data/processed/remine_all_bug34_summary.json", "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "total_accepted": total_accepted}, f, indent=2)
