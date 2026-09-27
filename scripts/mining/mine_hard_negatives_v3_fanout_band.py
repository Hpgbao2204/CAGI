"""Giai doan B, Buoc 2 (Tuan 12) - mine bo sung hard-negative cho 11
incident HIEN CO theo tieu chi fan_out MOI (band tuong doi,
compute_max_fan_out() - xem Buoc 1). Uu tien dung lai candidate DA BI
REJECT truoc day (co san cache tu E6, Tuan 9) - KHONG goi API moi.

Da xac nhan TRUOC KHI CHAY (xem cau hoi da hoi nguoi dung): voi 11
incident hien co, positive fan_out cao nhat = 4 (bsc_token_hub_2022),
compute_max_fan_out(4) = 3 (lam tron) = GIONG HET nguong cu - ky vong
THUC NGHIEM la 0 candidate moi pass. Script nay CHAY THAT de xac nhan
bang code, khong chi suy doan.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.collect.hard_negative_miner import (
    INCIDENT_MINING_CONTRACTS,
    MIXER_CONTRACTS,
    _mining_window,
    _passes_structural_filter,
    compute_max_fan_out,
    fetch_contract_counterparties,
    load_known_malicious_addresses,
)
from src.normalize.decoder import build_verified_bridge_address_index, build_verified_mixer_address_index, load_protocol_map
from src.pipeline.incident_pipeline import RAW_DIR, REGISTRY_PATH

REPO_ROOT = Path(__file__).resolve().parents[2]
HARD_NEGATIVE_REGISTRY_PATH = REPO_ROOT / "metadata" / "hard_negative_registry.csv"
HN_V2_PATH = REPO_ROOT / "metadata" / "hard_negative_registry_v2_complexity.csv"
FEATURES_V2_PATH = REPO_ROOT / "data" / "processed" / "features_v2.parquet"
OUT_CSV = REPO_ROOT / "results" / "tables" / "fanout_band_v3_gate_check.csv"
OUT_MD = REPO_ROOT / "results" / "reports" / "fanout_band_v3_mining_v1.md"


def _has_cache(chain: str, address: str, incident_id: str) -> bool:
    d = RAW_DIR / chain / address.lower() / incident_id
    return d.exists() and any(d.glob("*.json"))


def main():
    reg_df = pd.read_csv(REGISTRY_PATH)
    incident_rows = {r["incident_id"]: r for r in reg_df.to_dict("records")}

    feat = pd.read_parquet(FEATURES_V2_PATH)
    full = feat[feat["prefix_label"] == "ratio_100"]
    positive_fan_out = full[full["label"] == 1].set_index("group_id")["fan_out"].to_dict()

    hn1 = pd.read_csv(HARD_NEGATIVE_REGISTRY_PATH)
    hn2 = pd.read_csv(HN_V2_PATH) if HN_V2_PATH.exists() else pd.DataFrame(columns=hn1.columns)
    matched_addresses = set(hn1["seed_address"].str.lower()) | set(hn2["seed_address"].str.lower())
    excluded_base = load_known_malicious_addresses()

    protocol_map = load_protocol_map()
    bridge_index = build_verified_bridge_address_index(protocol_map)
    mixer_index = build_verified_mixer_address_index(protocol_map)

    print("=== Buoc 2: fan_out cua chinh positive + max_fan_out moi tinh duoc ===")
    for iid, fo in sorted(positive_fan_out.items(), key=lambda kv: -kv[1]):
        print(f"  {iid:28s} positive_fan_out={fo:.0f} -> max_fan_out_moi={compute_max_fan_out(int(fo))} (nguong cu=3)")

    rows = []
    newly_passing = []
    for incident_id, contracts in INCIDENT_MINING_CONTRACTS.items():
        if incident_id not in incident_rows or incident_id not in positive_fan_out:
            continue
        incident_row = incident_rows[incident_id]
        seed = incident_row["seed_address"].lower()
        max_fan_out_new = compute_max_fan_out(int(positive_fan_out[incident_id]))

        for chain, protocol_name, contract_address in contracts:
            start_block, end_block = _mining_window(chain, int(incident_row["start_block"]), incident_id)
            candidates = fetch_contract_counterparties(chain, contract_address, incident_id, start_block, end_block, do_collect=False)
            is_mixer = contract_address.lower() in MIXER_CONTRACTS

            seen = set()
            n_checkable = n_pass_old = n_pass_new = 0
            for cand in candidates:
                if cand in seen:
                    continue
                seen.add(cand)
                if cand == seed or cand in matched_addresses or cand in excluded_base:
                    continue
                if not _has_cache(chain, cand, incident_id):
                    continue
                n_checkable += 1

                passed_old, reason_old, _ = _passes_structural_filter(
                    chain, cand, contract_address, incident_id, is_mixer, start_block, end_block,
                    bridge_index, mixer_index, min_candidate_events=1, max_fan_out=3,
                )
                passed_new, reason_new, block_new = _passes_structural_filter(
                    chain, cand, contract_address, incident_id, is_mixer, start_block, end_block,
                    bridge_index, mixer_index, min_candidate_events=1, max_fan_out=max_fan_out_new,
                )
                if passed_old:
                    n_pass_old += 1
                if passed_new:
                    n_pass_new += 1
                if passed_new and not passed_old:
                    newly_passing.append({
                        "incident_id": incident_id, "chain": chain, "address": cand,
                        "contract": contract_address, "start_block": block_new,
                    })

            rows.append({
                "incident_id": incident_id, "chain": chain, "positive_fan_out": positive_fan_out[incident_id],
                "max_fan_out_new": max_fan_out_new, "n_checkable": n_checkable,
                "n_pass_old_threshold": n_pass_old, "n_pass_new_threshold": n_pass_new,
                "n_newly_passing": n_pass_new - n_pass_old,
            })
            print(f"{incident_id:28s} {chain:9s} max_fan_out_moi={max_fan_out_new} "
                  f"checkable={n_checkable:3d} pass_cu={n_pass_old:3d} pass_moi={n_pass_new:3d} "
                  f"newly_passing={n_pass_new - n_pass_old}")

    df = pd.DataFrame(rows)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_CSV, index=False)

    total_newly_passing = int(df["n_newly_passing"].sum())
    print(f"\n=== TONG KET: {total_newly_passing} candidate MOI pass nho tieu chi fan_out da noi ===")

    md = [
        "# Mining bổ sung theo band `fan_out` mới (Giai đoạn B, Bước 2)\n",
        "\n**Đã xác nhận TRƯỚC khi chạy** (không suy đoán, hỏi người dùng xác nhận cách tiến hành): "
        "với 11 incident hiện có, `positive_fan_out` cao nhất = 4 "
        "(`bsc_token_hub_2022`) — `compute_max_fan_out(4) = 3` (làm tròn) = **giống hệt ngưỡng cũ**. "
        "Kỳ vọng: 0 candidate mới pass. Script này CHẠY THẬT để xác nhận bằng code.\n",
        "\n## fan_out của từng positive + max_fan_out mới tính được\n",
        "\n| Incident | positive_fan_out | max_fan_out (mới) | Ngưỡng cũ |\n|---|---|---|---|\n",
    ]
    for iid, fo in sorted(positive_fan_out.items(), key=lambda kv: -kv[1]):
        md.append(f"| {iid} | {fo:.0f} | {compute_max_fan_out(int(fo))} | 3 |\n")

    md += [
        "\n## Kết quả kiểm tra lại 505 candidate đã cache (E6, Tuần 9)\n",
        "\n| Incident | Chain | max_fan_out mới | Checkable | Pass ngưỡng cũ | Pass ngưỡng mới | Mới pass thêm |\n|---|---|---|---|---|---|---|\n",
    ]
    for _, r in df.iterrows():
        md.append(f"| {r['incident_id']} | {r['chain']} | {r['max_fan_out_new']} | {r['n_checkable']} | "
                   f"{r['n_pass_old_threshold']} | {r['n_pass_new_threshold']} | {r['n_newly_passing']} |\n")

    md += [
        f"\n**Tổng candidate mới pass nhờ tiêu chí fan_out đã nới: {total_newly_passing}.**\n",
    ]
    if total_newly_passing == 0:
        md.append(
            "\n**XÁC NHẬN ĐÚNG DỰ ĐOÁN: 0 candidate mới** — vì `max_fan_out` tính được cho CẢ 11/11 "
            "incident hiện có đều bằng 3 (giống hệt ngưỡng cũ, do `positive_fan_out` cao nhất chỉ là "
            "4 và bị làm tròn về 3). Đây KHÔNG phải lỗi của công thức `compute_max_fan_out()` — công "
            "thức hoạt động đúng như thiết kế (band tương đối, không nới lỏng vô điều kiện) — chỉ là "
            "**tập 11 incident hiện tại chưa có incident nào với positive fan_out đủ cao** để band mới "
            "phát huy tác dụng. Payoff thật của tiêu chí này phụ thuộc vào Bước 3 (mở rộng incident "
            "mới) — nếu incident mới có positive fan_out cao hơn hẳn (vd >10), band sẽ nới đáng kể và "
            "supplemental mining lúc đó mới có ý nghĩa. **Không mine bổ sung gì thêm ở bước này "
            "(0 candidate hợp lệ) — chuyển sang Bước 3.**\n"
        )
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("".join(md), encoding="utf-8")
    print(f"Da luu {OUT_MD}")


if __name__ == "__main__":
    main()
