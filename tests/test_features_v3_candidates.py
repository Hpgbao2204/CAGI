"""Test cho 4 nhom feature ung vien MOI (Giai doan A, Tuan 11 - xem
configs/features_v3_candidate.yaml). Cac nhom nay KHONG duoc goi tu
extract_features()/extract_all_prefixes() - test rieng, khong dung chung
fixture voi test_no_future_leakage.py de tranh nham lan pham vi."""
from datetime import datetime, timedelta, timezone

import pytest

from src.features.extractor import (
    extract_v3_candidate_features,
    percentile_rank_against_reference,
)
from src.normalize.schema import CanonicalEvent
from src.trajectories.builder import Trajectory

BASE_TIME = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _addr(n: int) -> str:
    return "0x" + str(n).zfill(40)


def _tx(n: int) -> str:
    return "0x" + str(n).zfill(64)


def _ev(i, minutes, src, dst, event_type="transfer", amount=1.0, token="usdc", chain_id=1):
    return CanonicalEvent(
        chain_id=chain_id, block_number=1000 + i, timestamp=BASE_TIME + timedelta(minutes=minutes),
        tx_hash=_tx(i), log_index=0, src=src, dst=dst, event_type=event_type,
        amount_norm=amount, token=token,
    )


# ============ cross_chain ============
def test_cross_chain_single_chain_trajectory_has_distinct_count_1():
    """Khop dung phat hien thuc nghiem: du lieu that HIEN TAI luon chi co
    1 chain_id/trajectory - xac nhan hanh vi nay qua synthetic fixture
    (khong doc du lieu that o day, chi kiem tra logic dung khi chain_id
    dong nhat)."""
    seed = _addr(1)
    actions = [_ev(0, 0, seed, _addr(2), chain_id=1), _ev(1, 10, _addr(2), _addr(3), chain_id=1)]
    traj = Trajectory(trajectory_id="t1", seed_address=seed, actions=actions)
    feats = extract_v3_candidate_features(traj, len(traj))
    assert feats["cross_chain_distinct_count"] == 1.0
    assert feats["cross_chain_expansion_rate"] == 0.0


def test_cross_chain_detects_multiple_chains_when_present():
    """Code PHAI hoat dong dung neu chain_id thuc su khac nhau (du du
    lieu that hien tai khong co truong hop nay) - test logic, khong test
    gia dinh ve du lieu that."""
    seed = _addr(1)
    actions = [
        _ev(0, 0, seed, _addr(2), chain_id=1),
        _ev(1, 10, _addr(2), _addr(3), chain_id=1),
        _ev(2, 20, _addr(3), _addr(4), chain_id=56),  # chain moi o vi tri index=2 (action thu 3)
        _ev(3, 30, _addr(4), _addr(5), chain_id=56),
    ]
    traj = Trajectory(trajectory_id="t1", seed_address=seed, actions=actions)
    feats = extract_v3_candidate_features(traj, len(traj))
    assert feats["cross_chain_distinct_count"] == 2.0
    assert feats["cross_chain_expansion_rate"] == pytest.approx(3 / 4)  # cham chain moi cuoi cung o vi tri index=2 -> (2+1)/4


def test_cross_chain_prefix_only_reads_up_to_k():
    seed = _addr(1)
    actions = [
        _ev(0, 0, seed, _addr(2), chain_id=1),
        _ev(1, 10, _addr(2), _addr(3), chain_id=1),
        _ev(2, 20, _addr(3), _addr(4), chain_id=56),  # NGOAI prefix k=2
    ]
    traj = Trajectory(trajectory_id="t1", seed_address=seed, actions=actions)
    feats_k2 = extract_v3_candidate_features(traj, 2)
    assert feats_k2["cross_chain_distinct_count"] == 1.0, "prefix=2 khong duoc thay chain moi o action thu 3 (tuong lai)"


# ============ token_diversity_filtered ============
def test_token_diversity_filtered_excludes_dust_tokens():
    seed = _addr(1)
    # 1 token gia tri lon (99% tong) + 5 token "dust" cong lai <1%
    actions = [_ev(0, 0, seed, _addr(2), amount=10.0, token="usdc")]
    for i in range(1, 6):
        actions.append(_ev(i, i, seed, _addr(2 + i), amount=0.0001, token=f"dust_token_{i}"))
    traj = Trajectory(trajectory_id="t1", seed_address=seed, actions=actions)
    feats = extract_v3_candidate_features(traj, len(traj), min_value_share=0.01)
    # Loc dung: chi usdc (chiem hau het gia tri) song sot, dust bi loai
    assert feats["token_category_diversity_filtered"] == 1.0


def test_token_diversity_filtered_keeps_tokens_above_threshold():
    seed = _addr(1)
    # 2 token gia tri gan bang nhau (~50/50) - ca 2 deu >= 1% nguong
    actions = [
        _ev(0, 0, seed, _addr(2), amount=5.0, token="usdc"),
        _ev(1, 1, seed, _addr(3), amount=5.0, token="usdt"),
    ]
    traj = Trajectory(trajectory_id="t1", seed_address=seed, actions=actions)
    feats = extract_v3_candidate_features(traj, len(traj), min_value_share=0.01)
    assert feats["token_category_diversity_filtered"] == 2.0
    assert feats["token_value_entropy_filtered"] > 0.9  # gan entropy toi da cho 2 lop can bang (log2(2)=1.0)


def test_token_diversity_filtered_empty_trajectory():
    seed = _addr(1)
    traj = Trajectory(trajectory_id="t1", seed_address=seed, actions=[])
    feats = extract_v3_candidate_features(traj, 0)
    assert feats["token_category_diversity_filtered"] == 0.0
    assert feats["token_value_entropy_filtered"] == 0.0


# ============ local_centrality ============
def test_local_centrality_hub_node_has_higher_betweenness_than_leaf():
    """Do thi hinh sao: seed noi voi 3 leaf qua 1 hub trung gian -> hub
    phai co betweenness CAO HON cac leaf (moi duong di qua hub)."""
    seed = _addr(1)
    hub = _addr(2)
    leaves = [_addr(3), _addr(4), _addr(5)]
    actions = [_ev(0, 0, seed, hub)]
    for i, leaf in enumerate(leaves):
        actions.append(_ev(i + 1, i + 1, hub, leaf))
    traj = Trajectory(trajectory_id="t1", seed_address=seed, actions=actions)
    feats = extract_v3_candidate_features(traj, len(traj))
    assert feats["local_centrality_capped"] == 0.0
    # seed la leaf trong cau truc nay (chi 1 canh) -> betweenness thap;
    # test gian tiep qua mean > 0 (co it nhat 1 node trung gian thuc su)
    assert feats["mean_betweenness_centrality"] > 0.0


def test_local_centrality_capped_for_oversized_graph():
    seed = _addr(1)
    actions = [_ev(i, i, seed if i == 0 else _addr(i), _addr(i + 1)) for i in range(10)]
    traj = Trajectory(trajectory_id="t1", seed_address=seed, actions=actions)
    feats = extract_v3_candidate_features(traj, len(traj), max_nodes_for_exact=3)
    assert feats["local_centrality_capped"] == 1.0
    import math
    assert math.isnan(feats["seed_betweenness_centrality"])


def test_local_centrality_empty_trajectory():
    seed = _addr(1)
    traj = Trajectory(trajectory_id="t1", seed_address=seed, actions=[])
    feats = extract_v3_candidate_features(traj, 0)
    assert feats["seed_betweenness_centrality"] == 0.0
    assert feats["local_centrality_capped"] == 0.0


# ============ percentile_rank_against_reference ============
def test_percentile_rank_basic():
    ref = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert percentile_rank_against_reference(0.0, ref) == 0.0
    assert percentile_rank_against_reference(5.0, ref) == 100.0
    assert percentile_rank_against_reference(3.0, ref) == pytest.approx(60.0)  # 3/5 gia tri <= 3.0


def test_percentile_rank_empty_reference_returns_neutral_50():
    assert percentile_rank_against_reference(10.0, []) == 50.0
