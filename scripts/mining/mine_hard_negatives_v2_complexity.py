"""Buoc 2 (Tuan 5, dot 2 - sua shortcut do dai) - mine BO SUNG hard-negative
voi tieu chi MOI: do phuc tap (min_candidate_events, log-scale theo do dai
trajectory positive tuong ung - xem compute_min_candidate_events).

KHONG thay the 403 hard-negative cu (van giu nguyen trong
metadata/hard_negative_registry.csv) - ghi vao file RIENG
metadata/hard_negative_registry_v2_complexity.csv, id_infix="hnc" de
khong trung id. KHONG ha bat ky tieu chi nao khac (contract/fan_out/
mixer/volume giu nguyen y het _passes_structural_filter cu).

Ghi ket qua NGAY SAU MOI incident (khong doi den cuoi) - tranh bug mat du
lieu da gap truoc day khi 1 incident loi giua chung lam mat ket qua cac
incident da xong.
"""
from __future__ import annotations

import csv
import math
from pathlib import Path

import pandas as pd

import src.collect.hard_negative_miner as hn_mod
from src.collect.bsctrace_client import BscTraceClient
from src.collect.etherscan_client import EtherscanClient
from src.collect.hard_negative_miner import (
    BSC_CHAINS,
    HARD_NEGATIVE_REGISTRY_PATH,
    INCIDENT_MINING_CONTRACTS,
    RAW_DIR,
    MiningReport,
    MiningResult,
    compute_min_candidate_events,
    load_known_malicious_addresses,
    mine_hard_negatives_for_incident,
    write_hard_negative_registry,
)
from src.pipeline.incident_pipeline import REGISTRY_PATH, expand_and_build_trajectory
from src.trajectories.builder import load_trajectory_config

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = REPO_ROOT / "metadata" / "hard_negative_registry_v2_complexity.csv"
TARGET_PER_INCIDENT = 10
MAX_CANDIDATES_CHECKED = 150


def _robust_make_client(chain: str):
    """Thay _make_client mac dinh (max_retries=5, backoff_base_sec=1.0) —
    contract dung chung nhu PancakeSwap V2 (dung cho nhieu incident: qbridge_
    qubit_2022, wault_finance_2021, paraluni_2022) cuc ky nhieu giao dich,
    fetch TOAN BO lich su bidirectional trong cua so +-7 ngay gap rate-limit
    lien tuc — 5 lan retry (backoff toi da ~31s) khong du. Tang len 10 lan,
    backoff_base_sec=2.0 (toi da ~1024s cho lan retry cuoi) cho vong mine
    bo sung nay."""
    if chain in BSC_CHAINS:
        return BscTraceClient(cache_dir=RAW_DIR, max_retries=10, backoff_base_sec=2.0)
    return EtherscanClient(cache_dir=RAW_DIR, max_retries=10, backoff_base_sec=2.0)


hn_mod._make_client = _robust_make_client


def _load_resume_state():
    """Neu OUT_PATH da co du lieu tu 1 lan chay TRUOC bi loi giua chung
    (vd BSCTrace het quota) - nap lai de KHONG mine lai tu dau cac incident
    da xong (tranh lang phi quota/thoi gian that)."""
    all_reports: dict = {}
    if not OUT_PATH.exists():
        return all_reports
    df = pd.read_csv(OUT_PATH)
    for incident_id, grp in df.groupby("parent_incident_id"):
        report = MiningReport(parent_incident_id=incident_id)
        for _, r in grp.iterrows():
            report.accepted.append(MiningResult(
                address=r["seed_address"], chain=r["chain"], contract_used=r["contract_used"],
                protocol_name=r["protocol_name"], block_number=int(r["start_block"]),
            ))
        all_reports[incident_id] = report
    return all_reports


def main():
    config = load_trajectory_config()
    reg_df = pd.read_csv(REGISTRY_PATH)
    reg_df = reg_df[(reg_df["eval_tier"] == "primary") & (reg_df["label"] == 1)]

    all_reports: dict = _load_resume_state()
    failed_incidents: list = []
    if all_reports:
        print(f"RESUME: da co san {sum(len(r.accepted) for r in all_reports.values())} dong tu lan chay truoc "
              f"({list(all_reports.keys())}) - bo qua cac incident nay.", flush=True)

    # Loai tru: seed/known-malicious (da xu ly trong mine_hard_negatives_for_incident)
    # + TOAN BO dia chi da dung lam hard-negative o vong mine truoc (KHONG
    # dung lai, tranh trung) + dia chi da mine o vong nay (resume).
    existing_hn_addrs = set()
    if HARD_NEGATIVE_REGISTRY_PATH.exists():
        existing_hn_addrs = {a.lower() for a in pd.read_csv(HARD_NEGATIVE_REGISTRY_PATH)["seed_address"]}
    resumed_addrs = {r.address.lower() for report in all_reports.values() for r in report.accepted}
    global_excluded = set(load_known_malicious_addresses()) | existing_hn_addrs | resumed_addrs

    # Xu ly cac incident dung contract PancakeSwap V2 (cuc ky nhieu giao
    # dich, da gap loi het quota lien tuc) SAU CUNG — uu tien mine xong cac
    # incident dung contract khac (it rui ro rate-limit hon) truoc.
    PANCAKESWAP_HEAVY = {"qbridge_qubit_2022", "wault_finance_2021", "paraluni_2022"}
    reg_df = pd.concat([
        reg_df[~reg_df["incident_id"].isin(PANCAKESWAP_HEAVY)],
        reg_df[reg_df["incident_id"].isin(PANCAKESWAP_HEAVY)],
    ])

    for _, row in reg_df.iterrows():
        incident_id = row["incident_id"]
        if incident_id not in INCIDENT_MINING_CONTRACTS:
            continue
        if incident_id in all_reports and len(all_reports[incident_id].accepted) >= TARGET_PER_INCIDENT:
            print(f"\n=== Bo qua {incident_id} (da du {len(all_reports[incident_id].accepted)}/{TARGET_PER_INCIDENT} tu resume) ===", flush=True)
            continue

        traj, _, _ = expand_and_build_trajectory(
            row["chain_primary"], row["seed_address"], int(row["start_block"]),
            incident_id, 1, config=config, do_collect=False, max_iterations=None,
        )
        pos_len = len(traj.actions)
        min_events = compute_min_candidate_events(pos_len)
        print(f"\n=== Mining bo sung {incident_id} (positive_len={pos_len}, "
              f"min_candidate_events={min_events}, target={TARGET_PER_INCIDENT}) ===", flush=True)

        # KHONG de 1 incident loi (vd het quota API o contract cuc ky nhieu
        # giao dich nhu PancakeSwap V2) lam dung toan bo cac incident con
        # lai dung contract KHAC — ghi nhan that bai, tiep tuc incident tiep.
        try:
            report = mine_hard_negatives_for_incident(
                incident_id, row.to_dict(), target_count=TARGET_PER_INCIDENT,
                max_candidates_checked=MAX_CANDIDATES_CHECKED,
                excluded_addresses=global_excluded, do_collect=True,
                min_candidate_events=min_events,
            )
        except Exception as exc:
            print(f"  *** LOI khi mining {incident_id}: {exc} — BO QUA, tiep tuc incident tiep theo ***", flush=True)
            failed_incidents.append(incident_id)
            continue

        all_reports[incident_id] = report
        global_excluded |= {r.address for r in report.accepted}

        n_insufficient = sum(1 for r in report.rejected if r.reject_reason == "insufficient_complexity_vs_positive")
        print(f"  {incident_id}: accepted={len(report.accepted)} checked={report.candidates_checked} "
              f"rejected_insufficient_complexity={n_insufficient}/{len(report.rejected)}", flush=True)

        # Ghi NGAY sau moi incident — tranh mat du lieu neu incident sau loi.
        write_hard_negative_registry(all_reports, path=OUT_PATH, id_infix="hnc")
        print(f"  Da ghi tam {OUT_PATH} ({sum(len(r.accepted) for r in all_reports.values())} dong tich luy)", flush=True)

    print("\n=== TONG KET mining bo sung (do phuc tap) ===")
    for iid, report in all_reports.items():
        print(f"{iid:32s} accepted={len(report.accepted):3d} checked={report.candidates_checked:4d}")
    total_accepted = sum(len(r.accepted) for r in all_reports.values())
    print(f"\nTONG accepted moi: {total_accepted}")
    if failed_incidents:
        print(f"\n*** Cac incident LOI (chua mine duoc o vong nay, can chay lai rieng sau): {failed_incidents} ***")


if __name__ == "__main__":
    main()
