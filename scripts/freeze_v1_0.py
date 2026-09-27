"""Tuan 9, Buoc 7 - freeze dataset v1.0, feature v1.0, experiment config,
sau khi Buoc 1-6 (E4/E5/E6, calibration, efficiency) da chay va on dinh.
Chuan bi cho Tuan 10 (reproducibility sprint) - ghi lai checksum + phien
ban moi truong + commit hash, de xac nhan KHONG co drift tu day tro di.

"v1.0" o day la so hieu FREEZE (moc coong bo dau tien cho reproducibility),
KHONG trung voi "features_v2.parquet" (ten file, danh so tu Tuan 5 - da
tro thanh ten rieng, khong doi de tranh vo cac script/test dang tham chieu).
"""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import scipy
import sklearn
import xgboost

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_MD = REPO_ROOT / "results" / "reports" / "freeze_v1.0.md"
OUT_JSON = REPO_ROOT / "results" / "reports" / "freeze_v1.0.json"

FROZEN_FILES = [
    "data/processed/features_v2.parquet",
    "configs/features_v2_computed.json",
    "configs/features.yaml",
    "configs/model.yaml",
    "configs/data.yaml",
    "metadata/split_manifest.json",
    "metadata/incident_registry.csv",
    "metadata/hard_negative_registry.csv",
    "metadata/hard_negative_registry_v2_complexity.csv",
    "results/models/m1_final.joblib",
    "results/tables/main_table.csv",
    "results/tables/baseline_results_v2.csv",
    "results/tables/ablation_table.csv",
    "results/tables/robustness_table.csv",
    "results/tables/calibration_table.csv",
    "results/tables/runtime_table.csv",
]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_commit_hash() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT).decode().strip()
    except Exception:
        return "UNKNOWN"


def _git_dirty() -> bool:
    try:
        out = subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO_ROOT).decode()
        return len(out.strip()) > 0
    except Exception:
        return True


def main():
    now = datetime.now(timezone.utc).isoformat()
    commit = _git_commit_hash()
    dirty = _git_dirty()

    checksums = {}
    missing = []
    for rel in FROZEN_FILES:
        p = REPO_ROOT / rel
        if not p.exists():
            missing.append(rel)
            continue
        checksums[rel] = {"sha256": _sha256(p), "size_bytes": p.stat().st_size}

    df = pd.read_parquet(REPO_ROOT / "data" / "processed" / "features_v2.parquet")
    composition = {
        "n_rows_total": int(len(df)),
        "n_positive_rows": int((df["label"] == 1).sum()),
        "n_negative_rows": int((df["label"] == 0).sum()),
        "n_groups": int(df["group_id"].nunique()),
        "n_trajectories_distinct": int(df["source_id"].nunique()),
        "kind_counts": df.drop_duplicates("source_id")["kind"].value_counts().to_dict(),
    }

    env = {
        "python_version": platform.python_version(), "platform": platform.platform(),
        "sklearn_version": sklearn.__version__, "xgboost_version": xgboost.__version__,
        "pandas_version": pd.__version__, "scipy_version": scipy.__version__,
    }

    experiment_config = {
        "M1_hyperparameters": {
            "n_estimators": 200, "max_depth": 4, "learning_rate": 0.1, "random_state": 42,
            "min_positive_incident_coverage": 2,
            "scale_pos_weight": "n_neg/n_pos (tinh tren train fold)",
        },
        "threshold_policy": "FPR<=1% (select_threshold, fallback macro-F1 neu khong dat), "
                             "chon tren inner-train OOF - KHONG BAO GIO tren outer test",
        "split_methodology": "Leave-one-incident-out (LeaveOneGroupOut, group=parent_incident_id), "
                              "nested (outer+inner) - src/evaluation/nested_eval.py",
        "pooling_dedupe": "RQ1/ablation/calibration/E6: pool 8 prefix bucket + "
                           "dedupe_pooled_prefixes(source_id, prefix_len). RQ2: KHONG pool, "
                           "danh gia tung bucket rieng.",
        "calibration_recommended": "isotonic (ECE 0.0332 -> 0.0149, xem calibration_v1.md) - "
                                    "TUY CHON, chua bat buoc ap dung mac dinh cho RQ1/RQ2 da bao cao",
        "ablation_columns": {
            "no_temporal": ["time_to_first_bridge", "inter_action_gap_mean", "inter_action_gap_std",
                             "burstiness", "active_duration_sec"],
            "no_motif": ["motif_split", "motif_merge", "motif_peel_like_chain", "motif_bridge_then_swap",
                         "motif_swap_then_split", "motif_nested_bridge", "motif_rapid_token_pivot"],
            "no_bridge_context": ["time_to_first_bridge", "action_count_bridge_deposit",
                                   "action_count_bridge_deposit_ratio", "action_count_bridge_withdraw",
                                   "action_count_bridge_withdraw_ratio", "num_bridge_families",
                                   "swap_after_bridge", "motif_bridge_then_swap", "motif_nested_bridge"],
        },
    }

    manifest = {
        "freeze_version": "v1.0", "frozen_at_utc": now, "git_commit_hash": commit,
        "git_working_tree_dirty_at_freeze": dirty,
        "dataset_composition": composition, "environment": env,
        "experiment_config": experiment_config, "file_checksums": checksums,
        "missing_files": missing,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Da luu {OUT_JSON}")

    md = [
        "# Freeze v1.0 — Dataset / Feature / Experiment Config (Tuần 9, Bước 7)\n",
        f"\n**Thời điểm freeze:** {now}\n",
        f"**Git commit hash:** `{commit}`{' — ⚠️ WORKING TREE DIRTY LÚC FREEZE (có thay đổi chưa commit)' if dirty else ' (working tree sạch)'}\n",
        "\n## Thành phần dataset (features_v2.parquet)\n\n```\n" + json.dumps(composition, indent=2, ensure_ascii=False) + "\n```\n",
        "\n## Môi trường\n\n```\n" + "\n".join(f"{k}: {v}" for k, v in env.items()) + "\n```\n",
        "\n## Experiment config đông cứng\n\n```\n" + json.dumps(experiment_config, indent=2, ensure_ascii=False) + "\n```\n",
        "\n## Checksum file đông cứng (sha256)\n\n| File | sha256 | size (bytes) |\n|---|---|---|\n",
    ]
    for rel, info in checksums.items():
        md.append(f"| `{rel}` | `{info['sha256'][:16]}…` | {info['size_bytes']} |\n")
    if missing:
        md.append(f"\n**⚠️ File thiếu (chưa freeze được):** {missing}\n")
    md += [
        "\n## Cách xác minh không drift (Tuần 10)\n",
        "\n```bash\npython scripts/freeze_v1.0.py   # chạy lại, so sánh sha256 với bản ghi ở trên\n```\n",
        "Nếu bất kỳ sha256 nào đổi mà KHÔNG có commit mới giải thích rõ lý do — đây là drift "
        "ngoài ý muốn, cần điều tra trước khi tiếp tục Tuần 10 (reproducibility sprint).\n",
    ]
    OUT_MD.write_text("".join(md), encoding="utf-8")
    print(f"Da luu {OUT_MD}")
    print(f"\nCommit hash: {commit} (dirty={dirty})")
    print(f"So file da freeze: {len(checksums)}/{len(FROZEN_FILES)} (thieu: {missing})")


if __name__ == "__main__":
    main()
