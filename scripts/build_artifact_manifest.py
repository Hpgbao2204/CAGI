"""Tuan 10, Buoc 4 - artifact_manifest.json: liet ke MOI file ket qua quan
trong (results/tables/*.csv, results/figures/*.png, results/reports/*.md,
results/models/*.joblib) kem sha256, ngay tao (mtime tren dia - khong phai
gio tao that vi filesystem Windows co the khong luu creation time chinh
xac qua git checkout), commit hash HIEN TAI.

Khac freeze_v1.0.json (chi 16 file duoc chon lam "dong cung chinh thuc"
tu Tuan 9) - file nay LIET KE TOAN BO artifact ket qua hien co, dung cho
muc dich audit/kiem tra tinh toan ven tong the (Tuan 10).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = REPO_ROOT / "artifact_manifest.json"

SCAN_DIRS = [
    "results/tables",
    "results/figures",
    "results/reports",
    "results/models",
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


def _git_tracked(path: Path) -> bool:
    try:
        rel = path.relative_to(REPO_ROOT)
        out = subprocess.run(
            ["git", "ls-files", "--error-unmatch", str(rel)],
            cwd=REPO_ROOT, capture_output=True,
        )
        return out.returncode == 0
    except Exception:
        return False


def main():
    commit = _git_commit_hash()
    now = datetime.now(timezone.utc).isoformat()

    artifacts = []
    for d in SCAN_DIRS:
        base = REPO_ROOT / d
        if not base.exists():
            continue
        for p in sorted(base.rglob("*")):
            if not p.is_file():
                continue
            rel = str(p.relative_to(REPO_ROOT)).replace("\\", "/")
            artifacts.append({
                "path": rel,
                "sha256": _sha256(p),
                "size_bytes": p.stat().st_size,
                "modified_at_local": datetime.fromtimestamp(p.stat().st_mtime).isoformat(),
                "git_tracked": _git_tracked(p),
            })

    manifest = {
        "generated_at_utc": now,
        "git_commit_hash": commit,
        "n_artifacts": len(artifacts),
        "n_git_tracked": sum(1 for a in artifacts if a["git_tracked"]),
        "n_untracked_local_only": sum(1 for a in artifacts if not a["git_tracked"]),
        "note": "Danh sach TOAN BO artifact ket qua hien co (khac freeze_v1.0.json - "
                "chi 16 file 'dong cung chinh thuc' Tuan 9). git_tracked=false nghia la "
                "file CHUA duoc git add/commit (co the la output cua lan chay gan nhat "
                "chua kip commit) - kiem tra truoc khi coi day la 'ket qua chinh thuc'.",
        "artifacts": artifacts,
    }
    OUT_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Da luu {OUT_PATH}")
    print(f"Tong {len(artifacts)} artifact ({manifest['n_git_tracked']} da tracked, "
          f"{manifest['n_untracked_local_only']} CHUA tracked - can kiem tra)")

    untracked = [a["path"] for a in artifacts if not a["git_tracked"]]
    if untracked:
        print("\nFile CHUA duoc git tracked (kiem tra xem co can commit khong):")
        for u in untracked:
            print(f"  {u}")


if __name__ == "__main__":
    main()
