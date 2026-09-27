"""Tuan 9, Buoc 0 - xac nhan THAT (khong mac dinh) truoc khi lam E6: du lieu
candidate bi _passes_structural_filter loai co san trong cache
(data/raw/{chain}/{address}/{incident_id}/) tu qua trinh mining truoc day,
hay can fetch lai?

Cach lam: voi moi incident, doc lai DUNG danh sach candidate tu
fetch_contract_counterparties(..., do_collect=False) (chi doc cache, khong
goi API) - day la TOAN BO dia chi da tung tuong tac voi contract mining
trong cua so thoi gian, KHONG phu thuoc lich su script nao da chay. Loai
tru: seed address, dia chi malicious da biet, dia chi DA duoc chap nhan lam
hard-negative (403 + 106 hien tai - do la tap "matched", khong phai tap can
dung cho E6).

Voi cac candidate CON LAI (chua matched, chua excluded): kiem tra co thu
muc cache data/raw/{chain}/{address}/{incident_id}/ hay khong (bang chung
DA tung duoc fetch trong 1 lan chay mining truoc day, do
collect_address_raw_data() duoc goi cho MOI candidate checked, ke ca bi
tu choi - xem hard_negative_miner.py dong 345-351). Neu CO cache -> dung
_passes_structural_filter(..., do_collect ngam dinh vi load_events_for_addresses
chi doc cache) de phan loai pass/fail; neu KHONG co cache -> KHONG chay
filter (se cho ket qua sai/rong gia tao), dem rieng vao "chua ro trang
thai, can fetch moi neu muon dung".
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.collect.hard_negative_miner import (
    HARD_NEGATIVE_REGISTRY_PATH,
    INCIDENT_MINING_CONTRACTS,
    MIXER_CONTRACTS,
    _mining_window,
    _passes_structural_filter,
    fetch_contract_counterparties,
    load_known_malicious_addresses,
)
from src.normalize.decoder import build_verified_bridge_address_index, build_verified_mixer_address_index, load_protocol_map
from src.pipeline.incident_pipeline import RAW_DIR, REGISTRY_PATH

REPO_ROOT = Path(__file__).resolve().parents[1]
HN_V2_PATH = REPO_ROOT / "metadata" / "hard_negative_registry_v2_complexity.csv"
OUT_CSV = REPO_ROOT / "results" / "tables" / "e6_gate_check.csv"


def _has_cache(chain: str, address: str, incident_id: str) -> bool:
    d = RAW_DIR / chain / address.lower() / incident_id
    return d.exists() and any(d.glob("*.json"))


def main():
    reg_df = pd.read_csv(REGISTRY_PATH)
    incident_rows = {r["incident_id"]: r for r in reg_df.to_dict("records")}

    hn1 = pd.read_csv(HARD_NEGATIVE_REGISTRY_PATH)
    hn2 = pd.read_csv(HN_V2_PATH) if HN_V2_PATH.exists() else pd.DataFrame(columns=hn1.columns)
    matched_addresses = set(hn1["seed_address"].str.lower()) | set(hn2["seed_address"].str.lower())
    print(f"Tong matched hard-negative hien tai (403+106): {len(matched_addresses)} dia chi distinct", flush=True)

    excluded_base = load_known_malicious_addresses()

    protocol_map = load_protocol_map()
    bridge_index = build_verified_bridge_address_index(protocol_map)
    mixer_index = build_verified_mixer_address_index(protocol_map)

    rows = []
    for incident_id, contracts in INCIDENT_MINING_CONTRACTS.items():
        if incident_id not in incident_rows:
            continue
        incident_row = incident_rows[incident_id]
        seed = incident_row["seed_address"].lower()
        for chain, protocol_name, contract_address in contracts:
            start_block, end_block = _mining_window(chain, int(incident_row["start_block"]), incident_id)
            candidates = fetch_contract_counterparties(
                chain, contract_address, incident_id, start_block, end_block, do_collect=False,
            )
            is_mixer = contract_address.lower() in MIXER_CONTRACTS

            n_total = len(set(candidates))
            n_matched = n_excluded_other = n_cached_checkable = n_no_cache = 0
            n_pass = n_fail = 0
            reject_reasons = {}
            seen = set()
            for cand in candidates:
                if cand in seen:
                    continue
                seen.add(cand)
                if cand == seed:
                    continue
                if cand in matched_addresses:
                    n_matched += 1
                    continue
                if cand in excluded_base:
                    n_excluded_other += 1
                    continue
                if not _has_cache(chain, cand, incident_id):
                    n_no_cache += 1
                    continue
                n_cached_checkable += 1
                passed, reason, _ = _passes_structural_filter(
                    chain, cand, contract_address, incident_id, is_mixer, start_block, end_block,
                    bridge_index, mixer_index, min_candidate_events=1,
                )
                if passed:
                    n_pass += 1
                else:
                    n_fail += 1
                    reject_reasons[reason] = reject_reasons.get(reason, 0) + 1

            rows.append({
                "incident_id": incident_id, "chain": chain, "contract": contract_address,
                "n_total_candidates": n_total, "n_already_matched": n_matched,
                "n_excluded_other": n_excluded_other, "n_no_cache_unknown": n_no_cache,
                "n_checkable_from_cache": n_cached_checkable,
                "n_pass_structural_filter": n_pass, "n_fail_structural_filter": n_fail,
                "reject_reasons": str(reject_reasons),
            })
            print(f"{incident_id:28s} {chain:9s} candidates={n_total:4d} matched={n_matched:3d} "
                  f"excluded_other={n_excluded_other:3d} no_cache={n_no_cache:3d} "
                  f"checkable={n_cached_checkable:3d} -> pass={n_pass:3d} fail={n_fail:3d} "
                  f"reasons={reject_reasons}", flush=True)

    df = pd.DataFrame(rows)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_CSV, index=False)

    total_fail = int(df["n_fail_structural_filter"].sum())
    total_no_cache = int(df["n_no_cache_unknown"].sum())
    total_checkable = int(df["n_checkable_from_cache"].sum())
    print(f"\n=== TONG KET ===")
    print(f"Tong candidate CO CACHE, kiem tra duoc ngay (khong can API moi): {total_checkable}")
    print(f"  -> pass filter: {int(df['n_pass_structural_filter'].sum())}")
    print(f"  -> FAIL filter (= pool 'unmatched negative' cho E6): {total_fail}")
    print(f"Tong candidate CHUA CO CACHE (can fetch moi neu muon dua vao E6): {total_no_cache}")
    print(f"\nDa luu {OUT_CSV}")


if __name__ == "__main__":
    main()
