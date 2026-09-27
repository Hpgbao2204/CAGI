"""
Xây dựng danh sách trajectory THẬT (không synthetic) cho tập RQ1 chính (11
incident positive, KHÔNG bao gồm circulate_2023 — eval_tier=auxiliary_low_
evidence, xem data/dataset_card.md mục "Eval tier").

group_id đọc TRỰC TIẾP từ metadata/split_manifest.json (nguồn xác thực duy
nhất cho group membership — không tự suy luận lại) — mỗi group gồm: 1
positive incident + 1 hard-negative control gốc (cùng câu chuyện incident,
KHÔNG phải trajectory riêng) + N hard-negative đã mine, group theo
parent_incident_id.

do_collect=False (chỉ dùng cache đã có, không gọi mạng) — dùng cho
EDA/feature-building/baseline, không phải bước crawl dữ liệu mới.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import pandas as pd

from src.collect.hard_negative_miner import HARD_NEGATIVE_REGISTRY_PATH
from src.pipeline.incident_pipeline import REGISTRY_PATH, expand_and_build_trajectory
from src.trajectories.builder import Trajectory, TrajectoryConfig, load_trajectory_config

REPO_ROOT = Path(__file__).resolve().parents[2]
SPLIT_MANIFEST_PATH = REPO_ROOT / "metadata" / "split_manifest.json"
HARD_NEGATIVE_REGISTRY_V2_COMPLEXITY_PATH = REPO_ROOT / "metadata" / "hard_negative_registry_v2_complexity.csv"

AUXILIARY_INCIDENT_IDS = {"circulate_2023"}  # eval_tier=auxiliary_low_evidence, ngoài RQ1 chính
# new_free_dao_2022 KHONG con trong tap nay - nang len primary sau khi phat
# hien TornadoProxyLight (BSC mixer, 2026-08-28) khien trajectory co 12
# action mixer_or_exit that (khop bao cao cong khai), khong con la "toan
# transfer, khong evidence phan biet" nhu luc dau.


@dataclass
class DatasetItem:
    trajectory: Trajectory
    group_id: str  # đọc từ split_manifest.json — dùng cho GroupKFold/leave-one-group-out
    label: int
    chain: str
    kind: str  # "positive" | "hard_negative_control" | "hard_negative_mined"
    source_id: str  # incident_id hoặc hard_negative_id gốc (để truy vết)


def _load_group_membership() -> dict:
    """Trả về map: source_id (incident_id/hard_negative_id) -> group_id,
    CHỈ cho các group role=primary (loại circulate_2023's group nếu có)."""
    manifest = json.loads(SPLIT_MANIFEST_PATH.read_text(encoding="utf-8"))
    mapping: dict = {}
    for g in manifest["groups"]:
        if g.get("role") != "primary":
            continue
        group_id = g["group_id"]
        members = g["members"]
        mapping[members["positive_incident_id"]] = group_id
        if members.get("original_hard_negative_control_id"):
            mapping[members["original_hard_negative_control_id"]] = group_id
        for hn_id in members.get("mined_hard_negative_ids", []):
            mapping[hn_id] = group_id
    return mapping


def load_rq1_trajectories(
    config: Optional[TrajectoryConfig] = None,
    max_iterations_positive: Optional[int] = None,
    max_iterations_negative: int = 2,
    verbose: bool = False,
    include_v2_complexity: bool = False,
) -> List[DatasetItem]:
    """Build TOÀN BỘ trajectory thật cho tập RQ1 chính:
    - 11 positive incident (eval_tier=primary, label=1)
    - 5 hard-negative control gốc (eval_tier=primary, label=0)
    - toàn bộ hard-negative đã mine với parent_incident_id != circulate_2023

    max_iterations_positive=None -> dùng config.max_depth (mặc định chính
    thức, khớp golden fixture). max_iterations_negative=2 -> khớp quy ước
    đã dùng xuyên suốt dự án cho rebuild hard-negative (xem
    scripts/compute_dataset_v0.9_stats.py).

    include_v2_complexity=True: thêm CẢ hard-negative mine bổ sung theo
    tiêu chí độ phức tạp (Tuần 5, sửa shortcut độ dài — xem
    metadata/hard_negative_registry_v2_complexity.csv), kind đánh dấu riêng
    "hard_negative_mined_v2_complexity" để truy vết. Mặc định False để
    không đổi hành vi của các script/test đã dùng hàm này trước đây.
    """
    if config is None:
        config = load_trajectory_config()
    group_of = _load_group_membership()

    items: List[DatasetItem] = []

    reg_df = pd.read_csv(REGISTRY_PATH)
    reg_df = reg_df[reg_df["eval_tier"] == "primary"]
    for _, row in reg_df.iterrows():
        incident_id = row["incident_id"]
        traj, _, _ = expand_and_build_trajectory(
            row["chain_primary"], row["seed_address"], int(row["start_block"]),
            incident_id, int(row["label"]), config=config, do_collect=False,
            max_iterations=max_iterations_positive,
        )
        kind = "positive" if int(row["label"]) == 1 else "hard_negative_control"
        items.append(DatasetItem(
            trajectory=traj, group_id=group_of[incident_id], label=int(row["label"]),
            chain=row["chain_primary"], kind=kind, source_id=incident_id,
        ))
        if verbose:
            print(f"[{kind}] {incident_id}: n_actions={len(traj.actions)}", flush=True)

    def _load_mined(path: Path, kind: str) -> int:
        if not path.exists():
            return 0
        hn_df = pd.read_csv(path)
        hn_df = hn_df[~hn_df["parent_incident_id"].isin(AUXILIARY_INCIDENT_IDS)]
        n_empty = 0
        for _, row in hn_df.iterrows():
            hn_id = row["hard_negative_id"]
            parent = row["parent_incident_id"]
            traj, _, _ = expand_and_build_trajectory(
                row["chain"], row["seed_address"], int(row["start_block"]),
                parent, 0, config=config, do_collect=False,
                max_iterations=max_iterations_negative,
            )
            if len(traj) == 0:
                n_empty += 1
                continue
            items.append(DatasetItem(
                trajectory=traj, group_id=group_of[hn_id], label=0,
                chain=row["chain"], kind=kind, source_id=hn_id,
            ))
        if verbose:
            print(f"[{kind}] {len(hn_df) - n_empty}/{len(hn_df)} usable (rỗng: {n_empty})", flush=True)
        return len(hn_df)

    _load_mined(HARD_NEGATIVE_REGISTRY_PATH, "hard_negative_mined")
    if include_v2_complexity:
        _load_mined(HARD_NEGATIVE_REGISTRY_V2_COMPLEXITY_PATH, "hard_negative_mined_v2_complexity")

    return items
