"""Re-mine lại 2 incident BSC (qbridge_qubit_2022, bsc_token_hub_2022) sau khi
sửa bug merge_events_into_semantic_actions (representative-selection, xem
src/normalize/decoder.py, phát hiện 2026-08-13 khi verify lại positive
trajectory theo yêu cầu người dùng). Bug này ảnh hưởng _passes_structural_filter
(dùng chung load_events_for_addresses -> merge_events_into_semantic_actions)
nên TẬP hard-negative BSC đã chọn trước đó (95 dòng: qbridge=26, bsc_token_hub=69)
có thể sai (candidate lẽ ra pass lại bị reject và ngược lại) - cần chọn lại
từ đầu, KHÔNG chỉ rebuild trajectory của tập cũ.

KHÔNG đụng ronin_bridge_2022/deltaprime_arbitrum_2024/feg_bridge_2024 (ETH/
Arbitrum, ngoài phạm vi bug BSC-specific đang xử lý).

do_collect=False trước (dùng cache đã có từ 3 vòng mining trước) - nếu không
đủ candidate mới mở do_collect=True (gọi mạng thật).
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

KNOWN_LEAK_ADDRESSES = {
    "0x74de5d4fcbf63e00296fd95d33236b9794016631",
    "0x58f876857a02d6762e0101bb5c46a8c1ed44dc16",
    "0xb4a8d45647445ea9fc3e1058096142390683dbc2",
}

# target/max_checked = tổng đích cuối cùng đã đạt trước đó cho từng incident
# (qbridge: 45 target/100 checked ở vòng đầu, giữ nguyên vì "đã hết candidate";
#  bsc_token_hub: 70 target/150 checked ở vòng mở rộng) - re-mine lại từ đầu
# với đúng độ sâu đã dùng, KHÔNG nới thêm, để so sánh công bằng trước/sau fix.
PLAN = {
    "qbridge_qubit_2022": (45, 100),
    "bsc_token_hub_2022": (70, 150),
}

if __name__ == "__main__":
    other_df = pd.read_csv("metadata/hard_negative_registry.csv")
    other_addresses = set(
        other_df[~other_df["parent_incident_id"].isin(PLAN.keys())]["seed_address"].str.lower()
    )
    reg_df = pd.read_csv("metadata/incident_registry.csv")
    control_seed_addresses = set(reg_df["seed_address"].str.lower())  # tránh chọn trùng control gốc

    global_excluded = (
        load_known_malicious_addresses() | KNOWN_LEAK_ADDRESSES | other_addresses | control_seed_addresses
    )
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
    print("\n=== TONG KET remine (do_collect=False, dung cache) ===")
    for s in summary:
        print(s)
    print(f"\nTONG accepted moi (2 incident BSC): {total_accepted}")

    with open("data/processed/remine_bsc_summary.json", "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "total_accepted": total_accepted}, f, indent=2)

    # LƯU Ý: chưa ghi đè hard_negative_registry.csv ở đây - chỉ in kết quả để
    # so sánh, script khác sẽ merge với 170 dòng ronin/deltaprime/feg giữ nguyên
    # sau khi xác nhận kết quả hợp lý.
    with open("data/processed/remine_bsc_reports.json", "w", encoding="utf-8") as f:
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
