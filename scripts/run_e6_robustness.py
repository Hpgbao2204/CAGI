"""Tuan 9, Buoc 4 - E6: so sanh M1 tren hard-negative DA MATCH (hien tai,
403+106) vs "unmatched negative" (candidate bi _passes_structural_filter
loai, xem Buoc 0 - results/reports/e6_gate_v1.md, 505 candidate co san
cache, KHONG can API moi).

Goi dung ten "unmatched negative" (khong phai "random tuyet doi") trong
bao cao - cac candidate nay VAN da tuong tac voi contract trong allowlist,
chi khong khop tieu chi cau truc/volume (_passes_structural_filter).
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

from src.collect.hard_negative_miner import (
    INCIDENT_MINING_CONTRACTS,
    MIXER_CONTRACTS,
    _mining_window,
    fetch_contract_counterparties,
    load_known_malicious_addresses,
)
from src.evaluation.metrics import pr_auc
from src.evaluation.nested_eval import bootstrap_incident_level, dedupe_pooled_prefixes, evaluate_model_nested, per_incident_metric
from src.features.extractor import extract_all_prefixes
from src.models.baselines import M1TypedTemporalMotifModel
from src.normalize.decoder import build_verified_bridge_address_index, build_verified_mixer_address_index, load_protocol_map
from src.pipeline.dataset_builder import load_rq1_trajectories
from src.pipeline.incident_pipeline import RAW_DIR, REGISTRY_PATH, expand_and_build_trajectory, load_events_for_addresses
from src.trajectories.builder import load_trajectory_config

REPO_ROOT = Path(__file__).resolve().parents[1]
HARD_NEGATIVE_REGISTRY_PATH = REPO_ROOT / "metadata" / "hard_negative_registry.csv"
HN_V2_PATH = REPO_ROOT / "metadata" / "hard_negative_registry_v2_complexity.csv"
OOF_M1_FULL_PATH = REPO_ROOT / "data" / "processed" / "oof_predictions_v1.csv"
FEATURES_V2_PATH = REPO_ROOT / "data" / "processed" / "features_v2.parquet"
OUT_TABLE = REPO_ROOT / "results" / "tables" / "robustness_table.csv"
OUT_MD = REPO_ROOT / "results" / "reports" / "e6_robustness_v1.md"

META_COLS = ["trajectory_id", "source_id", "group_id", "kind", "chain", "label",
             "prefix_label", "prefix_len", "trajectory_len"]


def _has_cache(chain: str, address: str, incident_id: str) -> bool:
    d = RAW_DIR / chain / address.lower() / incident_id
    return d.exists() and any(d.glob("*.json"))


def _first_touch_block(chain, candidate, contract_address, incident_id, start_block, end_block, bridge_index, mixer_index) -> Optional[int]:
    events = load_events_for_addresses(chain, [candidate], incident_id, bridge_index, mixer_index=mixer_index)
    events = [e for e in events if start_block <= e.block_number <= end_block]
    contract_touch = [e for e in events if e.src == contract_address.lower() or e.dst == contract_address.lower()]
    if not contract_touch:
        return None
    return min(e.block_number for e in contract_touch)


def collect_unmatched_negative_candidates() -> List[dict]:
    """Tai lap DUNG logic Buoc 0 (results/reports/e6_gate_v1.md) - candidate
    bi loai boi _passes_structural_filter, CHI dung candidate da co cache
    (khong goi API moi). Tra ve list dict (chain, address, contract, parent_incident_id, start_block)."""
    from src.collect.hard_negative_miner import _passes_structural_filter

    reg_df = pd.read_csv(REGISTRY_PATH)
    incident_rows = {r["incident_id"]: r for r in reg_df.to_dict("records")}

    hn1 = pd.read_csv(HARD_NEGATIVE_REGISTRY_PATH)
    hn2 = pd.read_csv(HN_V2_PATH) if HN_V2_PATH.exists() else pd.DataFrame(columns=hn1.columns)
    matched_addresses = set(hn1["seed_address"].str.lower()) | set(hn2["seed_address"].str.lower())
    excluded_base = load_known_malicious_addresses()

    protocol_map = load_protocol_map()
    bridge_index = build_verified_bridge_address_index(protocol_map)
    mixer_index = build_verified_mixer_address_index(protocol_map)

    out = []
    for incident_id, contracts in INCIDENT_MINING_CONTRACTS.items():
        if incident_id not in incident_rows:
            continue
        incident_row = incident_rows[incident_id]
        seed = incident_row["seed_address"].lower()
        for chain, protocol_name, contract_address in contracts:
            start_block, end_block = _mining_window(chain, int(incident_row["start_block"]), incident_id)
            candidates = fetch_contract_counterparties(chain, contract_address, incident_id, start_block, end_block, do_collect=False)
            is_mixer = contract_address.lower() in MIXER_CONTRACTS
            seen = set()
            for cand in candidates:
                if cand in seen:
                    continue
                seen.add(cand)
                if cand == seed or cand in matched_addresses or cand in excluded_base:
                    continue
                if not _has_cache(chain, cand, incident_id):
                    continue
                passed, reason, _ = _passes_structural_filter(
                    chain, cand, contract_address, incident_id, is_mixer, start_block, end_block,
                    bridge_index, mixer_index, min_candidate_events=1,
                )
                if passed:
                    continue
                block = _first_touch_block(chain, cand, contract_address, incident_id, start_block, end_block, bridge_index, mixer_index)
                if block is None:
                    continue  # khong tim duoc block cham contract - bo qua, khong doan
                out.append({
                    "chain": chain, "address": cand, "contract_used": contract_address,
                    "parent_incident_id": incident_id, "start_block": block, "reject_reason": reason,
                })
    return out


def main():
    print("=== Buoc A: thu thap candidate 'unmatched negative' (chi doc cache) ===", flush=True)
    candidates = collect_unmatched_negative_candidates()
    print(f"Tong {len(candidates)} candidate unmatched-negative kha dung.", flush=True)
    by_incident = pd.Series([c["parent_incident_id"] for c in candidates]).value_counts()
    print(by_incident.to_string(), flush=True)

    print("\n=== Buoc B: build trajectory (do_collect=False, chi cache) ===", flush=True)
    config = load_trajectory_config()
    unmatched_items = []
    n_empty = 0
    for c in candidates:
        traj, _, _ = expand_and_build_trajectory(
            c["chain"], c["address"], int(c["start_block"]), c["parent_incident_id"], 0,
            config=config, do_collect=False, max_iterations=2,
        )
        if len(traj) == 0:
            n_empty += 1
            continue
        unmatched_items.append({
            "trajectory": traj, "group_id": c["parent_incident_id"], "label": 0,
            "chain": c["chain"], "kind": "unmatched_negative",
            "source_id": f"{c['parent_incident_id']}__unm_{c['address'][2:10]}",
        })
    print(f"Trajectory rong (bo qua): {n_empty}/{len(candidates)}", flush=True)
    print(f"Unmatched-negative usable: {len(unmatched_items)}", flush=True)

    print("\n=== Buoc C: lay 11 positive trajectory (tai su dung load_rq1_trajectories) ===", flush=True)
    all_items = load_rq1_trajectories(verbose=False, include_v2_complexity=True)
    positive_items = [i for i in all_items if i.kind == "positive"]
    print(f"Positive: {len(positive_items)}", flush=True)

    print("\n=== Buoc D: tinh feature cho tap UNMATCHED (positive + unmatched negative) ===", flush=True)
    rows, meta_rows = [], []
    for item in positive_items:
        for spec, feats in extract_all_prefixes(item.trajectory, include_endpoint_context=False):
            feats = dict(feats)
            feats.pop("prefix_len", None)
            rows.append(feats)
            meta_rows.append({
                "trajectory_id": item.trajectory.trajectory_id, "source_id": item.source_id,
                "group_id": item.group_id, "kind": "positive", "chain": item.chain, "label": 1,
                "prefix_label": spec.label, "prefix_len": spec.length, "trajectory_len": len(item.trajectory),
            })
    for it in unmatched_items:
        traj = it["trajectory"]
        for spec, feats in extract_all_prefixes(traj, include_endpoint_context=False):
            feats = dict(feats)
            feats.pop("prefix_len", None)
            rows.append(feats)
            meta_rows.append({
                "trajectory_id": traj.trajectory_id, "source_id": it["source_id"], "group_id": it["group_id"],
                "kind": it["kind"], "chain": it["chain"], "label": 0,
                "prefix_label": spec.label, "prefix_len": spec.length, "trajectory_len": len(traj),
            })

    X_df = pd.DataFrame(rows).fillna(0.0)
    meta_df = pd.DataFrame(meta_rows)
    df_unmatched_raw = pd.concat([meta_df, X_df], axis=1)
    print(f"Tong {len(df_unmatched_raw)} prefix row (positive+unmatched-negative), truoc dedupe.", flush=True)

    (REPO_ROOT / "data" / "processed" / "e6_unmatched_negative_features.parquet").parent.mkdir(parents=True, exist_ok=True)
    df_unmatched_raw.to_parquet(REPO_ROOT / "data" / "processed" / "e6_unmatched_negative_features.parquet", index=False)

    df_unmatched = dedupe_pooled_prefixes(df_unmatched_raw)
    print(f"Sau dedupe_pooled_prefixes: {len(df_unmatched)} dong.", flush=True)
    n_groups_pos = df_unmatched[df_unmatched["label"] == 1]["group_id"].nunique()
    print(f"So group co positive: {n_groups_pos}/{len(positive_items)}", flush=True)

    feature_cols = [c for c in df_unmatched.columns if c not in META_COLS]
    X = df_unmatched[feature_cols]
    y = df_unmatched["label"]
    groups = df_unmatched["group_id"]

    print("\n=== Buoc E: evaluate_model_nested (M1) tren tap UNMATCHED ===", flush=True)
    result = evaluate_model_nested(M1TypedTemporalMotifModel, X, y, groups, target_fpr=0.01)
    for r in result["fold_rows"]:
        print(f"  held_out={r['held_out_group']:32s} n_val={r['n_val_rows']:4d} pr_auc={r['pr_auc']:.4f}", flush=True)
    oof = result["oof_prob"]
    valid = oof.notna()
    ci_unmatched = bootstrap_incident_level(y[valid].to_numpy(), oof[valid].to_numpy(), groups[valid].to_numpy(), pr_auc, n_boot=2000)
    per_inc_unmatched = per_incident_metric(y[valid].to_numpy(), oof[valid].to_numpy(), groups[valid].to_numpy(), pr_auc)
    print(f"\nMean PR-AUC (unmatched negative) = {ci_unmatched['point']:.4f} "
          f"[{ci_unmatched['ci_low']:.4f}, {ci_unmatched['ci_high']:.4f}]")

    # --- So sanh voi M1 tren matched hard-negative (oof_predictions_v1.csv co san) ---
    oof_matched_df = pd.read_csv(OOF_M1_FULL_PATH)
    y_m = oof_matched_df["label"].to_numpy()
    g_m = oof_matched_df["group_id"].to_numpy()
    p_m = oof_matched_df["oof_prob_M1"].to_numpy()
    ci_matched = bootstrap_incident_level(y_m, p_m, g_m, pr_auc, n_boot=2000)
    per_inc_matched = per_incident_metric(y_m, p_m, g_m, pr_auc)
    print(f"Mean PR-AUC (matched hard-negative, da co) = {ci_matched['point']:.4f} "
          f"[{ci_matched['ci_low']:.4f}, {ci_matched['ci_high']:.4f}]")

    common = sorted(set(per_inc_unmatched) & set(per_inc_matched))
    diffs = np.array([per_inc_unmatched[i] - per_inc_matched[i] for i in common])
    rng = np.random.default_rng(42)
    boot = np.array([rng.choice(diffs, size=len(diffs), replace=True).mean() for _ in range(2000)])
    diff_lo, diff_hi = np.percentile(boot, [2.5, 97.5])
    mean_diff = float(diffs.mean())
    try:
        _, wp = wilcoxon([per_inc_unmatched[i] for i in common], [per_inc_matched[i] for i in common])
    except ValueError:
        wp = float("nan")
    print(f"\nPaired diff (unmatched - matched) = {mean_diff:+.4f} [{diff_lo:+.4f}, {diff_hi:+.4f}], Wilcoxon p={wp}")

    summary = pd.DataFrame([
        {"eval_set": "matched_hard_negative", "mean_pr_auc": ci_matched["point"],
         "ci_low_95": ci_matched["ci_low"], "ci_high_95": ci_matched["ci_high"], "n_incidents": len(per_inc_matched)},
        {"eval_set": "unmatched_negative", "mean_pr_auc": ci_unmatched["point"],
         "ci_low_95": ci_unmatched["ci_low"], "ci_high_95": ci_unmatched["ci_high"], "n_incidents": len(per_inc_unmatched)},
    ])
    summary["paired_diff_vs_matched"] = [0.0, mean_diff]
    summary["paired_ci_low"] = [0.0, diff_lo]
    summary["paired_ci_high"] = [0.0, diff_hi]
    summary["wilcoxon_p"] = [np.nan, wp]
    OUT_TABLE.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(OUT_TABLE, index=False)
    print(f"\nDa luu {OUT_TABLE}")

    per_inc_df = pd.DataFrame(
        [{"eval_set": "matched", "incident_id": k, "pr_auc": v} for k, v in per_inc_matched.items()] +
        [{"eval_set": "unmatched", "incident_id": k, "pr_auc": v} for k, v in per_inc_unmatched.items()]
    )
    per_inc_df.to_csv(REPO_ROOT / "results" / "tables" / "robustness_per_incident.csv", index=False)

    md = [
        "# E6 — Robustness: hard-negative đã match vs \"unmatched negative\"\n",
        "\n**Gọi đúng tên \"unmatched negative\"** (không phải \"random\" tuyệt đối) — "
        "các candidate này vẫn đã tương tác với contract trong allowlist, chỉ không "
        "khớp tiêu chí cấu trúc/volume (`_passes_structural_filter`: fan_out≤3, không "
        "mixer bất thường, volume>0, tương tác trực tiếp). Nguồn: 505 candidate bị "
        f"reject đã có sẵn cache (Bước 0, `e6_gate_v1.md`) — dùng được {len(unmatched_items)}/"
        f"{len(candidates)} (còn lại trajectory rỗng khi build lại).\n",
        f"\n- Số group có positive trong tập unmatched: {n_groups_pos}/{len(positive_items)}\n",
        "\n## Kết quả\n",
        "\n| Eval set | Mean PR-AUC | 95% CI | n incident |\n|---|---|---|---|\n",
    ]
    for _, r in summary.iterrows():
        md.append(f"| {r['eval_set']} | {r['mean_pr_auc']:.4f} | [{r['ci_low_95']:.4f}, {r['ci_high_95']:.4f}] | {int(r['n_incidents'])} |\n")
    md += [
        f"\n**Paired diff (unmatched - matched) = {mean_diff:+.4f}, 95% bootstrap CI = "
        f"[{diff_lo:+.4f}, {diff_hi:+.4f}], Wilcoxon p={wp}**\n",
        "\n## Diễn giải\n",
    ]
    if mean_diff > 0 and diff_lo > 0:
        md.append("\n**KỲ VỌNG ĐÚNG (có ý nghĩa thống kê):** PR-AUC trên unmatched-negative cao hơn "
                   "matched hard-negative rõ rệt — bằng chứng cho thấy hard-negative mining (match "
                   "theo contract/fan-out/mixer/volume/độ dài) có giá trị thật: nó tạo ra bộ negative "
                   "khó phân biệt hơn nhiều so với candidate bị loại tự nhiên, không phải bước thừa.\n")
    elif mean_diff > 0:
        md.append("\nPR-AUC trên unmatched-negative cao hơn matched (đúng hướng kỳ vọng) nhưng CI "
                   "chứa 0 — chưa đủ bằng chứng thống kê với mẫu 11 incident, dù xu hướng đúng chiều.\n")
    else:
        # NGUOC ky vong ban dau - DA DIEU TRA nguyen nhan cu the (Tuan 9), tinh
        # LAI DONG (khong hardcode so cu) de van dung neu du lieu/ket qua doi
        # nho o lan chay khac - dam bao dien giai KHONG bi mat khi rerun
        # script (bug tai lap that phat hien Tuan 10: ban cu chi sua tay file
        # .md sau khi chay, bi script ghi de mat lai o lan rerun sau).
        feat_v2 = pd.read_parquet(FEATURES_V2_PATH)
        matched_100_fo = feat_v2[(feat_v2["kind"].isin(["hard_negative_mined", "hard_negative_mined_v2_complexity"])) &
                                  (feat_v2["prefix_label"] == "ratio_100")]["fan_out"]
        unmatched_100_fo = df_unmatched_raw[(df_unmatched_raw["label"] == 0) &
                                             (df_unmatched_raw["prefix_label"] == "ratio_100")]["fan_out"]
        md.append(
            "\n**NGƯỢC kỳ vọng ban đầu (PR-AUC unmatched THẤP HƠN matched) — đã điều tra, KHÔNG "
            "phải bug:** lý do reject chiếm đa số trong pool unmatched-negative là "
            "`fan_out_split_like_pattern` (`unique_dst > 3`, xem `_passes_structural_filter`). "
            "Khi build lại trajectory đầy đủ, so sánh đặc trưng cấu trúc thật:\n"
            f"\n| | fan_out mean | fan_out median | fan_out max |\n|---|---|---|---|\n"
            f"| Matched hard-negative (n={len(matched_100_fo)}) | {matched_100_fo.mean():.2f} | "
            f"{matched_100_fo.median():.0f} | {matched_100_fo.max():.0f} |\n"
            f"| Unmatched negative (n={len(unmatched_100_fo)}) | {unmatched_100_fo.mean():.2f} | "
            f"{unmatched_100_fo.median():.0f} | {unmatched_100_fo.max():.0f} |\n"
            "\nMatched hard-negative bị chặn ở fan_out≤3 gần như tuyệt đối (đúng tiêu chí mining) "
            "— trong khi unmatched-negative có đuôi phân phối dài hơn hẳn. Đây **chính là** loại "
            "hành vi \"phân tán/split\" (fan-out cao) mà motif/structural feature của M1 được thiết "
            "kế để coi là dấu hiệu đáng ngờ (rửa tiền thường phân tán qua nhiều địa chỉ). Vì vậy "
            "pool \"unmatched negative\" — dù bị loại vì KHÔNG khớp tiêu chí mining — lại vô tình "
            "bị lệch về phía các địa chỉ CÓ hành vi cấu trúc GIỐNG dấu hiệu rửa tiền hơn matched "
            "hard-negative, khiến M1 khó phân biệt hơn (không phải dễ hơn như kỳ vọng ban đầu).\n"
            "\n**Kết luận đã điều chỉnh:** kết quả này KHÔNG chứng minh \"hard-negative mining là "
            "bước thừa\", nhưng cũng KHÔNG phải bug — nó cho thấy tiêu chí `fan_out≤3` trong mining "
            "đang lọc bỏ đúng một nhóm địa chỉ có fan-out cao (có thể benign hoặc đáng ngờ chưa xác "
            "nhận) khỏi tập hard-negative, khiến tập hard-negative hiện tại \"sạch\"/đồng nhất hơn "
            "(fan-out thấp), còn tập bị loại lại KHÓ HƠN thực sự đối với M1. Đây là hạn chế đáng "
            "ghi nhận của tiêu chí mining hiện tại (chưa test được M1 trên entity fan-out cao NHƯNG "
            "benign) — xem thêm `results/reports/high_fanout_benign_probe.md` và "
            "`data/dataset_card.md` mục Giới hạn #12.\n"
        )
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("".join(md), encoding="utf-8")
    print(f"Da luu {OUT_MD}")


if __name__ == "__main__":
    main()
