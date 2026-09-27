"""
Test cho bounded value-flow trajectory builder (Bước 4), dùng dữ liệu
synthetic từ tests/fixtures/synthetic_trajectories.py.
"""
import math
from datetime import datetime, timedelta, timezone

from src.normalize.schema import CanonicalEvent
from src.trajectories.builder import TrajectoryConfig, build_trajectory
from tests.fixtures.synthetic_trajectories import build_synthetic_dataset

CONFIG = TrajectoryConfig(max_depth=6, time_horizon_hours=72, min_tainted_share=0.05)


def test_positive_trajectory_includes_bridge_swap_split_mixer():
    dataset = build_synthetic_dataset()
    pos = next(d for d in dataset if d["label"] == 1)
    traj = build_trajectory(
        pos["events"], pos["seed"], CONFIG, incident_id=pos["incident_id"], label=pos["label"]
    )
    event_types = {a.event_type for a in traj.actions}
    assert {"bridge_deposit", "swap", "split", "mixer_or_exit"} <= event_types
    assert len(traj) == len(pos["events"])  # tất cả event nên được giữ (tainted share cao)


def test_negative_trajectory_builds_without_mixer():
    dataset = build_synthetic_dataset()
    neg = next(d for d in dataset if d["label"] == 0)
    traj = build_trajectory(
        neg["events"], neg["seed"], CONFIG, incident_id=neg["incident_id"], label=neg["label"]
    )
    event_types = {a.event_type for a in traj.actions}
    assert "mixer_or_exit" not in event_types
    assert len(traj) > 0


def test_max_depth_bounds_expansion():
    dataset = build_synthetic_dataset()
    pos = next(d for d in dataset if d["label"] == 1)
    tight_config = TrajectoryConfig(max_depth=1, time_horizon_hours=72, min_tainted_share=0.05)
    traj = build_trajectory(pos["events"], pos["seed"], tight_config)
    # max_depth=1: chỉ event có src == seed (depth 0) được chấp nhận
    assert all(a.src == traj.seed_address for a in traj.actions)


def test_time_horizon_bounds_expansion():
    dataset = build_synthetic_dataset()
    pos = next(d for d in dataset if d["label"] == 1)
    tight_config = TrajectoryConfig(max_depth=6, time_horizon_hours=0.1, min_tainted_share=0.05)
    traj = build_trajectory(pos["events"], pos["seed"], tight_config)
    assert len(traj) < len(pos["events"])


def test_bridge_links_have_confidence():
    dataset = build_synthetic_dataset()
    pos = next(d for d in dataset if d["label"] == 1)
    traj = build_trajectory(pos["events"], pos["seed"], CONFIG)
    assert len(traj.bridge_links) >= 1
    for link in traj.bridge_links:
        assert 0.0 <= link.confidence <= 1.0


def test_actions_sorted_chronologically():
    dataset = build_synthetic_dataset()
    pos = next(d for d in dataset if d["label"] == 1)
    traj = build_trajectory(pos["events"], pos["seed"], CONFIG)
    timestamps = [a.timestamp for a in traj.actions]
    assert timestamps == sorted(timestamps)


def test_full_synthetic_dataset_builds_without_error():
    dataset = build_synthetic_dataset()
    for item in dataset:
        traj = build_trajectory(
            item["events"], item["seed"], CONFIG, incident_id=item["incident_id"], label=item["label"]
        )
        assert len(traj) > 0


def _addr(n: int) -> str:
    return "0x" + str(n).zfill(40)


def _tx(n: int) -> str:
    return "0x" + str(n).zfill(64)


def _mk_event(idx, minutes, src, dst, event_type, amount, token="ETH"):
    return CanonicalEvent(
        chain_id=1,
        block_number=1000 + idx,
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=minutes),
        tx_hash=_tx(idx),
        log_index=0,
        src=src,
        dst=dst,
        event_type=event_type,
        amount_norm=amount,
        token=token,
    )


def test_does_not_expand_frontier_through_allowlisted_mixer():
    """Regression test (bug thật FEG Bridge 2026-08-13): mixer trong
    allowlist PHẢI được chấp nhận vào trajectory (endpoint), nhưng KHÔNG
    được dùng làm src để tiếp tục mở rộng — nếu không, giao dịch của
    NGƯỜI DÙNG KHÁC đi qua cùng mixer sẽ lẫn vào trajectory.
    """
    seed = _addr(1)
    mixer = _addr(2)
    unrelated_victim_output = _addr(3)  # rút tiền của người dùng KHÁC qua cùng mixer

    events = [
        _mk_event(0, 0, seed, mixer, "mixer_or_exit", 3.0),
        # Giao dịch này có src=mixer (không phải seed) — thuộc về người
        # dùng khác của cùng mixer, KHÔNG được lẫn vào trajectory của seed.
        _mk_event(1, 5, mixer, unrelated_victim_output, "transfer", 5.0),
    ]
    config = TrajectoryConfig(max_depth=6, time_horizon_hours=72, min_tainted_share=0.05, mixer_allowlist=(mixer,))
    traj = build_trajectory(events, seed, config)

    dsts = {a.dst for a in traj.actions}
    assert mixer in dsts  # mixer event PHẢI có mặt (endpoint hợp lệ)
    assert unrelated_victim_output not in dsts  # KHÔNG được trace tiếp qua mixer
    assert mixer not in traj.node_depth  # mixer KHÔNG được thêm vào node_depth


def test_value_share_computed_per_token_not_pooled_across_tokens():
    """Regression test (bug thật Radiant Capital 2026-08-27): outflow_by_src
    trước đây cộng dồn raw value của NHIỀU TOKEN KHÁC NHAU (ETH+ARB+WBTC+
    USDC...) vào 1 mẫu số chung — đơn vị thô không tương thích giữa các
    token khác nhau (11,977 "ETH" so với hàng trăm nghìn "ARB"/"WBTC" ở đơn
    vị token thô không quy đổi USD). Hệ quả: 1 giao dịch outbound ETH thật,
    chiếm gần như toàn bộ giá trị outbound thật theo đúng đơn vị ETH, có thể
    bị tính value_share thấp giả tạo và bị loại oan nếu seed có nhiều hoạt
    động token khác (ARB/WBTC/USDC) với số lượng thô lớn hơn.

    Fix: mẫu số PHẢI tính riêng theo từng (src, token) — value_share của
    giao dịch ETH chỉ so với tổng outflow ETH của seed, không so với tổng
    gộp mọi token.
    """
    seed = _addr(1)
    dst_eth = _addr(2)  # EOA thường, KHÔNG nằm trong allowlist
    pool_a, pool_b = _addr(3), _addr(4)

    events = [
        # Nhiều swap nhỏ ra token khác, số lượng RAW lớn (vd ARB có nhiều
        # decimal/số lượng token thô lớn) -> nếu cộng dồn chung mẫu số sẽ
        # áp đảo giao dịch ETH thật bên dưới.
        _mk_event(0, 0, seed, pool_a, "swap", math.log1p(200_000), token="ARB"),
        _mk_event(1, 1, seed, pool_b, "swap", math.log1p(150_000), token="WBTC_RAW_UNITS"),
        # Giao dịch ETH thật, chiếm ~100% outflow ETH của seed (chỉ có 1
        # giao dịch ETH) nhưng chỉ ~0.03% nếu so với tổng gộp mọi token.
        _mk_event(2, 2, seed, dst_eth, "transfer", math.log1p(100.0), token="ETH"),
    ]
    config = TrajectoryConfig(max_depth=6, time_horizon_hours=72, min_tainted_share=0.05)
    traj = build_trajectory(events, seed, config)

    dsts = {a.dst for a in traj.actions}
    assert dst_eth in dsts, (
        "Giao dịch ETH thật (100% outflow ETH) bị loại oan do mẫu số gộp "
        "chung với ARB/WBTC — value_share phải tính riêng theo từng token."
    )


def test_does_not_expand_frontier_through_allowlisted_dex_router():
    """Cùng bug áp dụng cho DEX router dùng chung (bug thật QBridge
    2026-08-13): router trong allowlist là endpoint, không phải hop.
    """
    seed = _addr(1)
    router = _addr(2)
    unrelated_other_user = _addr(3)

    events = [
        _mk_event(0, 0, seed, router, "transfer", 3.0),
        _mk_event(1, 5, router, unrelated_other_user, "transfer", 5.0),
    ]
    config = TrajectoryConfig(max_depth=6, time_horizon_hours=72, min_tainted_share=0.05, dex_allowlist=(router,))
    traj = build_trajectory(events, seed, config)

    dsts = {a.dst for a in traj.actions}
    assert router in dsts
    assert unrelated_other_user not in dsts
    assert router not in traj.node_depth
