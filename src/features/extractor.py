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
from collections import Counter, deque
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


# ============================================================================
# Giai đoạn A (feature ứng viên MỚI, configs/features_v3_candidate.yaml) —
# KHÔNG được gọi từ extract_features()/extract_all_prefixes() (giữ nguyên
# hành vi cũ, KHÔNG ảnh hưởng RQ1/RQ2 chính thức đã freeze v1.0). Chỉ dùng
# qua extract_v3_candidate_features() (script thử nghiệm riêng, Tuần 11).
# ============================================================================
def _cross_chain_features(actions: List[CanonicalEvent]) -> Dict[str, float]:
    """Cross-chain diversity per prefix — số chain PHÂN BIỆT đã chạm tới
    (dựa trên `chain_id` thật của từng event, KHÔNG suy ra từ đếm bridge
    action như `num_bridge_families`/`time_to_first_bridge` đã có).

    LƯU Ý QUAN TRỌNG (đã xác nhận bằng dữ liệu thật, không suy đoán): kiến
    trúc pipeline HIỆN TẠI build mỗi trajectory hoàn toàn trong 1 chain duy
    nhất (collector/decoder không fetch dữ liệu chain đích khi gặp
    bridge_deposit/bridge_withdraw — event đó chỉ đánh dấu "đã tương tác
    contract bridge đã verify", vẫn nằm trên CÙNG `chain_id` nguồn). Kiểm
    tra trực tiếp `data/processed/*_events.json`: MỌI trajectory hiện có
    chỉ có ĐÚNG 1 `chain_id` distinct. Feature này vì vậy DỰ KIẾN sẽ có
    variance=0 trên dữ liệu hiện tại — implement đúng như đặc tả để đo
    thực nghiệm xác nhận (Bước 2), không tự ý thay thế bằng proxy khác.
    """
    if not actions:
        return {"cross_chain_distinct_count": 0.0, "cross_chain_expansion_rate": 0.0}
    chain_ids = [a.chain_id for a in actions]
    distinct = set(chain_ids)
    n_distinct = len(distinct)

    seen: set = set()
    first_new_chain_positions: List[int] = []
    for i, cid in enumerate(chain_ids):
        if cid not in seen:
            seen.add(cid)
            first_new_chain_positions.append(i)
    # ty le vi tri (theo so action) cham chain MOI CUOI CUNG - "toc do mo
    # rong": gan 0 = mo rong sang chain moi rat som, 1 = chi cham chain moi
    # o cuoi (hoac khong co chain moi nao ngoai chain dau).
    expansion_rate = (
        float(first_new_chain_positions[-1] + 1) / len(actions) if n_distinct >= 2 else 0.0
    )
    return {
        "cross_chain_distinct_count": float(n_distinct),
        "cross_chain_expansion_rate": expansion_rate,
    }


def _token_diversity_filtered_features(
    actions: List[CanonicalEvent], min_value_share: float = 0.01,
) -> Dict[str, float]:
    """Token diversity đã LỌC DUST — chỉ tính token có value share >= nguong
    tren TONG inflow that (tài liệu gốc mục 3.9: dust/spam token có thể
    thổi phồng diversity giả tạo).

    Đã kiểm tra: `token_category_diversity` HIỆN CÓ (economic group,
    `_economic_features`) = `len({a.token for a in actions if a.token})` —
    đếm MỌI token phân biệt, KHÔNG lọc theo value share — xác nhận đúng
    nghi ngờ trong yêu cầu: đây là hạn chế thật của feature cũ. KHÔNG sửa
    trực tiếp `_economic_features` (tránh đổi RQ1/RQ2 đã freeze) — chỉ ghi
    nhận ở đây, đề xuất thay thế nếu nhóm feature này được chọn mang sang
    Giai đoạn B.

    Dùng RAW value (expm1 cua amount_norm log-scale, DUNG QUY UOC da co
    trong src/trajectories/builder.py::_raw_value — cong don truc tiep tren
    gia tri log-scale la SAI, da la bug that phat hien truoc do trong du
    an) de tinh dung ty le dong gop cua tung token.
    """
    if not actions:
        return {"token_category_diversity_filtered": 0.0, "token_value_entropy_filtered": 0.0}
    value_by_token: Dict[str, float] = {}
    total = 0.0
    for a in actions:
        if not a.token:
            continue
        raw_v = math.expm1(abs(a.amount_norm))
        value_by_token[a.token] = value_by_token.get(a.token, 0.0) + raw_v
        total += raw_v

    if total <= 0 or not value_by_token:
        return {"token_category_diversity_filtered": 0.0, "token_value_entropy_filtered": 0.0}

    shares = {t: v / total for t, v in value_by_token.items()}
    filtered = {t: s for t, s in shares.items() if s >= min_value_share}
    diversity_filtered = float(len(filtered))

    if filtered:
        filtered_total = sum(filtered.values())
        entropy = -sum(
            (s / filtered_total) * math.log2(s / filtered_total) for s in filtered.values() if s > 0
        )
    else:
        entropy = 0.0

    return {
        "token_category_diversity_filtered": diversity_filtered,
        "token_value_entropy_filtered": float(entropy),
    }


def _local_centrality_features(
    actions: List[CanonicalEvent], seed_address: str, max_nodes_for_exact: int = 500,
) -> Dict[str, float]:
    """Approximate centrality trong subgraph NHỎ, ĐÃ BOUNDED của chính
    trajectory (KHÔNG phải betweenness toàn mạng chain — tài liệu gốc đã
    loại vì quá đắt trên toàn chain; ở đây graph chỉ có tối đa vài trăm
    node vì đã bounded theo thiết kế trajectory, nên tính CHÍNH XÁC
    (Brandes' algorithm, coi cạnh vô hướng) vẫn rẻ — "approximate" đúng
    nghĩa so với mạng đầy đủ, không phải xấp xỉ thuật toán).

    `max_nodes_for_exact`: guard an toàn — nếu subgraph vượt ngưỡng (hiếm,
    hard-negative dài nhất quan sát được ~1000 event), trả NaN + cờ
    `local_centrality_capped=1` thay vì tính (tránh runaway compute), KHÔNG
    suy đoán giá trị thay thế.
    """
    if not actions:
        return {
            "seed_betweenness_centrality": 0.0, "seed_closeness_centrality": 0.0,
            "mean_betweenness_centrality": 0.0, "local_centrality_capped": 0.0,
        }

    adj: Dict[str, set] = {}
    nodes: set = set()
    for a in actions:
        nodes.add(a.src)
        nodes.add(a.dst)
        if a.src == a.dst:
            continue
        adj.setdefault(a.src, set()).add(a.dst)
        adj.setdefault(a.dst, set()).add(a.src)
    for n in nodes:
        adj.setdefault(n, set())

    n_nodes = len(nodes)
    if n_nodes > max_nodes_for_exact:
        return {
            "seed_betweenness_centrality": float("nan"), "seed_closeness_centrality": float("nan"),
            "mean_betweenness_centrality": float("nan"), "local_centrality_capped": 1.0,
        }

    # Brandes' betweenness centrality (unweighted, undirected) - O(V*E), re
    # voi graph nho da bounded.
    betweenness = {n: 0.0 for n in nodes}
    for s in nodes:
        stack: List[str] = []
        pred: Dict[str, List[str]] = {n: [] for n in nodes}
        sigma = {n: 0.0 for n in nodes}
        sigma[s] = 1.0
        dist = {n: -1 for n in nodes}
        dist[s] = 0
        queue = deque([s])
        while queue:
            v = queue.popleft()
            stack.append(v)
            for w in adj[v]:
                if dist[w] < 0:
                    dist[w] = dist[v] + 1
                    queue.append(w)
                if dist[w] == dist[v] + 1:
                    sigma[w] += sigma[v]
                    pred[w].append(v)
        delta = {n: 0.0 for n in nodes}
        while stack:
            w = stack.pop()
            for v in pred[w]:
                if sigma[w] > 0:
                    delta[v] += (sigma[v] / sigma[w]) * (1 + delta[w])
            if w != s:
                betweenness[w] += delta[w]
    for n in nodes:  # moi cap dinh duoc dem 2 lan (tu 2 huong BFS) vi do thi vo huong
        betweenness[n] /= 2.0
    norm = ((n_nodes - 1) * (n_nodes - 2) / 2.0) if n_nodes > 2 else 1.0
    betweenness_norm = {n: (v / norm if norm else 0.0) for n, v in betweenness.items()}

    dist_from_seed = {n: -1 for n in nodes}
    if seed_address in nodes:
        dist_from_seed[seed_address] = 0
        q = deque([seed_address])
        while q:
            v = q.popleft()
            for w in adj[v]:
                if dist_from_seed[w] < 0:
                    dist_from_seed[w] = dist_from_seed[v] + 1
                    q.append(w)
    reachable_dists = [d for d in dist_from_seed.values() if d > 0]
    closeness = (
        len(reachable_dists) / sum(reachable_dists) if reachable_dists and sum(reachable_dists) > 0 else 0.0
    )

    return {
        "seed_betweenness_centrality": float(betweenness_norm.get(seed_address, 0.0)),
        "seed_closeness_centrality": float(closeness),
        "mean_betweenness_centrality": float(sum(betweenness_norm.values()) / n_nodes) if n_nodes else 0.0,
        "local_centrality_capped": 0.0,
    }


def percentile_rank_against_reference(value: float, reference_values: Sequence[float]) -> float:
    """% giá trị trong `reference_values` <= `value` (0-100) — dùng cho
    nhóm feature 4 (percentile-normalized). Hàm THUẦN TÚY (không truy cập
    dataset toàn cục) — PHẢI được gọi với `reference_values` CHỈ LẤY TỪ
    TRAIN FOLD (không bao giờ gồm outer test fold của chính leave-one-
    incident-out), nếu không sẽ rò rỉ thống kê validation vào feature
    (đúng nguyên tắc `_filter_low_coverage_columns` đã áp dụng trong
    src/models/baselines.py) — xem cách dùng fold-aware trong
    scripts/run_feature_candidates_v3_evaluation.py.
    """
    ref = sorted(reference_values)
    if not ref:
        return 50.0
    n_le = sum(1 for v in ref if v <= value)
    return float(n_le) / len(ref) * 100.0


def extract_v3_candidate_features(
    trajectory: Trajectory, prefix_len: int, min_value_share: float = 0.01, max_nodes_for_exact: int = 500,
) -> Dict[str, float]:
    """Giai đoạn A, Bước 1 — 3/4 nhóm feature ứng viên mới có thể tính
    THUẦN TỪ 1 trajectory (cross_chain, token_diversity_filtered,
    local_centrality). Nhóm 4 (percentile-normalized) KHÔNG nằm ở đây —
    cần tham chiếu quần thể train fold, tính ở tầng script (xem
    `percentile_rank_against_reference` ở trên).

    KHÔNG gọi từ `extract_features()`/`extract_all_prefixes()` — tách biệt
    hoàn toàn, không ảnh hưởng RQ1/RQ2 chính thức đã freeze v1.0.
    """
    actions = _prefix_actions(trajectory, prefix_len)
    feats: Dict[str, float] = {}
    feats.update(_cross_chain_features(actions))
    feats.update(_token_diversity_filtered_features(actions, min_value_share=min_value_share))
    feats.update(_local_centrality_features(actions, trajectory.seed_address, max_nodes_for_exact=max_nodes_for_exact))
    return feats


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
    feats["prefix_ratio"] = float(prefix_len) / len(trajectory) if len(trajectory) else 0.0
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
