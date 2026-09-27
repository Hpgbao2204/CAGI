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
from src.pipeline.incident_pipeline import (
    PROCESSED_DIR, REGISTRY_PATH, address_cache_complete, expand_and_build_trajectory,
)
from src.normalize.schema import CanonicalEvent
from src.trajectories.builder import build_trajectory
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
    max_iterations_negative: Optional[int] = None,
    verbose: bool = False,
    include_v2_complexity: bool = False,
    require_complete_cache: bool = False,
    provenance: Optional[dict] = None,
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
    # Mac dinh (2026-09-27): CUNG so vong mo rong cho incident va negative
    # (configs/data.yaml::trajectory.expand_iterations).
    if max_iterations_positive is None:
        max_iterations_positive = config.expand_iterations
    if max_iterations_negative is None:
        max_iterations_negative = config.expand_iterations
    group_of = _load_group_membership()
    if provenance is None:
        provenance = {}

    items: List[DatasetItem] = []

    reg_df = pd.read_csv(REGISTRY_PATH)
    reg_df = reg_df[reg_df["eval_tier"] == "primary"]
    for _, row in reg_df.iterrows():
        incident_id = row["incident_id"]
        traj, _, processed = expand_and_build_trajectory(
            row["chain_primary"], row["seed_address"], int(row["start_block"]),
            incident_id, int(row["label"]), config=config, do_collect=False,
            max_iterations=max_iterations_positive,
        )
        complete = all(address_cache_complete(row["chain_primary"], a, incident_id) for a in processed)
        provenance[incident_id] = "raw_cache" if complete else "raw_cache_incomplete"
        if require_complete_cache and not complete:
            fallback = _trajectory_from_decoded_trace(incident_id, row, config, max_iterations_positive)
            if fallback is not None:
                traj = fallback
                provenance[incident_id] = "original_decoded_trace"
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
            traj, _, processed = expand_and_build_trajectory(
                row["chain"], row["seed_address"], int(row["start_block"]),
                parent, 0, config=config, do_collect=False,
                max_iterations=max_iterations_negative,
            )
            if require_complete_cache and not all(address_cache_complete(row["chain"], a, parent) for a in processed):
                provenance[hn_id] = "excluded_incomplete_cache"
                n_empty += 1
                continue
            if len(traj) == 0:
                n_empty += 1
                continue
            provenance[hn_id] = "raw_cache"
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


def _trajectory_from_decoded_trace(incident_id: str, row, config: TrajectoryConfig, max_iterations: int):
    """Fallback khi cache API khong day du (vd het quota NodeReal cho BSC):
    dung trace DA DECODE tu lan crawl goc (data/processed/original_trace/,
    trung voi tests/fixtures/golden) va cat ve CUNG so hop voi cac trajectory
    khac: chay lai builder voi max_depth = max_iterations + 1 (nguon cua
    action phai nam trong <= max_iterations hop tu seed)."""
    from dataclasses import replace
    path = PROCESSED_DIR / "original_trace" / f"{incident_id}_events.json"
    if not path.exists():
        return None
    events = [CanonicalEvent(**e) for e in json.loads(path.read_text(encoding="utf-8"))]
    cfg = replace(config, max_depth=max_iterations + 1)
    return build_trajectory(events, seed_address=row["seed_address"], config=cfg, incident_id=incident_id,
                            label=int(row["label"]), trajectory_id=incident_id)
