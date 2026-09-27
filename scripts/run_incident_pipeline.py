"""
CLI tổng quát: chạy pipeline collect -> decode -> build trajectory cho 1
incident_id đọc từ metadata/incident_registry.csv. Thay thế
scripts/build_trajectory_from_raw.py (bản pilot hardcode Ronin Bridge).

Usage:
    python scripts/run_incident_pipeline.py --incident-id ronin_bridge_2022
    python scripts/run_incident_pipeline.py --incident-id ronin_bridge_2022 --no-collect  # chỉ dùng cache, không gọi mạng
"""
from __future__ import annotations

import argparse

from src.normalize.decoder import (
    build_verified_bridge_address_index,
    build_verified_mixer_address_index,
    load_protocol_map,
)
from src.pipeline.incident_pipeline import (
    compute_end_block,
    find_swap_evidence,
    load_incident_row,
    run_incident_pipeline,
)
from src.trajectories.builder import load_trajectory_config


def summarize(traj, provenance_events, processed, swap_evidence) -> None:
    print(f"trajectory_id={traj.trajectory_id} seed={traj.seed_address} n_actions={len(traj)}")
    print(f"addresses đã xử lý (frontier expansion): {len(processed)} -> {processed}")
    print(f"bridge_links (confidence>0): {len(traj.bridge_links)}")
    for link in traj.bridge_links:
        print(f"  deposit_key={link.deposit_key} withdraw_key={link.withdraw_key} "
              f"confidence={link.confidence} evidence={link.evidence}")

    print("\nActions theo thời gian:")
    for i, a in enumerate(traj.actions):
        print(f"  [{i}] {a.timestamp.isoformat()} {a.event_type:16s} {a.src[:10]}->{a.dst[:10]} "
              f"amount_norm={a.amount_norm:.4f} token={a.token} protocol={a.protocol} tx={a.tx_hash[:12]}")

    bridge_events = [a for a in traj.actions if a.event_type in ("bridge_deposit", "bridge_withdraw")]
    swap_events = [a for a in traj.actions if a.event_type == "swap"]
    print(
        f"\nGate check: provenance bridge event thật = {len(provenance_events)}, "
        f"outbound bridge event trong trajectory = {len(bridge_events)}, "
        f"swap/DEX event trong trajectory = {len(swap_events)}, "
        f"swap evidence NGOÀI trajectory (inbound) = {len(swap_evidence)}"
    )
    print("  (swap evidence ngoài trajectory = DEX event thật nhưng src không nằm trong node_depth "
          "của builder forward-only, vd LP pool -> ví — vẫn là bằng chứng DEX thật, không ép vào trajectory)")
    for ev in provenance_events:
        print(f"  PROVENANCE BRIDGE: tx={ev.tx_hash} amount(log)={ev.amount_norm:.4f} token={ev.token} "
              f"protocol={ev.protocol or '(chưa gắn nhãn protocol)'}")
    for ev in bridge_events:
        print(f"  OUTBOUND BRIDGE: tx={ev.tx_hash} protocol={ev.protocol} {ev.event_type}")
    for ev in swap_events:
        print(f"  SWAP (trajectory): tx={ev.tx_hash} {ev.src[:10]}->{ev.dst[:10]}")
    for ev in swap_evidence[:10]:
        print(f"  SWAP (evidence, ngoài trajectory): tx={ev.tx_hash} {ev.src[:10]}->{ev.dst[:10]} token={ev.token}")
    if len(swap_evidence) > 10:
        print(f"  ... và {len(swap_evidence) - 10} swap evidence khác")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--incident-id", required=True)
    parser.add_argument("--no-collect", action="store_true", help="Không gọi mạng, chỉ dùng cache data/raw/ đã có")
    parser.add_argument("--max-iterations", type=int, default=None)
    args = parser.parse_args()

    traj, provenance_events, processed = run_incident_pipeline(
        args.incident_id, do_collect=not args.no_collect, max_iterations=args.max_iterations
    )

    # swap evidence (bổ sung, không ép vào trajectory) — tính riêng vì
    # run_incident_pipeline() không trả trực tiếp để tránh đổi signature ảnh
    # hưởng các nơi gọi khác (xem src/pipeline/incident_pipeline.py).
    row = load_incident_row(args.incident_id)
    config = load_trajectory_config()
    end_block = compute_end_block(row["chain_primary"], int(row["start_block"]), config)
    protocol_map = load_protocol_map()
    bridge_index = build_verified_bridge_address_index(protocol_map)
    mixer_index = build_verified_mixer_address_index(protocol_map)
    swap_evidence = find_swap_evidence(
        row["chain_primary"], processed, args.incident_id, int(row["start_block"]), end_block, bridge_index, mixer_index
    )

    summarize(traj, provenance_events, processed, swap_evidence)


if __name__ == "__main__":
    main()
