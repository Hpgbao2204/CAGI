"""
Feature extractor — xem configs/features.yaml -> feature_groups, anti_leakage_rules.

Nguyên tắc bắt buộc: mọi feature tại prefix k CHỈ được tính từ
`trajectory.actions[:k]` (k action đầu tiên theo thời gian). Không hàm nào
trong module này được phép đọc `trajectory.actions[k:]`.

context group (`known_mixer_interaction`, `public_exit_service_label`,
`protocol_category`) liên quan tới endpoint — theo anti_leakage_rules,
2 feature đầu tiên PHẢI bị loại khi mục tiêu là cảnh báo trước endpoint
(early detection). Mặc định `include_endpoint_context=False`.
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from src.normalize.schema import CanonicalEvent
from src.trajectories.builder import Trajectory

KNOWN_MIXER_TYPES = {"mixer_or_exit"}


@dataclass(frozen=True)
class PrefixSpec:
    label: str  # vd "ratio_25", "k_5"
    length: int  # số action đầu tiên được giữ lại


def generate_prefixes(
    trajectory: Trajectory,
    ratios: Sequence[float] = (0.25, 0.5, 0.75, 1.0),
    k_values: Sequence[int] = (2, 3, 5, 7),
) -> List[PrefixSpec]:
    """Sinh danh sách prefix (theo tỉ lệ % và theo số action k cố định).

    QUAN TRỌNG (sửa bug Tuần 7 - xem results/reports/rq2_ratio100_diagnostic.md):
    với trajectory NGẮN, nhiều mốc ratio (và có thể cả k) có thể tính ra
    CÙNG một độ dài nguyên (vd trajectory 3 action: ratio_75 và ratio_100
    đều = độ dài 3). Bản cũ dùng `specs.setdefault()` nên chỉ giữ nhãn xử lý
    ĐẦU TIÊN (luôn là ratio nhỏ hơn, vì duyệt 0.25→0.5→0.75→1.0) — hệ quả:
    trajectory ngắn hơn 4 action KHÔNG BAO GIỜ có dòng nhãn `ratio_100`,
    thiên lệch có hệ thống loại bỏ toàn bộ trajectory ngắn khỏi mốc 100%.

    Sửa: một độ dài có thể mang NHIỀU nhãn — sinh 1 PrefixSpec/nhãn (cùng
    length thì feature giống hệt nhau, nhưng mỗi bucket prefix_label vẫn có
    đúng 1 dòng đại diện cho mọi trajectory, kể cả trajectory rất ngắn).
    Bất biến bắt buộc: mọi trajectory luôn có 1 dòng nhãn "ratio_100" với
    length == len(trajectory) (chính là prefix đầy đủ).
    """
    n = len(trajectory)
    length_labels: Dict[int, List[str]] = {}

    for r in ratios:
        length = max(1, math.ceil(n * r))
        length = min(length, n)
        label = f"ratio_{int(r * 100)}"
        length_labels.setdefault(length, []).append(label)

    for k in k_values:
        if 0 < k <= n:
            length_labels.setdefault(k, []).append(f"k_{k}")

    specs = [
        PrefixSpec(label=label, length=length)
        for length in sorted(length_labels)
        for label in length_labels[length]
    ]
    assert any(s.label == "ratio_100" and s.length == n for s in specs), (
        f"Bat bien vi pham: trajectory do dai {n} phai co dong nhan ratio_100 "
        f"voi length == {n}"
    )
    return specs


def _prefix_actions(trajectory: Trajectory, prefix_len: int) -> List[CanonicalEvent]:
    if prefix_len < 0 or prefix_len > len(trajectory):
        raise ValueError("prefix_len ngoài phạm vi số action của trajectory")
    return trajectory.actions[:prefix_len]  # CHỈ index < prefix_len — không đọc future


def _temporal_features(actions: List[CanonicalEvent]) -> Dict[str, float]:
    if not actions:
        return {
            "time_to_first_bridge": -1.0,
            "inter_action_gap_mean": 0.0,
            "inter_action_gap_std": 0.0,
            "burstiness": 0.0,
            "active_duration_sec": 0.0,
        }
    t0 = actions[0].timestamp
    gaps = [
        (actions[i].timestamp - actions[i - 1].timestamp).total_seconds()
        for i in range(1, len(actions))
    ]
    bridge_ts = [a.timestamp for a in actions if a.event_type in ("bridge_deposit", "bridge_withdraw")]
    time_to_first_bridge = (bridge_ts[0] - t0).total_seconds() if bridge_ts else -1.0

    gap_mean = sum(gaps) / len(gaps) if gaps else 0.0
    if len(gaps) >= 2:
        variance = sum((g - gap_mean) ** 2 for g in gaps) / len(gaps)
        gap_std = math.sqrt(variance)
    else:
        gap_std = 0.0
    # burstiness (Goh-Barabasi): (std - mean) / (std + mean), 0 nếu không xác định
    burstiness = (gap_std - gap_mean) / (gap_std + gap_mean) if (gap_std + gap_mean) > 0 else 0.0
    active_duration = (actions[-1].timestamp - t0).total_seconds()

    return {
        "time_to_first_bridge": float(time_to_first_bridge),
        "inter_action_gap_mean": float(gap_mean),
        "inter_action_gap_std": float(gap_std),
        "burstiness": float(burstiness),
        "active_duration_sec": float(active_duration),
    }


def _structural_features(actions: List[CanonicalEvent], seed_address: str) -> Dict[str, float]:
    if not actions:
        return {
            "fan_out": 0.0,
            "fan_in": 0.0,
            "unique_counterparties": 0.0,
            "local_ego_density": 0.0,
            "path_depth": 0.0,
            "branch_count": 0.0,
        }
    out_edges = Counter((a.src, a.dst) for a in actions)
    fan_out = len({a.dst for a in actions if a.src == seed_address})
    fan_in = len({a.src for a in actions if a.dst == seed_address})
    nodes = {a.src for a in actions} | {a.dst for a in actions}
    unique_counterparties = len(nodes - {seed_address})

    n_nodes = len(nodes)
    possible_edges = n_nodes * (n_nodes - 1) if n_nodes > 1 else 1
    local_ego_density = len(out_edges) / possible_edges if possible_edges else 0.0

    # path_depth: số hop lớn nhất từ seed dựa trên thứ tự thời gian của action
    # (chỉ dùng actions đã có trong prefix -> không leak).
    depth: Dict[str, int] = {seed_address: 0}
    for a in actions:
        if a.src in depth:
            d = depth[a.src] + 1
            if a.dst not in depth or depth[a.dst] > d:
                depth[a.dst] = d
    path_depth = max(depth.values()) if depth else 0

    out_degree = Counter(a.src for a in actions)
    branch_count = sum(1 for v in out_degree.values() if v > 1)

    return {
        "fan_out": float(fan_out),
        "fan_in": float(fan_in),
        "unique_counterparties": float(unique_counterparties),
        "local_ego_density": float(local_ego_density),
        "path_depth": float(path_depth),
        "branch_count": float(branch_count),
    }


def _economic_features(actions: List[CanonicalEvent], min_token_value_share: float = 0.01) -> Dict[str, float]:
    if not actions:
        return {
            "log_amount_mean": 0.0,
            "outgoing_incoming_ratio": 0.0,
            "value_retention": 0.0,
            "token_category_diversity": 0.0,
        }
    amounts = [abs(a.amount_norm) for a in actions]
    log_amounts = [math.log1p(x) for x in amounts]
    log_amount_mean = sum(log_amounts) / len(log_amounts)

    total_in = sum(amounts)  # amount_norm đã chuẩn hóa (log/ratio), coi mọi action là "flow"
    total_out = sum(a.amount_norm for a in actions if a.event_type != "merge")
    outgoing_incoming_ratio = (total_out / total_in) if total_in > 0 else 0.0

    value_retention = (amounts[-1] / amounts[0]) if amounts[0] > 0 else 0.0

    # token_category_diversity — SỬA BUG Tuần 11 (xem
    # results/reports/token_category_diversity_fix_v1.md): bản CŨ đếm MỌI
    # token phân biệt (`len({a.token for a in actions if a.token})`),
    # KHÔNG lọc theo value share — bị dust/spam token thổi phồng diversity
    # giả tạo (tài liệu gốc mục 3.9 đã cảnh báo đúng vấn đề này, nhưng chưa
    # được implement đúng cho tới giờ). Sửa: CHỈ đếm token có value share
    # >= `min_token_value_share` (mặc định 1%) trên TỔNG inflow THẬT — dùng
    # RAW value qua `math.expm1` (KHÔNG cộng dồn trực tiếp trên
    # `amount_norm` log-scale — cộng dồn log-scale trực tiếp là bug toán
    # học đã biết trước trong dự án, xem src/trajectories/builder.py::_raw_value).
    value_by_token: Dict[str, float] = {}
    total_token_value = 0.0
    for a in actions:
        if not a.token:
            continue
        raw_v = math.expm1(abs(a.amount_norm))
        value_by_token[a.token] = value_by_token.get(a.token, 0.0) + raw_v
        total_token_value += raw_v
    if total_token_value > 0:
        token_category_diversity = float(
            sum(1 for v in value_by_token.values() if v / total_token_value >= min_token_value_share)
        )
    else:
        token_category_diversity = 0.0

    return {
        "log_amount_mean": float(log_amount_mean),
        "outgoing_incoming_ratio": float(outgoing_incoming_ratio),
        "value_retention": float(value_retention),
        "token_category_diversity": float(token_category_diversity),
    }


def _semantic_action_features(actions: List[CanonicalEvent]) -> Dict[str, float]:
    type_counts = Counter(a.event_type for a in actions)
    all_types = [
        "transfer", "bridge_deposit", "bridge_withdraw", "lending_deposit", "lending_withdraw",
        "swap", "split", "merge", "mixer_or_exit", "other",
    ]
    n = len(actions)
    feats = {f"action_count_{t}": float(type_counts.get(t, 0)) for t in all_types}
    # Ban chuan hoa theo prefix_len (Tuan 5, sua shortcut do dai — xem
    # results/reports/leakage_audit_v1_findings.md): action_count_* thô
    # tương quan TUYỆT ĐỐI (pearson r=1.000) với prefix_len vì tổng của
    # chúng CHÍNH LÀ prefix_len — model có đường tắt học "nhiều action =
    # positive" thay vì học TỶ LỆ loại hành động. Bản _ratio (chia cho số
    # action trong prefix) giữ nguyên thông tin về THÀNH PHẦN hành động
    # nhưng loại bỏ phần lớn tín hiệu độ dài thô — dùng làm feature CHÍNH
    # cho B2/B3/M1 (xem src/models/baselines.py), giữ bản thô chỉ làm phụ.
    feats.update({
        f"action_count_{t}_ratio": (type_counts.get(t, 0) / n) if n else 0.0
        for t in all_types
    })

    bigrams = Counter(
        (actions[i].event_type, actions[i + 1].event_type) for i in range(len(actions) - 1)
    )
    trigrams = Counter(
        (actions[i].event_type, actions[i + 1].event_type, actions[i + 2].event_type)
        for i in range(len(actions) - 2)
    )
    feats["num_distinct_bigrams"] = float(len(bigrams))
    feats["num_distinct_trigrams"] = float(len(trigrams))

    bridge_protocols = {a.protocol for a in actions if a.event_type in ("bridge_deposit", "bridge_withdraw") and a.protocol}
    feats["num_bridge_families"] = float(len(bridge_protocols))

    swap_after_bridge = 0
    for i in range(len(actions) - 1):
        if actions[i].event_type in ("bridge_deposit", "bridge_withdraw") and actions[i + 1].event_type == "swap":
            swap_after_bridge += 1
    feats["swap_after_bridge"] = float(swap_after_bridge)

    stablecoins = {"usdc", "usdt", "dai", "busd"}
    feats["stablecoin_pivot"] = float(
        sum(1 for a in actions if a.token and a.token.lower() in stablecoins)
    )
    return feats


def _motif_features(actions: List[CanonicalEvent]) -> Dict[str, float]:
    """Motif chỉ được đếm nếu ĐÃ hoàn tất trong prefix hiện tại.

    vd `split` cần >=2 outgoing edges từ cùng src trong cùng cụm thời gian đã
    quan sát; nếu motif cần future event để xác nhận (vd merge chưa thấy các
    nhánh hội tụ) thì không được đếm là "hoàn tất" — chỉ dựa vào actions đã
    có trong prefix, không suy đoán action tương lai.
    """
    out_by_src: Dict[str, List[CanonicalEvent]] = {}
    in_by_dst: Dict[str, List[CanonicalEvent]] = {}
    for a in actions:
        out_by_src.setdefault(a.src, []).append(a)
        in_by_dst.setdefault(a.dst, []).append(a)

    split_count = sum(1 for v in out_by_src.values() if len(v) >= 2)
    merge_count = sum(1 for v in in_by_dst.values() if len(v) >= 2)

    bridge_then_swap = 0
    swap_then_split = 0
    for i in range(len(actions) - 1):
        if actions[i].event_type in ("bridge_deposit", "bridge_withdraw") and actions[i + 1].event_type == "swap":
            bridge_then_swap += 1
        if actions[i].event_type == "swap" and actions[i + 1].event_type == "split":
            swap_then_split += 1

    # peel_like_chain: chuỗi liên tiếp transfer với 1 outgoing mỗi hop, giảm dần amount
    peel_like = 0
    chain_len = 1
    for i in range(1, len(actions)):
        prev, cur = actions[i - 1], actions[i]
        if prev.event_type == "transfer" == cur.event_type and prev.dst == cur.src and cur.amount_norm <= prev.amount_norm:
            chain_len += 1
            if chain_len >= 3:
                peel_like = 1
        else:
            chain_len = 1

    bridge_events = [a for a in actions if a.event_type in ("bridge_deposit", "bridge_withdraw")]
    nested_bridge = 1 if len({a.protocol for a in bridge_events if a.protocol}) >= 2 else 0

    tokens_seq = [a.token for a in actions if a.token]
    rapid_token_pivot = sum(
        1 for i in range(1, len(tokens_seq)) if tokens_seq[i] != tokens_seq[i - 1]
    )

    return {
        "motif_split": float(split_count),
        "motif_merge": float(merge_count),
        "motif_bridge_then_swap": float(bridge_then_swap),
        "motif_swap_then_split": float(swap_then_split),
        "motif_peel_like_chain": float(peel_like),
        "motif_nested_bridge": float(nested_bridge),
        "motif_rapid_token_pivot": float(rapid_token_pivot),
    }


def _context_features(actions: List[CanonicalEvent]) -> Dict[str, float]:
    """Context/endpoint features — CHỈ dùng cho phân tích full-trajectory,
    KHÔNG được bật khi mục tiêu là cảnh báo trước endpoint (early warning).
    """
    known_mixer_interaction = float(any(a.event_type in KNOWN_MIXER_TYPES for a in actions))
    public_exit_service_label = float(
        any((a.counterparty_type or "").lower() in ("cex", "exit_service") for a in actions)
    )
    protocol_category_diversity = float(len({a.protocol for a in actions if a.protocol}))
    return {
        "known_mixer_interaction": known_mixer_interaction,
        "public_exit_service_label": public_exit_service_label,
        "protocol_category_diversity": protocol_category_diversity,
    }




def extract_features(
    trajectory: Trajectory,
    prefix_len: int,
    include_endpoint_context: bool = False,
) -> Dict[str, float]:
    """Tính toàn bộ 6 nhóm feature tại prefix `prefix_len`.

    `include_endpoint_context=False` (mặc định) loại bỏ context features liên
    quan tới endpoint (mixer/CEX) để tuân thủ anti_leakage_rules khi mục tiêu
    là cảnh báo trước endpoint. Chỉ bật True cho phân tích trajectory hoàn
    chỉnh (vd RQ1 so sánh full-trajectory), không dùng cho RQ2 (early
    detection).
    """
    actions = _prefix_actions(trajectory, prefix_len)

    feats: Dict[str, float] = {}
    feats.update(_temporal_features(actions))
    feats.update(_structural_features(actions, trajectory.seed_address))
    feats.update(_economic_features(actions))
    feats.update(_semantic_action_features(actions))
    feats.update(_motif_features(actions))
    if include_endpoint_context:
        feats.update(_context_features(actions))

    feats["prefix_len"] = float(prefix_len)
    # KHONG tinh prefix_ratio = prefix_len / len(trajectory): mau so la do dai
    # CUOI CUNG cua trajectory (chi biet sau khi dong tien ket thuc) -> leak
    # thong tin tuong lai vao prefix. Da xoa 2026-09-27 (Todo T4).
    return feats


def extract_all_prefixes(
    trajectory: Trajectory,
    ratios: Sequence[float] = (0.25, 0.5, 0.75, 1.0),
    k_values: Sequence[int] = (2, 3, 5, 7),
    include_endpoint_context: bool = False,
) -> List[Tuple[PrefixSpec, Dict[str, float]]]:
    specs = generate_prefixes(trajectory, ratios=ratios, k_values=k_values)
    return [
        (spec, extract_features(trajectory, spec.length, include_endpoint_context=include_endpoint_context))
        for spec in specs
    ]
