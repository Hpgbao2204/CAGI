"""
Test bắt buộc: đảm bảo feature tại prefix k chỉ dùng event <= k,
và motif cần future event để xác nhận phải bị loại/đổi trạng thái "chưa hoàn tất".
Xem configs/features.yaml -> anti_leakage_rules.
"""
from datetime import datetime, timedelta, timezone

import pytest

from src.features.extractor import (
    extract_all_prefixes,
    extract_features,
    generate_prefixes,
)
from src.normalize.schema import CanonicalEvent
from src.trajectories.builder import Trajectory

CHAIN_ID = 1
BASE_TIME = datetime(2024, 1, 1, tzinfo=timezone.utc)
SEED = "0x" + "1" * 40


def _addr(n: int) -> str:
    return "0x" + str(n).zfill(40)


def _tx(n: int) -> str:
    return "0x" + str(n).zfill(64)


def _mk_event(i: int, minutes: int, src: str, dst: str, event_type: str, amount: float, token=None) -> CanonicalEvent:
    return CanonicalEvent(
        chain_id=CHAIN_ID,
        block_number=1000 + i,
        timestamp=BASE_TIME + timedelta(minutes=minutes),
        tx_hash=_tx(i),
        log_index=0,
        src=src,
        dst=dst,
        event_type=event_type,
        amount_norm=amount,
        token=token,
    )


def _make_trajectory(tail_events, tail_types=None) -> Trajectory:
    """10-action trajectory: 5 action đầu cố định, 5 action sau (tail) thay đổi
    được giữa các lần gọi để kiểm tra rằng features tại prefix=5 không đổi.
    """
    a0 = _addr(1)  # seed
    a1, a2, a3, a4, a5 = _addr(2), _addr(3), _addr(4), _addr(5), _addr(6)

    actions = [
        _mk_event(0, 0, a0, a1, "transfer", 5.0, token="usdc"),
        _mk_event(1, 10, a1, a2, "bridge_deposit", 4.8, token="usdc"),
        _mk_event(2, 20, a2, a3, "bridge_withdraw", 4.7, token="usdc"),
        _mk_event(3, 30, a3, a4, "swap", 4.5, token="eth"),
        _mk_event(4, 40, a4, a5, "transfer", 4.4, token="eth"),
    ]
    actions.extend(tail_events(a5))

    traj = Trajectory(trajectory_id="t1", seed_address=a0, actions=actions)
    return traj


def _tail_variant_a(a5):
    a6, a7 = _addr(7), _addr(8)
    return [
        _mk_event(5, 50, a5, a6, "swap", 4.0, token="usdc"),
        _mk_event(6, 60, a6, a7, "split", 2.0, token="usdc"),
        _mk_event(7, 60, a6, _addr(9), "split", 2.0, token="usdc"),
        _mk_event(8, 70, a7, _addr(10), "mixer_or_exit", 1.9, token="usdc"),
        _mk_event(9, 80, a7, _addr(11), "transfer", 0.5, token="usdc"),
    ]


def _tail_variant_b(a5):
    # Hoàn toàn khác variant A: khác event_type, khác amount, khác token,
    # khác cấu trúc (không split/mixer) — nếu prefix=5 leak, feature sẽ khác.
    a6 = _addr(20)
    return [
        _mk_event(5, 500, a5, a6, "transfer", 0.1, token="dai"),
        _mk_event(6, 900, a6, _addr(21), "other", 0.01, token="dai"),
        _mk_event(7, 1200, a6, _addr(22), "other", 0.01, token="dai"),
        _mk_event(8, 1500, _addr(21), _addr(23), "transfer", 0.01, token="dai"),
        _mk_event(9, 1800, _addr(22), _addr(24), "transfer", 0.01, token="dai"),
    ]


def test_features_at_prefix_identical_regardless_of_future_actions():
    traj_a = _make_trajectory(_tail_variant_a)
    traj_b = _make_trajectory(_tail_variant_b)

    feats_a = extract_features(traj_a, prefix_len=5, include_endpoint_context=True)
    feats_b = extract_features(traj_b, prefix_len=5, include_endpoint_context=True)

    assert feats_a == feats_b, "Feature tại prefix=5 không được phụ thuộc action 6-10"


def test_features_at_prefix_independent_of_future_trajectory_length():
    """Bat leak kieu prefix_ratio = k/n (Todo T4): hai trajectory co CUNG 5
    action dau nhung DO DAI tail khac nhau (1 vs 5 action) phai cho feature
    giong het nhau tai prefix=5 — do dai cuoi cung chi biet sau khi dong
    tien ket thuc."""
    traj_long = _make_trajectory(_tail_variant_a)
    traj_short = _make_trajectory(lambda a5: _tail_variant_a(a5)[:1])
    assert len(traj_long) != len(traj_short)

    feats_long = extract_features(traj_long, prefix_len=5)
    feats_short = extract_features(traj_short, prefix_len=5)

    assert feats_long == feats_short, "Feature tai prefix=5 khong duoc phu thuoc do dai trajectory cuoi cung"


def test_prefix_only_reads_events_up_to_k():
    traj = _make_trajectory(_tail_variant_a)
    for k in [2, 3, 5, 7, 10]:
        feats = extract_features(traj, prefix_len=k)
        # action_count tổng phải <= k (không đếm được action ngoài prefix)
        # Loại "_ratio" (bản chuẩn hóa theo prefix_len, thêm Tuần 5 sửa
        # shortcut độ dài) — chỉ tổng bản THÔ mới phải khớp đúng prefix_len.
        action_count_keys = [key for key in feats if key.startswith("action_count_") and not key.endswith("_ratio")]
        total_counted = sum(feats[key] for key in action_count_keys)
        assert total_counted == k, f"prefix={k}: tổng action_count phải đúng bằng {k}, được {total_counted}"


def test_prefix_len_cannot_exceed_trajectory_length():
    traj = _make_trajectory(_tail_variant_a)
    with pytest.raises(ValueError):
        extract_features(traj, prefix_len=len(traj) + 1)


def test_incomplete_motif_not_counted_before_future_event():
    """Motif `split` cần 2 outgoing edges đã QUAN SÁT ĐƯỢC trong prefix.
    Tại prefix=7 (chỉ 1 trong 2 nhánh split xuất hiện, event index 6),
    motif_split phải là 0 (chưa hoàn tất); chỉ tại prefix=8 (cả 2 nhánh split
    event index 6,7 đã có trong prefix) motif_split mới được tính là hoàn
    tất (>=1).
    """
    traj = _make_trajectory(_tail_variant_a)
    feats_before = extract_features(traj, prefix_len=7)  # chỉ có 1 nhánh split (event index 6)
    feats_after = extract_features(traj, prefix_len=8)  # cả 2 nhánh split (event index 6,7)

    assert feats_before["motif_split"] == 0.0
    assert feats_after["motif_split"] >= 1.0


def test_endpoint_context_excluded_by_default_for_early_detection():
    traj = _make_trajectory(_tail_variant_a)
    feats = extract_features(traj, prefix_len=len(traj), include_endpoint_context=False)
    assert "known_mixer_interaction" not in feats
    assert "public_exit_service_label" not in feats

    feats_full = extract_features(traj, prefix_len=len(traj), include_endpoint_context=True)
    assert feats_full["known_mixer_interaction"] == 1.0  # mixer_or_exit xuất hiện ở action 8


def test_token_category_diversity_excludes_dust_tokens():
    """Sua bug Tuan 11 (results/reports/token_category_diversity_fix_v1.md):
    token_category_diversity (feature CHINH THUC) truoc day dem MOI token
    phan biet, khong loc dust - sua thanh chi dem token co value share
    >=1% tong inflow that."""
    seed = _addr(1)
    actions = [
        _mk_event(0, 0, seed, _addr(2), "transfer", 10.0, token="usdc"),  # gia tri lon
    ]
    for i in range(1, 6):
        actions.append(_mk_event(i, i, seed, _addr(2 + i), "transfer", 0.0001, token=f"dust_{i}"))
    traj = Trajectory(trajectory_id="t_dust", seed_address=seed, actions=actions)
    feats = extract_features(traj, prefix_len=len(traj))
    assert feats["token_category_diversity"] == 1.0, "5 token dust (gop lai <1% tong gia tri) phai bi loc"


def test_generate_prefixes_covers_ratios_and_k_values():
    traj = _make_trajectory(_tail_variant_a)  # 10 actions
    specs = generate_prefixes(traj, ratios=(0.25, 0.5, 0.75, 1.0), k_values=(2, 3, 5, 7))
    lengths = {s.length for s in specs}
    assert lengths == {2, 3, 5, 7, 8, 10}  # ceil(10*0.25)=3 collide with k=3; ceil(10*0.75)=8
    for s in specs:
        assert 1 <= s.length <= len(traj)

    # Sau khi sửa bug (Tuần 7): length trùng nhau (3 và 5) không còn bị
    # "nuốt" nhãn — cả 2 nhãn (ratio_25/k_3 và ratio_50/k_5) đều phải xuất
    # hiện, mỗi nhãn 1 dòng riêng dù cùng length.
    labels_by_length = {}
    for s in specs:
        labels_by_length.setdefault(s.length, set()).add(s.label)
    assert labels_by_length[3] == {"ratio_25", "k_3"}
    assert labels_by_length[5] == {"ratio_50", "k_5"}
    assert len(specs) == 8  # 4 ratio + 4 k, không mất nhãn nào dù trùng length


def test_generate_prefixes_short_trajectory_always_has_ratio_100():
    """Bug đã sửa (Tuần 7, xem rq2_ratio100_diagnostic.md): trajectory ngắn
    hơn 4 action trước đây KHÔNG BAO GIỜ có dòng ratio_100 (bị nuốt vào
    ratio_25/50/75) — bất biến bắt buộc: mọi trajectory, bất kể độ dài, đều
    phải có đúng 1 dòng ratio_100 với length == độ dài đầy đủ.
    """
    full_traj = _make_trajectory(_tail_variant_a)  # 10 actions
    for n in (1, 2, 3, 4, 10):
        actions = full_traj.actions[:n]
        traj = Trajectory(trajectory_id=f"short_{n}", seed_address=_addr(1), actions=actions)
        assert len(traj) == n

        specs = generate_prefixes(traj)
        ratio_100_specs = [s for s in specs if s.label == "ratio_100"]
        assert len(ratio_100_specs) == 1, f"n={n}: phai co dung 1 dong ratio_100"
        assert ratio_100_specs[0].length == n, f"n={n}: ratio_100 phai co length == {n}"

        # Bat bien chong leakage cu van phai giu nguyen: moi dong chi doc
        # dung {length} action dau tien, khong doc vuot qua.
        feats = extract_features(traj, prefix_len=n)
        action_count_keys = [k for k in feats if k.startswith("action_count_") and not k.endswith("_ratio")]
        assert sum(feats[k] for k in action_count_keys) == n


def test_extract_all_prefixes_each_prefix_bounded():
    traj = _make_trajectory(_tail_variant_a)
    results = extract_all_prefixes(traj)
    for spec, feats in results:
        # Loại "_ratio" (bản chuẩn hóa theo prefix_len, thêm Tuần 5 sửa
        # shortcut độ dài) — chỉ tổng bản THÔ mới phải khớp đúng prefix_len.
        action_count_keys = [key for key in feats if key.startswith("action_count_") and not key.endswith("_ratio")]
        assert sum(feats[key] for key in action_count_keys) == spec.length
