"""Migrate cache tu cau truc CU (chain, address) sang cau truc MOI
(chain, address, incident_id) sau khi sua bug #6 (xem annotation_guide.md
muc 15) - CHI MOVE FILE (khong goi mang lai) de tranh phai re-fetch toan bo
~440 hard-negative candidate.

Dung ban CU (truoc khi sua) cua incident_pipeline.py (import dong tu git
HEAD, van doc dung cau truc flat cu tren dia) de tinh CHINH XAC processed-
address-set cua tung incident/hard-negative theo dung logic da dung khi
build du lieu v0.8 - KHONG suy doan/nho lai tu memory.

Sau migrate: 2 dia chi dung chung biet truoc (0xdd90e5e8... giua
qbridge_qubit_2022/paraluni_2022) se duoc XU LY DAC BIET (giu ban cua
incident fetch SAU CUNG lam migrate, roi refetch rieng cho incident kia).
"""
import importlib.util
import shutil
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "data" / "raw"
OLD_MODULE_PATH = REPO_ROOT.parent / "scratchpad_old_incident_pipeline.py"

# [DA CHAY XONG - script lich su, KHONG con chay lai duoc - xem ghi chu
# Tuan 10 duoi day] Nap ban CU cua incident_pipeline.py (tu git HEAD, truoc
# khi sua bug #6). File nguon la 1 file tam trong scratchpad phien lam viec
# luc do (da bi xoa tu lau, khong con ton tai) - duong dan goc (co chua ten
# may/session ID ca nhan) da duoc RA SOAT VA XOA khoi file nay o Tuan 10
# (reproducibility sprint - xem results/reports/reproduction_v1.0.md muc
# "thong tin ca nhan"). Migration THAT SU da chay xong 1 lan (xem
# data/dataset_card.md muc "sua goc bug #6") - cache tren dia hien tai DA O
# dung cau truc moi, KHONG can chay lai script nay.
OLD_FILE = Path("<DA XOA - file tam scratchpad session, chi dung 1 lan, khong con ton tai>")
spec = importlib.util.spec_from_file_location("old_incident_pipeline", OLD_FILE)
old_mod = importlib.util.module_from_spec(spec)
sys.modules["old_incident_pipeline"] = old_mod
spec.loader.exec_module(old_mod)
# __file__ cua module nap dong la duong dan TAM (scratchpad), khong phai repo
# that -> RAW_DIR tu tinh (REPO_ROOT/parents[2]) sai hoan toan. Ghi de lai
# bang RAW_DIR THAT cua repo (cung 1 hang so, khong lien quan bug #6).
old_mod.RAW_DIR = RAW_DIR

from src.trajectories.builder import load_trajectory_config

config = load_trajectory_config()

migrated_pairs = set()  # (chain, address_lower, incident_id) da migrate, tranh lap


def _migrate_address(chain: str, address: str, incident_id: str) -> None:
    key = (chain, address.lower(), incident_id)
    if key in migrated_pairs:
        return
    migrated_pairs.add(key)
    src_dir = RAW_DIR / chain / address.lower()
    if not src_dir.exists():
        return
    # Chi lay cac file .json nam TRUC TIEP trong src_dir (khong phai da la
    # thu muc con incident_id tu truoc - bo qua neu da migrate)
    files = [f for f in src_dir.iterdir() if f.is_file() and f.suffix == ".json"]
    if not files:
        return
    dst_dir = src_dir / incident_id
    dst_dir.mkdir(parents=True, exist_ok=True)
    for f in files:
        shutil.copy2(f, dst_dir / f.name)


# ----------------------------------------------------------------------
# 1. Primary incidents (17 dong incident_registry.csv, KE CA circulate_2023)
# ----------------------------------------------------------------------
reg_df = pd.read_csv(REPO_ROOT / "metadata" / "incident_registry.csv")
print("=== MIGRATE PRIMARY INCIDENTS ===")
for _, row in reg_df.iterrows():
    incident_id = row["incident_id"]
    chain = row["chain_primary"]
    seed = row["seed_address"]
    start_block = int(row["start_block"])
    traj, _, processed = old_mod.expand_and_build_trajectory(
        chain, seed, start_block, incident_id, int(row["label"]),
        config=config, do_collect=False, max_iterations=None,
    )
    for addr in processed:
        _migrate_address(chain, addr, incident_id)
    print(f"{incident_id:35s} n_actions={len(traj.actions):4d} n_processed={len(processed):3d} -> migrated")

# ----------------------------------------------------------------------
# 2. Hard-negative candidates (moi dong -> parent_incident_id)
# ----------------------------------------------------------------------
hn_path = REPO_ROOT / "metadata" / "hard_negative_registry.csv"
hn_df = pd.read_csv(hn_path)
print(f"\n=== MIGRATE {len(hn_df)} HARD-NEGATIVE CANDIDATES ===")
n_migrated = 0
for _, row in hn_df.iterrows():
    incident_id = row["parent_incident_id"]
    chain = row["chain"]
    seed = row["seed_address"]
    start_block = int(row["start_block"])
    # Hard-negative rebuild dung max_iterations=2 (theo quy uoc cac script
    # thong ke/QA leak hien co) - chi can migrate dung processed set nay.
    traj, _, processed = old_mod.expand_and_build_trajectory(
        chain, seed, start_block, row["hard_negative_id"], 0,
        config=config, do_collect=False, max_iterations=2,
    )
    for addr in processed:
        _migrate_address(chain, addr, incident_id)
    n_migrated += 1
    if n_migrated % 50 == 0:
        print(f"  ... {n_migrated}/{len(hn_df)}")

print(f"\nTONG so (chain, address, incident_id) da migrate: {len(migrated_pairs)}")
