"""
Xây dựng dataset (X, y, groups) từ trajectory + feature extractor, dùng cho
GroupKFold evaluation. group key = incident_id (Bước 7): mọi prefix của
cùng một trajectory/incident phải nằm cùng split.
"""
from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

import pandas as pd

from src.features.extractor import extract_all_prefixes
from src.trajectories.builder import Trajectory, TrajectoryConfig, build_trajectory


def build_prefix_dataset(
    raw_items: Sequence[dict],
    config: TrajectoryConfig,
    ratios: Sequence[float] = (0.25, 0.5, 0.75, 1.0),
    k_values: Sequence[int] = (2, 3, 5, 7),
) -> Tuple[pd.DataFrame, pd.Series, pd.Series, pd.DataFrame]:
    """raw_items: list các dict {seed, events, incident_id, label} (vd từ
    tests/fixtures/synthetic_trajectories.build_synthetic_dataset()).

    Trả về (X, y, groups, meta) — mỗi row là MỘT PREFIX của MỘT trajectory.
    `groups` = incident_id, dùng cho GroupKFold để tránh leakage giữa các
    prefix cùng incident.
    """
    rows: List[Dict] = []
    labels: List[int] = []
    groups: List[str] = []
    meta_rows: List[Dict] = []

    for item in raw_items:
        traj: Trajectory = build_trajectory(
            item["events"],
            item["seed"],
            config,
            incident_id=item["incident_id"],
            label=item["label"],
        )
        if len(traj) == 0:
            continue
        for spec, feats in extract_all_prefixes(traj, ratios=ratios, k_values=k_values):
            rows.append(feats)
            labels.append(item["label"])
            groups.append(item["incident_id"])
            meta_rows.append(
                {
                    "trajectory_id": traj.trajectory_id,
                    "incident_id": item["incident_id"],
                    "prefix_label": spec.label,
                    "prefix_len": spec.length,
                    "trajectory_len": len(traj),
                }
            )

    X = pd.DataFrame(rows).fillna(0.0)
    y = pd.Series(labels, name="label")
    g = pd.Series(groups, name="incident_id")
    meta = pd.DataFrame(meta_rows)
    return X, y, g, meta
