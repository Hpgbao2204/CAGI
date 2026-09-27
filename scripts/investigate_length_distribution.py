"""Buoc 1 (dot 2, sua shortcut) - dieu tra chi tiet phan phoi do dai
trajectory theo TUNG group rieng (khong gop chung 408 hard-negative), de
xac nhan do dai hard-negative thap DONG DEU o moi incident hay chi vai
nhom keo trung vi xuong."""
from __future__ import annotations

import statistics
from collections import defaultdict

from src.pipeline.dataset_builder import load_rq1_trajectories


def _stats(lens):
    if not lens:
        return "n=0"
    s = sorted(lens)
    n = len(s)
    med = statistics.median(s)
    q1 = s[max(0, n // 4)]
    q3 = s[min(n - 1, (3 * n) // 4)]
    return f"n={n:3d} median={med:5.1f} IQR=[{q1},{q3}] min={min(s)} max={max(s)}"


def main():
    items = load_rq1_trajectories(verbose=False)
    by_group = defaultdict(lambda: {"pos": [], "neg_control": [], "neg_mined": []})
    for i in items:
        key = "pos" if i.kind == "positive" else ("neg_control" if i.kind == "hard_negative_control" else "neg_mined")
        by_group[i.group_id][key].append(len(i.trajectory))

    print(f"{'group_id':32s} {'positive':10s} | {'neg_control':10s} | neg_mined")
    print("=" * 120)
    for gid in sorted(by_group):
        d = by_group[gid]
        pos_len = d["pos"][0] if d["pos"] else "-"
        ctrl_len = d["neg_control"][0] if d["neg_control"] else "-"
        print(f"{gid:32s} len={pos_len!s:6s} | ctrl_len={ctrl_len!s:6s} | mined: {_stats(d['neg_mined'])}")

    print("\n=== Ty le mined hard-negative NGAN HON RAT NHIEU so voi positive tuong ung ===")
    print(f"{'group_id':32s} {'pos_len':>8s} {'mined_median':>13s} {'ratio (pos/mined_median)':>26s}")
    for gid in sorted(by_group):
        d = by_group[gid]
        pos_len = d["pos"][0] if d["pos"] else None
        mined = d["neg_mined"]
        if pos_len and mined:
            med = statistics.median(mined)
            ratio = pos_len / med if med > 0 else float("inf")
            flag = " <<<< " if ratio > 5 else ""
            print(f"{gid:32s} {pos_len:8d} {med:13.1f} {ratio:26.1f}{flag}")

    all_mined = [len(i.trajectory) for i in items if i.kind == "hard_negative_mined"]
    print(f"\nTOM TAT tat ca 403 mined hard-negative (gop): {_stats(all_mined)}")
    n_len1 = sum(1 for x in all_mined if x == 1)
    print(f"So mined hard-negative co DUNG 1 action: {n_len1}/{len(all_mined)} ({100*n_len1/len(all_mined):.1f}%)")


if __name__ == "__main__":
    main()
