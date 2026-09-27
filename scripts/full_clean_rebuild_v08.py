"""Rebuild SACH toan bo 16 dong "primary" (11 positive + 5 control) sau khi
sua 3 bug: (1) thieu dedup trong _load_cached_rows, (2) client khong tu don
cache cu truoc khi fetch lai (gay tich luy nhieu the he file chong lan),
(3) dia chi 1inch bi thieu ky tu + thieu Uniswap V3 USDC pool trong
allowlist (xem annotation_guide.md muc 14).

Chay TUAN TU, dung network that, do_collect=True, max_iterations=None
(dung config.max_depth mac dinh - GIONG HET cach run_incident_pipeline.py
CLI van chay, khong cap nhan tao o muc 2 nhu audit script truoc).

Sau khi rebuild tat ca, chay LAI 1 vong do_collect=False de phat hien incident
nao bi "ghi de" boi 1 incident khac dung chung dia chi (window khac nhau).
"""
import json
import time

import pandas as pd

from src.pipeline.incident_pipeline import REGISTRY_PATH, run_incident_pipeline
from src.trajectories.builder import load_trajectory_config

config = load_trajectory_config()
reg_df = pd.read_csv(REGISTRY_PATH)
reg_df = reg_df[reg_df["eval_tier"] == "primary"]

pass1 = []
for _, row in reg_df.iterrows():
    incident_id = row["incident_id"]
    print(f"=== FETCH SACH: {incident_id} ({row['chain_primary']}) ===", flush=True)
    traj, provenance_events, processed = run_incident_pipeline(
        incident_id, do_collect=True, max_iterations=None, write_output=True,
    )
    n = len(traj.actions)
    print(f"    n_actions={n} n_processed={len(processed)}", flush=True)
    pass1.append({"incident_id": incident_id, "n_actions_pass1": n, "n_processed_pass1": len(processed)})
    time.sleep(0.5)

print("\n=== PASS 2: xac nhan on dinh (do_collect=False) ===")
pass2 = []
for _, row in reg_df.iterrows():
    incident_id = row["incident_id"]
    traj, _, processed = run_incident_pipeline(
        incident_id, do_collect=False, max_iterations=None, write_output=False,
    )
    n = len(traj.actions)
    pass2.append({"incident_id": incident_id, "n_actions_pass2": n, "n_processed_pass2": len(processed)})

print("\n=== SO SANH PASS1 vs PASS2 (phat hien clobber do dia chi dung chung) ===")
unstable = []
for r1, r2 in zip(pass1, pass2):
    assert r1["incident_id"] == r2["incident_id"]
    stable = r1["n_actions_pass1"] == r2["n_actions_pass2"]
    if not stable:
        unstable.append(r1["incident_id"])
    print(r1["incident_id"], "pass1=", r1["n_actions_pass1"], "pass2=", r2["n_actions_pass2"], "" if stable else "*** UNSTABLE ***")

print(f"\nSo incident UNSTABLE (bi anh huong boi dia chi dung chung): {len(unstable)}")
print(unstable)

with open("data/processed/full_clean_rebuild_v08_results.json", "w", encoding="utf-8") as f:
    json.dump({"pass1": pass1, "pass2": pass2, "unstable": unstable}, f, indent=2)
