"""Tuan 8 Buoc 1 - kiem tra data gate RQ3 (next-event prediction, optional)
dung DUNG tieu chi trong research_questions.md muc "RQ3":
  >= 1,000 action transition; moi next-action class >= 30 mau; majority
  class < 60%.

Khong goi API on-chain moi - dung lai chinh xac tap trajectory da build
san (cache local) ma features_v2.parquet/RQ2 dang dung
(load_rq1_trajectories(include_v2_complexity=True) - 525 trajectory:
11 positive + 5 control + 403 hard-negative + 106 hard-negative bo sung
do phuc tap).

Dinh nghia (khop dung "next-event prediction" trong RQ3): 1 "action
transition" = 1 cap hanh dong LIEN TIEP (action[i], action[i+1]) trong
CUNG 1 trajectory, sap theo thoi gian (dung thu tu da co trong
Trajectory.actions - xem src/trajectories/builder.py). "next-action
class" = event_type cua action[i+1] (nhan can du doan, cho truoc
event_type cua action[i]).

Dem tren TOAN BO 525 trajectory (khop dung tap RQ2 dang dung, khong rieng
positive) - vi RQ3 la next-event prediction TONG QUAT (mo hinh chuoi hanh
dong, khong gan voi nhan positive/negative) dung lam tin hieu bo sung cho
alert, khop tinh than "dung ban RQ2 - theo bucket rieng biet, khong pool"
(RQ2 cung dung toan bo 525 trajectory, khac RQ1 chi dung 11 incident khi
tinh scale khac). De minh bach, van in RIENG so lieu neu CHI tinh tren 11
positive (tham khao, khong dung de quyet dinh gate) - xem phan cuoi.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import pandas as pd

from src.pipeline.dataset_builder import load_rq1_trajectories

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_CSV = REPO_ROOT / "results" / "tables" / "rq3_data_gate_check.csv"
OUT_MD = REPO_ROOT / "results" / "reports" / "rq3_data_gate_v1.md"

GATE_MIN_TRANSITIONS = 1000
GATE_MIN_PER_CLASS = 30
GATE_MAX_MAJORITY_RATIO = 0.60


def count_transitions(items):
    """Tra ve (tong so transition, Counter next-action class, so trajectory
    dung duoc (>=2 action - trajectory 0-1 action khong co transition nao))."""
    next_class_counter = Counter()
    n_traj_with_transitions = 0
    n_traj_too_short = 0
    for item in items:
        actions = item.trajectory.actions
        if len(actions) < 2:
            n_traj_too_short += 1
            continue
        n_traj_with_transitions += 1
        for i in range(len(actions) - 1):
            next_class_counter[actions[i + 1].event_type] += 1
    total = sum(next_class_counter.values())
    return total, next_class_counter, n_traj_with_transitions, n_traj_too_short


def main():
    print("=== Nap toan bo trajectory (khop dung tap RQ2 dang dung, cache local) ===", flush=True)
    items = load_rq1_trajectories(verbose=False, include_v2_complexity=True)
    n_pos = sum(1 for i in items if i.label == 1)
    n_neg = sum(1 for i in items if i.label == 0)
    print(f"Tong {len(items)} trajectory (positive={n_pos}, negative={n_neg})", flush=True)

    print("\n=== Dem tren TOAN BO trajectory (chinh thuc, dung de quyet dinh gate) ===", flush=True)
    total, counter, n_with, n_short = count_transitions(items)
    print(f"Tong so action transition: {total}")
    print(f"So trajectory co >=2 action (dong gop transition): {n_with}")
    print(f"So trajectory qua ngan (<2 action, khong co transition): {n_short}")

    class_table = pd.DataFrame(
        sorted(counter.items(), key=lambda kv: -kv[1]), columns=["next_action_class", "n_samples"],
    )
    class_table["ratio"] = class_table["n_samples"] / total
    print("\nPhan phoi next-action class:")
    print(class_table.to_string(index=False))

    majority_class = class_table.iloc[0]["next_action_class"]
    majority_ratio = float(class_table.iloc[0]["ratio"])
    min_class_count = int(class_table["n_samples"].min())
    n_classes_below_30 = int((class_table["n_samples"] < GATE_MIN_PER_CLASS).sum())

    gate_transitions = total >= GATE_MIN_TRANSITIONS
    gate_min_class = n_classes_below_30 == 0
    gate_majority = majority_ratio < GATE_MAX_MAJORITY_RATIO
    gate_pass = gate_transitions and gate_min_class and gate_majority

    print(f"\n=== KIEM TRA DATA GATE (research_questions.md muc RQ3) ===")
    print(f"[{'PASS' if gate_transitions else 'FAIL'}] Tong transition >= {GATE_MIN_TRANSITIONS}: {total}")
    print(f"[{'PASS' if gate_min_class else 'FAIL'}] Moi class >= {GATE_MIN_PER_CLASS} mau: "
          f"min={min_class_count}, so class duoi nguong={n_classes_below_30}/{len(class_table)}")
    print(f"[{'PASS' if gate_majority else 'FAIL'}] Majority class < {GATE_MAX_MAJORITY_RATIO*100:.0f}%: "
          f"'{majority_class}' = {majority_ratio*100:.2f}%")
    print(f"\n=== KET LUAN GATE: {'DAT' if gate_pass else 'KHONG DAT'} ===")

    # --- Tham khao (KHONG dung de quyet dinh gate): chi 11 positive incident ---
    print("\n=== (Tham khao, KHONG dung quyet dinh) Chi 11 positive incident ===")
    pos_items = [i for i in items if i.label == 1]
    total_pos, counter_pos, n_with_pos, n_short_pos = count_transitions(pos_items)
    print(f"Tong transition (chi positive): {total_pos}")
    if total_pos:
        class_table_pos = pd.DataFrame(
            sorted(counter_pos.items(), key=lambda kv: -kv[1]), columns=["next_action_class", "n_samples"],
        )
        maj_pos = class_table_pos.iloc[0]
        print(f"Majority class (chi positive): '{maj_pos['next_action_class']}' = "
              f"{maj_pos['n_samples']/total_pos*100:.2f}%")

    class_table.to_csv(OUT_CSV, index=False)
    print(f"\nDa luu {OUT_CSV}")

    md = [
        "# RQ3 — Kiểm tra data gate (Tuần 8, Bước 1)\n",
        "\nTiêu chí (đúng `research_questions.md` mục RQ3): **≥1,000 action "
        "transition; mỗi next-action class ≥30 mẫu; majority class <60%.**\n",
        "\nĐịnh nghĩa: 1 transition = 1 cặp hành động liên tiếp `(action[i], action[i+1])` "
        "trong cùng 1 trajectory; next-action class = `event_type` của `action[i+1]`. "
        f"Đếm trên **toàn bộ {len(items)} trajectory** ({n_pos} positive + {n_neg} negative "
        "— control gốc + hard-negative mining + hard-negative bổ sung độ phức tạp) — cùng tập "
        "trajectory mà RQ2 dùng (features_v2.parquet đã sửa bug prefix), vì next-event "
        "prediction là mô hình chuỗi hành động tổng quát, không gắn riêng nhãn positive/negative.\n",
        f"\n- Tổng trajectory: {len(items)} (positive={n_pos}, negative={n_neg})\n",
        f"- Trajectory có ≥2 action (đóng góp transition): {n_with}\n",
        f"- Trajectory quá ngắn (<2 action, không có transition nào): {n_short}\n",
        "\n## Kết quả đếm\n",
        f"\n- **Tổng số action transition: {total}**\n",
        f"- Số next-action class: {len(class_table)}\n",
        "\n| next_action_class | n_samples | ratio |\n|---|---|---|\n",
    ]
    for _, r in class_table.iterrows():
        md.append(f"| {r['next_action_class']} | {int(r['n_samples'])} | {r['ratio']*100:.2f}% |\n")

    md += [
        "\n## Kiểm tra từng tiêu chí\n",
        f"\n| Tiêu chí | Ngưỡng | Giá trị thật | Đạt? |\n|---|---|---|---|\n",
        f"| Tổng transition | ≥{GATE_MIN_TRANSITIONS} | {total} | {'✅ ĐẠT' if gate_transitions else '❌ KHÔNG ĐẠT'} |\n",
        f"| Mỗi class ≥{GATE_MIN_PER_CLASS} mẫu | 0 class dưới ngưỡng | "
        f"min={min_class_count}, {n_classes_below_30}/{len(class_table)} class dưới ngưỡng | "
        f"{'✅ ĐẠT' if gate_min_class else '❌ KHÔNG ĐẠT'} |\n",
        f"| Majority class | <{GATE_MAX_MAJORITY_RATIO*100:.0f}% | "
        f"'{majority_class}' = {majority_ratio*100:.2f}% | {'✅ ĐẠT' if gate_majority else '❌ KHÔNG ĐẠT'} |\n",
        f"\n## KẾT LUẬN: {'ĐẠT GATE — triển khai RQ3' if gate_pass else 'KHÔNG ĐẠT GATE — loại RQ3 khỏi paper chính thức'}\n",
    ]
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("".join(md), encoding="utf-8")
    print(f"Da luu {OUT_MD}")

    return gate_pass


if __name__ == "__main__":
    main()
