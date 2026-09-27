"""Sau khi fix bug thieu dedup trong _load_cached_rows (src/pipeline/incident_pipeline.py),
build lai TAT CA 15 dong (khong goi mang, dung cache hien co tren dia - la hop cua cache
cu + cache widen do audit_cache_completeness.py tao ra) va so sanh voi golden fixture
(neu co) de xac dinh: thay doi nao la du lieu that bi thieu truoc day, thay doi nao la
artifact cua bug double-count vua fix.
"""
import json
from pathlib import Path

import pandas as pd

from src.pipeline.incident_pipeline import REGISTRY_PATH, compute_end_block, expand_and_build_trajectory
from src.trajectories.builder import load_trajectory_config

GOLDEN_DIR = Path("tests/fixtures/golden")

config = load_trajectory_config()
reg_df = pd.read_csv(REGISTRY_PATH)
reg_df = reg_df[reg_df["eval_tier"] == "primary"]
reg_df = reg_df[reg_df["incident_id"] != "qbridge_qubit_2022"]

results = []
for _, row in reg_df.iterrows():
    incident_id = row["incident_id"]
    chain = row["chain_primary"]
    seed = row["seed_address"]
    start_block = int(row["start_block"])

    traj, _, processed = expand_and_build_trajectory(
        chain, seed, start_block, incident_id, int(row["label"]),
        config=config, do_collect=False, max_iterations=2,
    )
    n_after_fix = len(traj.actions)

    golden_path = GOLDEN_DIR / f"{incident_id}_events.golden.json"
    n_golden = None
    if golden_path.exists():
        n_golden = len(json.loads(golden_path.read_text(encoding="utf-8")))

    results.append({
        "incident_id": incident_id, "chain": chain,
        "n_actions_after_dedup_fix": n_after_fix,
        "n_golden": n_golden,
        "matches_golden": (n_golden == n_after_fix) if n_golden is not None else None,
    })
    print(results[-1], flush=True)

print("\n=== TONG KET (sau fix dedup) ===")
for r in results:
    print(r)
