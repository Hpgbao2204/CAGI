"""
Bounded value-flow trajectory builder — xem configs/data.yaml -> trajectory
và proposal_revision_v1.md.

Trajectory = một chuỗi CanonicalEvent đã sắp xếp theo thời gian, được mở
rộng từ một seed address bằng thuật toán bounded value-flow expansion:
chỉ giữ nhánh outgoing nếu (a) value share đủ lớn so với tổng outflow của
node đó (tainted share), hoặc (b) counterparty nằm trong allowlist đã biết
(bridge/DEX). Việc mở rộng bị chặn bởi max_depth (số hop) và
time_horizon_hours (cửa sổ thời gian kể từ event đầu tiên trong trajectory).

Bridge linking (nối một bridge_deposit ở chain A với bridge_withdraw tương
ứng ở chain B) chỉ được thực hiện khi có evidence rõ ràng (cùng protocol,
cùng token, thứ tự thời gian hợp lệ, và độ lệch giá trị nhỏ) — mọi liên kết
đều gắn kèm `confidence`, không suy đoán mù theo địa chỉ.
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import yaml

from src.normalize.schema import CanonicalEvent

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_CONFIG_PATH = REPO_ROOT / "configs" / "data.yaml"


@dataclass(frozen=True)
class TrajectoryConfig:
    max_depth: int
    time_horizon_hours: float
    min_tainted_share: float
    bridge_allowlist: Tuple[str, ...] = ()
    dex_allowlist: Tuple[str, ...] = ()
    mixer_allowlist: Tuple[str, ...] = ()
    lending_allowlist: Tuple[str, ...] = ()
    expand_iterations: int = 2

    @property
    def allowlist(self) -> set:
        # Counterparty thuộc allowlist LUÔN được giữ bất kể value_share — bắt
        # buộc cho các trường hợp cash-out qua nhiều token khác nhau (vd
        # USDC+ARB+WETH+WBTC cùng lúc), nơi so sánh "share" trên SỐ LƯỢNG
        # TOKEN THÔ giữa các token khác nhau không có ý nghĩa (1 WBTC và 1
        # USDC không cùng giá trị — không có dữ liệu giá để quy đổi USD).
        # Bug thật phát hiện ở DeltaPrime 2026-08-13: 2.967 WBTC (~$267k)
        # bridge_deposit bị tính share=0.0 vì so trực tiếp với ~300,000 đơn
        # vị USDC+ARB+WETH cộng dồn, dù giá trị USD tương đương còn cao hơn.
        # lending_allowlist thêm 2026-08-13 (Venus Protocol) — cùng lý do.
        return set(
            a.lower()
            for a in (*self.bridge_allowlist, *self.dex_allowlist, *self.mixer_allowlist, *self.lending_allowlist)
        )


def load_trajectory_config(path: Path = DEFAULT_DATA_CONFIG_PATH) -> TrajectoryConfig:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    traj = raw["trajectory"]
    return TrajectoryConfig(
        max_depth=traj["max_depth"],
        time_horizon_hours=traj["time_horizon_hours"],
        min_tainted_share=traj["min_tainted_share"],
        bridge_allowlist=tuple(raw.get("bridge_allowlist") or ()),
        dex_allowlist=tuple(raw.get("dex_allowlist") or ()),
        mixer_allowlist=tuple(raw.get("mixer_allowlist") or ()),
        lending_allowlist=tuple(raw.get("lending_allowlist") or ()),
        expand_iterations=int(traj.get("expand_iterations", 2)),
    )


@dataclass
class BridgeLink:
    """Một liên kết bridge_deposit -> bridge_withdraw có evidence."""

    deposit_key: Tuple
    withdraw_key: Tuple
    confidence: float
    evidence: str


@dataclass
class Trajectory:
    trajectory_id: str
    seed_address: str
    actions: List[CanonicalEvent] = field(default_factory=list)
    node_depth: Dict[str, int] = field(default_factory=dict)
    bridge_links: List[BridgeLink] = field(default_factory=list)
    incident_id: Optional[str] = None
    label: Optional[int] = None

    def __len__(self) -> int:
        return len(self.actions)


def _sort_key(ev: CanonicalEvent):
    # Schema (Bước 1) không có transaction_index; dùng tx_hash làm tie-break
    # kế tiếp sau block_number, rồi log_index — gần đúng nhất có thể với thứ
    # tự (timestamp, block_number, transaction_index, log_index) mô tả trong
    # spec khi transaction_index không có sẵn trong dữ liệu nguồn.
    return (ev.timestamp, ev.block_number, ev.tx_hash, ev.log_index)


def _dedup(events: Iterable[CanonicalEvent]) -> List[CanonicalEvent]:
    seen: Dict[Tuple, CanonicalEvent] = {}
    for ev in events:
        seen[ev.dedup_key()] = ev
    return list(seen.values())


def build_trajectory(
    events: Sequence[CanonicalEvent],
    seed_address: str,
    config: TrajectoryConfig,
    incident_id: Optional[str] = None,
    label: Optional[int] = None,
    trajectory_id: Optional[str] = None,
) -> Trajectory:
    """Mở rộng trajectory từ seed_address bằng bounded value-flow expansion.

    `events` là pool sự kiện ứng viên (đã normalize qua CanonicalEvent),
    không nhất thiết chỉ thuộc trajectory này — hàm sẽ lọc lấy phần liên
    quan bằng cách bám theo frontier bắt đầu từ seed_address.
    """
    seed_address = seed_address.lower()
    all_events = _dedup(events)
    all_events.sort(key=_sort_key)

    if not all_events:
        return Trajectory(
            trajectory_id=trajectory_id or f"traj_{seed_address}",
            seed_address=seed_address,
            incident_id=incident_id,
            label=label,
        )

    # Tổng outflow theo từng src address, dùng để tính tainted (value) share.
    # QUAN TRỌNG: amount_norm đã log-scale (log1p) theo schema Bước 1, nên
    # KHÔNG được cộng dồn/so sánh trực tiếp trên amount_norm để tính "tỷ lệ
    # giá trị" — log(a)+log(b) != log(a+b), phép cộng dồn giá trị log-scale
    # không có ý nghĩa toán học đúng và làm value_share bị nén sai lệch khi
    # có nhiều event tương đồng (bug thật phát hiện ở QBridge 2026-08-13:
    # max_share tính trên log-scale chỉ 1.9% dù giá trị thật chiếm 16.7%).
    # Dùng math.expm1 (nghịch đảo log1p) để khôi phục giá trị thật CHỈ cho
    # phép tính nội bộ này — không đổi CanonicalEvent.amount_norm (vẫn giữ
    # log-scale đúng theo schema).
    def _raw_value(ev: CanonicalEvent) -> float:
        return math.expm1(abs(ev.amount_norm))

    # Mẫu số PHẢI được tính riêng theo từng TOKEN (khóa (src, token)), không
    # cộng dồn qua nhiều token khác nhau của cùng 1 src — đơn vị thô của các
    # token khác nhau không tương thích (vd 11,977 "ETH" cộng với hàng trăm
    # nghìn "ARB"/"WBTC"/"USDC" ở đơn vị token thô không quy đổi USD). Bug
    # thật phát hiện 2026-08-27 khi thêm Radiant Capital: seed có nhiều swap
    # ARB/WBTC/USDC nhỏ trước đó khiến tổng mẫu số (gộp token) bị đội lên
    # ~4.98 triệu đơn vị hỗn hợp, làm giao dịch outbound 11,977 ETH THẬT
    # (khớp báo cáo công khai) bị tính value_share=0.24% và bị loại oan dù
    # đây gần như là 100% giá trị outbound thật theo đúng đơn vị ETH. Kiểm
    # tra lại toàn bộ 17 incident/control cũ (dữ liệu cache, không gọi API
    # mới) cho thấy bug này ảnh hưởng 12/17 (tăng +9 đến +437 action mỗi ca)
    # — MỌI action trước đây vẫn được giữ (fix chỉ MỞ RỘNG, không bao giờ
    # loại bỏ action đã chấp nhận, vì mẫu số per-token luôn <= mẫu số gộp
    # token cho cùng 1 event) — xem
    # results/reports/value_share_unit_mix_fix_v1.md. Đây là fix hoàn chỉnh
    # hơn cho CÙNG root cause đã phát hiện một phần ở DeltaPrime 2026-08-13
    # (xem TrajectoryConfig.allowlist ở trên) — allowlist bypass chỉ giúp khi
    # counterparty là protocol đã verify; per-token share sửa gốc cho cả
    # trường hợp EOA-to-EOA.
    outflow_by_src_token: Dict[Tuple[str, Optional[str]], float] = {}
    for ev in all_events:
        key = (ev.src, ev.token)
        outflow_by_src_token[key] = outflow_by_src_token.get(key, 0.0) + _raw_value(ev)

    node_depth: Dict[str, int] = {seed_address: 0}
    accepted: List[CanonicalEvent] = []
    start_time = None
    allowlist = config.allowlist

    # Sắp xếp trước theo thời gian nghĩa là ta có thể duyệt tuyến tính và mở
    # rộng frontier "online": một event chỉ được chấp nhận nếu src của nó đã
    # nằm trong node_depth (đã reachable từ seed) tại thời điểm event xảy ra.
    # Đặt CAGI_ED_DEBUG_BUILDER=1 để in lý do skip/eval từng event — công cụ
    # chẩn đoán trajectory rỗng (dùng khi điều tra hard-negative mining
    # 2026-08-13, xem metadata/annotation_guide.md mục 9).
    _debug = os.environ.get("CAGI_ED_DEBUG_BUILDER")
    for ev in all_events:
        if ev.src not in node_depth:
            if _debug:
                print(f"DEBUG skip(src_not_in_node_depth): {ev.tx_hash[:12]} src={ev.src[:10]}")
            continue

        depth = node_depth[ev.src]
        if depth >= config.max_depth:
            if _debug:
                print(f"DEBUG skip(max_depth): {ev.tx_hash[:12]}")
            continue

        if start_time is None:
            start_time = ev.timestamp
        elapsed_hours = (ev.timestamp - start_time).total_seconds() / 3600.0
        if elapsed_hours > config.time_horizon_hours:
            if _debug:
                print(f"DEBUG skip(elapsed_hours={elapsed_hours:.2f}>{config.time_horizon_hours}): {ev.tx_hash[:12]}")
            continue

        total_out = outflow_by_src_token.get((ev.src, ev.token), 0.0)
        value_share = (_raw_value(ev) / total_out) if total_out > 0 else 0.0
        counterparty_allowed = ev.dst in allowlist or ev.src in allowlist
        if _debug:
            print(f"DEBUG eval: {ev.tx_hash[:12]} src={ev.src[:10]} dst={ev.dst[:10]} "
                  f"total_out={total_out} value_share={value_share:.4f} allowed={counterparty_allowed}")

        if value_share >= config.min_tainted_share or counterparty_allowed:
            accepted.append(ev)
            # KHÔNG mở rộng frontier QUA địa chỉ protocol đã verify (bridge/
            # DEX/mixer trong allowlist): đây là hạ tầng DÙNG CHUNG bởi rất
            # nhiều user không liên quan (mixer contract, DEX router...),
            # không phải ví cá nhân. Nếu cho dst vào node_depth, các giao
            # dịch của NGƯỜI DÙNG KHÁC đi qua CÙNG contract đó sẽ bị builder
            # coi nhầm là cùng trajectory. Theo threat_model.md mục 4, mixer
            # LÀ endpoint hợp lệ — không tiếp tục trace qua nó; áp dụng
            # tương tự cho DEX router vì cùng là hạ tầng dùng chung.
            # Bug thật phát hiện 2026-08-13: (1) FEG Bridge — thêm Tornado
            # Cash vào mixer_allowlist khiến trajectory phình 15->237 action
            # vì trace qua mixer sang withdrawal không liên quan; (2) QBridge
            # — PancakeSwap Router bị coi là node có thể mở rộng tiếp, cùng
            # rủi ro nếu có cache dữ liệu thật cho toàn bộ router (hàng triệu
            # tx của user khác).
            if ev.dst not in allowlist and (ev.dst not in node_depth or node_depth[ev.dst] > depth + 1):
                node_depth[ev.dst] = depth + 1

    traj = Trajectory(
        trajectory_id=trajectory_id or f"traj_{seed_address}",
        seed_address=seed_address,
        actions=accepted,
        node_depth=node_depth,
        incident_id=incident_id,
        label=label,
    )
    traj.bridge_links = _link_bridges(accepted)
    return traj


def _link_bridges(actions: Sequence[CanonicalEvent]) -> List[BridgeLink]:
    """Nối bridge_deposit -> bridge_withdraw chỉ khi có evidence rõ ràng.

    Evidence tối thiểu: cùng `protocol`, cùng `token`, bridge_withdraw xảy ra
    sau bridge_deposit, và deposit chưa được match trước đó (1-1 matching).
    Đây là heuristic thận trọng (conservative) — không suy đoán theo địa chỉ
    counterparty, chỉ dùng cho tới khi có evidence mạnh hơn (vd event message
    ID thật) khi decoder thật (Bước 3) khả dụng.
    """
    deposits = [a for a in actions if a.event_type == "bridge_deposit"]
    withdraws = [a for a in actions if a.event_type == "bridge_withdraw"]
    used_withdraws = set()
    links: List[BridgeLink] = []

    for dep in deposits:
        best = None
        for wd in withdraws:
            key = wd.dedup_key()
            if key in used_withdraws:
                continue
            if wd.timestamp < dep.timestamp:
                continue
            if dep.protocol and wd.protocol and dep.protocol != wd.protocol:
                continue
            if dep.token and wd.token and dep.token != wd.token:
                continue
            best = wd
            break
        if best is not None:
            used_withdraws.add(best.dedup_key())
            same_protocol = bool(dep.protocol) and dep.protocol == best.protocol
            same_token = bool(dep.token) and dep.token == best.token
            confidence = 0.4 + 0.3 * same_protocol + 0.3 * same_token
            evidence = "protocol+token match, ordered in time" if (same_protocol or same_token) else "time-order only (weak)"
            links.append(
                BridgeLink(
                    deposit_key=dep.dedup_key(),
                    withdraw_key=best.dedup_key(),
                    confidence=round(min(confidence, 1.0), 3),
                    evidence=evidence,
                )
            )
    return links
