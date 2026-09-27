"""
Hard-negative miner — mở rộng Bước D: thay vì 1 hard-negative/incident, khai
thác QUẦN THỂ benign user đã tương tác với cùng contract bridge/DEX/mixer đã
verify liên quan tới mỗi incident positive, trong 1 khung thời gian quanh
incident, để đạt mục tiêu ≥200 hard-negative trajectory cho toàn dataset.

Thuật toán mỗi incident:
1. Lấy (chain, contract) đã verify liên quan tới incident đó (xem
   `INCIDENT_MINING_CONTRACTS`).
2. Bulk fetch MỘT LẦN mọi địa chỉ đã tương tác với contract đó trong khung
   ±MINING_WINDOW_DAYS ngày quanh incident (hoặc chỉ "trước" incident nếu
   contract bị dừng/bất thường sau đó — xem `MINING_WINDOW_OVERRIDE`).
3. Với từng candidate: loại trừ (seed/known-malicious/đã dùng ở incident
   khác), rồi build trajectory NHẸ (không full frontier expansion) để kiểm
   tra tiêu chí Bước D: cùng chain, cùng protocol, trong khung thời gian,
   không mixer_or_exit bất thường, không fan-out kiểu split, volume > 0.
4. Dừng khi đạt target_count hoặc hết candidate — KHÔNG hạ tiêu chí lọc để
   ép đủ số lượng.

Toàn bộ candidate đã CHẤP NHẬN được coi là hard-negative trajectory riêng,
group theo `parent_incident_id` (không phải `incident_id` gốc) khi split —
xem `metadata/hard_negative_registry.csv`.
"""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd

from src.collect.bsctrace_client import BscTraceClient
from src.collect.etherscan_client import EtherscanClient
from src.normalize.decoder import (
    build_verified_bridge_address_index,
    build_verified_mixer_address_index,
    load_protocol_map,
)
from src.normalize.schema import CanonicalEvent
from src.pipeline.incident_pipeline import (
    APPROX_BLOCKS_PER_HOUR,
    BSC_CHAINS,
    RAW_DIR,
    REGISTRY_PATH,
    collect_address_raw_data,
    load_events_for_addresses,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
AMLGUARD_CANDIDATES_PATH = REPO_ROOT / "metadata" / "incident_candidates_amlguard.csv"
HARD_NEGATIVE_REGISTRY_PATH = REPO_ROOT / "metadata" / "hard_negative_registry.csv"

# Khung thời gian mining — LỰA CHỌN: ±7 ngày quanh incident. Lý do: đủ rộng
# để có quần thể candidate (hàng chục-hàng trăm địa chỉ tương tác với 1
# contract phổ biến trong 2 tuần), đủ hẹp để giữ "cùng giai đoạn thời gian"
# có ý nghĩa (không mining candidate cách incident hàng năm).
MINING_WINDOW_DAYS = 7

# BSC Token Hub: chain BỊ DỪNG (44 validator tạm ngưng) ngay sau hack —
# hoạt động "sau" incident trong vài ngày đầu không phản ánh user bình
# thường (chain đóng băng). Chỉ mining "trước" incident cho case này.
MINING_WINDOW_OVERRIDE: Dict[str, str] = {
    "bsc_token_hub_2022": "before_only",
}

# (chain, protocol_name, contract_address) dùng để mining candidate cho mỗi
# incident — chọn contract ĐÃ VERIFY liên quan trực tiếp tới outbound
# trajectory/provenance của incident đó (xem metadata/protocol_map.yaml).
INCIDENT_MINING_CONTRACTS: Dict[str, List[Tuple[str, str, str]]] = {
    "ronin_bridge_2022": [
        ("eth", "Ronin Bridge", "0x1a2a1c938ce3ec39b6d47113c7955baa9dd454f2"),
        ("eth", "Uniswap V3 SwapRouter", "0xe592427a0aece92de3edee1f18e0157c05861564"),
        ("eth", "1inch v4 AggregationRouter", "0x1111111254fb6c44bac0bed2854e76f90643097"),
    ],
    "qbridge_qubit_2022": [
        ("bsc", "PancakeSwap V2", "0x10ed43c718714eb63d5aa57b78b54704e256024e"),
    ],
    "feg_bridge_2024": [
        ("eth", "Tornado Cash Router", "0xd90e2f925da726b50c4ed8d0fb90ad053324f31b"),
    ],
    "deltaprime_arbitrum_2024": [
        ("arbitrum", "Across Protocol SpokePool", "0xe35e9842fceaca96570b734083f4a58e8f7c5f2a"),
    ],
    "bsc_token_hub_2022": [
        ("bsc", "BSC Token Hub", "0x0000000000000000000000000000000000001004"),
    ],
    "chibi_finance_2023": [
        ("arbitrum", "Stargate (LayerZero)", "0xbf22f0f184bccbea268df387a49ff5238dd23e40"),
    ],
    "wooppv2_2024": [
        ("arbitrum", "Stargate (LayerZero)", "0xbf22f0f184bccbea268df387a49ff5238dd23e40"),
    ],
    "utopiasphere_2024": [
        ("bsc", "LI.FI Diamond", "0x1231deb6f5749ef6ce6943a275a1d3e7486f4eae"),
    ],
    "xkingdom_2024": [
        ("arbitrum", "Stargate (LayerZero)", "0xbf22f0f184bccbea268df387a49ff5238dd23e40"),
    ],
    "wault_finance_2021": [
        ("bsc", "Multichain (AnySwap) anyETH Token (legacy, 2021)", "0x6f817a0ce8f7640add3bc0c1c2298635043c2423"),
        # fallback: contract goc (anyETH legacy) khong con candidate nao trong cua so mining (checked=0,
        # contract qua it giao dich vao 2026 khi crawl) - dung PancakeSwap V2 (da verify, phu bien) lam
        # nguon mining thay the, cung window +-7 ngay quanh incident 2021-08-04 (khac han window 2022 cua
        # qbridge_qubit_2022 dung chung contract nay - khong trung candidate).
        ("bsc", "PancakeSwap V2", "0x10ed43c718714eb63d5aa57b78b54704e256024e"),
    ],
    "paraluni_2022": [
        ("bsc", "PancakeSwap V2", "0x10ed43c718714eb63d5aa57b78b54704e256024e"),
    ],
    "circulate_2023": [
        ("bsc", "Multichain (AnySwap) Router V4 (legacy, 2023)", "0xd1c5966f9f5ee6881ff6b261bbeda45972b1b5f3"),
        # fallback: cung ly do voi wault_finance_2021 (contract goc het candidate, checked=0) - dung
        # PancakeSwap V2 window +-7 ngay quanh incident 2023-01-12 (khac window 2022 cua qbridge, khong
        # trung candidate).
        ("bsc", "PancakeSwap V2", "0x10ed43c718714eb63d5aa57b78b54704e256024e"),
    ],
    "radiant_capital_arbitrum_2024": [
        # LI.FI Diamond - CUNG dia chi da xac nhan xuat hien THAT trong outbound
        # trajectory cua incident nay (56 action bridge_deposit that, xem golden
        # fixture radiant_capital_arbitrum_2024_events.golden.json) - dung lam
        # nguon mining vi day la contract THAT ma ke tan cong da dung, dung quy
        # uoc "chon contract da verify lien quan truc tiep toi outbound trajectory/
        # provenance cua incident" (xem docstring INCIDENT_MINING_CONTRACTS).
        ("arbitrum", "LI.FI Diamond", "0x1231deb6f5749ef6ce6943a275a1d3e7486f4eae"),
    ],
    "magic_abracadabra_arbitrum_2025": [
        # LI.FI Diamond - CUNG dia chi that xuat hien trong outbound trajectory
        # (2 action bridge_deposit that, xem golden fixture
        # magic_abracadabra_arbitrum_2025_events.golden.json).
        ("arbitrum", "LI.FI Diamond", "0x1231deb6f5749ef6ce6943a275a1d3e7486f4eae"),
    ],
    "hackerdao_2022": [
        # PancakeSwap V2 - CUNG dia chi that xuat hien trong outbound trajectory
        # (2 action swap that, xem golden fixture hackerdao_2022_events.golden.json).
        ("bsc", "PancakeSwap V2", "0x10ed43c718714eb63d5aa57b78b54704e256024e"),
    ],
    "new_free_dao_2022": [
        # KHONG co DEX/bridge nao trong outbound trajectory (9 action toan
        # transfer, xem golden fixture) - dung PancakeSwap V2 lam nguon
        # mining THAY THE, cung ly do da dung cho circulate_2023/
        # wault_finance_2021 khi gap tinh huong tuong tu (contract goc
        # khong co candidate). eval_tier=auxiliary_low_evidence.
        ("bsc", "PancakeSwap V2", "0x10ed43c718714eb63d5aa57b78b54704e256024e"),
    ],
}

MIXER_CONTRACTS = {"0xd90e2f925da726b50c4ed8d0fb90ad053324f31b"}  # Tornado Cash Router


@dataclass
class MiningResult:
    address: str
    chain: str
    contract_used: str
    protocol_name: str
    block_number: int
    reject_reason: Optional[str] = None

    @property
    def accepted(self) -> bool:
        return self.reject_reason is None


@dataclass
class MiningReport:
    parent_incident_id: str
    accepted: List[MiningResult] = field(default_factory=list)
    rejected: List[MiningResult] = field(default_factory=list)
    candidates_checked: int = 0


def load_known_malicious_addresses() -> Set[str]:
    """Địa chỉ đã biết là malicious — dùng để LOẠI TRỪ khỏi candidate pool.

    Nguồn: cột address trong incident_candidates_amlguard.csv (82 seed,
    dùng để tra cứu — KHÔNG dùng ground truth, chỉ dùng để loại trừ trùng)
    + toàn bộ seed_address trong incident_registry.csv (mọi incident đã
    thu thập, cả positive lẫn negative, tránh dùng lại địa chỉ đã gán vai
    trò khác).
    """
    addrs: Set[str] = set()
    if AMLGUARD_CANDIDATES_PATH.exists():
        df = pd.read_csv(AMLGUARD_CANDIDATES_PATH)
        # cột địa chỉ tên "Heist" trong incident_candidates_amlguard.csv (không
        # phải "address") — fallback tìm cột chứa "address"/"heist" cho an toàn
        addr_col = [c for c in df.columns if c.lower() in ("heist", "address")] or [
            c for c in df.columns if "address" in c.lower() or "heist" in c.lower()
        ]
        if addr_col:
            addrs |= {str(a).lower() for a in df[addr_col[0]].dropna()}
    if REGISTRY_PATH.exists():
        df = pd.read_csv(REGISTRY_PATH)
        if "seed_address" in df.columns:
            addrs |= {str(a).lower() for a in df["seed_address"].dropna()}
    return addrs


def _mining_window(chain: str, incident_start_block: int, incident_id: str) -> Tuple[int, int]:
    blocks_per_day = APPROX_BLOCKS_PER_HOUR.get(chain, 280) * 24
    span = blocks_per_day * MINING_WINDOW_DAYS
    mode = MINING_WINDOW_OVERRIDE.get(incident_id, "symmetric")
    if mode == "before_only":
        return max(0, incident_start_block - span), incident_start_block - 1
    return max(0, incident_start_block - span), incident_start_block + span


def _make_client(chain: str):
    return BscTraceClient(cache_dir=RAW_DIR) if chain in BSC_CHAINS else EtherscanClient(cache_dir=RAW_DIR)


def fetch_contract_counterparties(
    chain: str, contract_address: str, incident_id: str, start_block: int, end_block: int, do_collect: bool = True
) -> List[str]:
    """Bulk fetch MỘT LẦN: mọi địa chỉ đã tương tác (từ hoặc tới) với
    `contract_address` trong [start_block, end_block]. Trả về list address
    (giữ thứ tự xuất hiện, KHÔNG dedup thứ tự — caller tự dedup nếu cần).

    `incident_id`: scope cache theo `parent_incident_id` (bug #6, xem
    annotation_guide.md mục 15) — cùng 1 contract (vd PancakeSwap V2 dùng
    làm fallback cho nhiều incident khác nhau) được mining với cửa sổ
    RIÊNG cho từng incident, không ghi đè cache của nhau.
    """
    client = _make_client(chain) if do_collect else None
    if do_collect:
        collect_address_raw_data(client, chain, contract_address, incident_id, start_block, end_block)

    protocol_map = load_protocol_map()
    bridge_index = build_verified_bridge_address_index(protocol_map)
    mixer_index = build_verified_mixer_address_index(protocol_map)
    events = load_events_for_addresses(chain, [contract_address], incident_id, bridge_index, mixer_index=mixer_index)
    events = [e for e in events if start_block <= e.block_number <= end_block]

    contract_lower = contract_address.lower()
    counterparties: List[str] = []
    seen: Set[str] = set()
    for ev in events:
        other = ev.dst if ev.src == contract_lower else ev.src
        if other == contract_lower or other in seen:
            continue
        seen.add(other)
        counterparties.append(other)
    return counterparties


def compute_min_candidate_events(positive_trajectory_len: int, min_fraction: float = 0.35) -> int:
    """Tính ngưỡng độ phức tạp tối thiểu (số event thô trong cửa sổ mining)
    cho hard-negative candidate, theo tỉ lệ LOG-SCALE so với độ dài
    trajectory của incident positive tương ứng — cùng quy ước log1p đã dùng
    xuyên suốt dự án cho amount_norm (không phải tỉ lệ tuyến tính, tránh đòi
    hỏi candidate dài gần bằng incident lớn như ronin_bridge_2022=113 action).

    Thêm 2026-08-14 (Tuần 5, sửa shortcut độ dài — xem
    results/reports/leakage_audit_v1_findings.md): trước đây
    `_passes_structural_filter` KHÔNG có tiêu chí nào về độ dài/độ phức tạp
    trajectory (chỉ chạm contract + fan_out<=3 + volume>0), khiến 227/403
    (56.3%) hard-negative đã mine chỉ có ĐÚNG 1 action — action_count_* vì
    vậy tương quan gần tuyệt đối với label qua trung gian độ dài, không
    phải tín hiệu semantic thật.
    """
    import math
    if positive_trajectory_len <= 1:
        return 1
    target_log = math.log1p(positive_trajectory_len) * min_fraction
    return max(2, round(math.expm1(target_log)))


def compute_max_fan_out(positive_fan_out: int, scale_fraction: float = 0.85) -> int:
    """Băng TRÊN fan_out cho phép khi mining hard-negative — THAY ngưỡng
    tuyệt đối `fan_out<=3` cũ (áp dụng CÙNG 1 con số cho MỌI incident, bất
    kể fan_out THẬT của chính positive tương ứng) bằng band TƯƠNG ĐỐI theo
    LOG-SCALE so với fan_out của chính positive này — cùng triết lý đã áp
    dụng cho `compute_min_candidate_events` (độ dài/volume).

    Phát hiện Tuần 9 (E6, xem `results/reports/e6_robustness_v1.md`):
    ngưỡng `fan_out<=3` cố định khiến tập hard-negative "sạch" hơn thực tế
    vận hành — "unmatched negative" (candidate bị loại CHÍNH VÌ tiêu chí
    này, fan_out thật lên tới 144) khiến M1 phân biệt KÉM HƠN matched
    (PR-AUC 0.55 vs 0.72). Nguyên nhân gốc: nhiều incident có fan_out THẬT
    cao hơn 3 (vd bsc_token_hub_2022), nhưng hard-negative bị ép phải
    fan_out<=3 — không còn là phép so sánh công bằng.

    `positive_fan_out <= 3` (đa số incident): giữ NGUYÊN ngưỡng CŨ = 3 —
    KHÔNG nới lỏng vô điều kiện cho incident đang có fan_out thấp bình
    thường (đúng yêu cầu "không phải nới lỏng vô điều kiện").
    `positive_fan_out > 3`: nới band theo công thức log-scale (log1p/expm1,
    giống hệt `compute_min_candidate_events`, `scale_fraction < 1` — CÙNG
    triết lý "tỉ lệ log-scale, không phải tuyến tính 1-1" đã dùng cho
    `min_fraction` bên đó) — cho phép hard-negative có fan_out cao hơn hẳn
    ngưỡng cũ, NHƯNG vẫn nhỏ hơn chính fan_out của positive ở mức rất cao
    (sublinear, không bùng nổ vô hạn khi positive_fan_out rất lớn).
    """
    base_max_fan_out = 3
    if positive_fan_out <= base_max_fan_out:
        return base_max_fan_out
    target_log = math.log1p(positive_fan_out) * scale_fraction
    return max(base_max_fan_out, round(math.expm1(target_log)))


def _passes_structural_filter(
    chain: str,
    candidate: str,
    contract_address: str,
    incident_id: str,
    is_mixer: bool,
    start_block: int,
    end_block: int,
    bridge_index: dict,
    mixer_index: dict,
    min_candidate_events: int = 1,
    max_fan_out: int = 3,
) -> Tuple[bool, str, Optional[int]]:
    """Áp dụng tiêu chí Bước D: cùng chain (ngầm định — dữ liệu đã fetch
    theo chain), cùng protocol (candidate có tương tác với contract, đã
    đảm bảo ở bước fetch_contract_counterparties), trong khung thời gian,
    không mixer_or_exit bất thường tiếp theo, không fan-out kiểu split,
    volume > 0, ĐỦ độ phức tạp tối thiểu (min_candidate_events, mặc định=1
    tức KHÔNG lọc thêm — giữ nguyên hành vi cũ cho các lần gọi không truyền
    tham số này). Trả về (pass, reason_neu_fail, actual_block_number).

    `max_fan_out` (mặc định=3, giữ nguyên hành vi cũ cho lần gọi không
    truyền tham số này): ngưỡng TRÊN cho fan_out — Tuần 12 sửa từ hằng số
    cố định sang band tương đối theo `compute_max_fan_out()` (log-scale so
    với fan_out của chính positive tương ứng), gọi bởi
    `mine_hard_negatives_for_incident`.

    `actual_block_number`: block của giao dịch chạm contract SỚM NHẤT —
    dùng làm `start_block` khi build lại trajectory sau này (KHÔNG dùng
    block đầu cửa sổ mining ±7 ngày — bug thật phát hiện 2026-08-13:
    31/211 hard-negative có trajectory RỖNG khi build lại vì start_block
    ghi nhầm thành đầu cửa sổ mining thay vì block giao dịch thật, khiến
    cửa sổ time_horizon_hours=72 chuẩn không phủ đúng hoạt động thật).
    """
    events = load_events_for_addresses(chain, [candidate], incident_id, bridge_index, mixer_index=mixer_index)
    events = [e for e in events if start_block <= e.block_number <= end_block]
    if not events:
        return False, "no_events_in_window", None

    # Tiêu chí độ phức tạp — xem compute_min_candidate_events(). Đặt SAU
    # "no_events_in_window" (đã lọc rỗng) nhưng TRƯỚC các tiêu chí khác để
    # tránh tính toán thừa cho candidate quá đơn giản.
    if len(events) < min_candidate_events:
        return False, "insufficient_complexity_vs_positive", None

    contract_touch_events = [
        e for e in events if e.src == contract_address.lower() or e.dst == contract_address.lower()
    ]
    if not contract_touch_events:
        return False, "no_direct_interaction_with_contract", None
    first_touch_block = min(e.block_number for e in contract_touch_events)

    candidate_src_events = [e for e in events if e.src == candidate]
    mixer_events = [e for e in candidate_src_events if e.event_type == "mixer_or_exit"]
    if is_mixer:
        # Contract CHÍNH LÀ mixer (vd Tornado Cash) -> 1 lần deposit là kỳ
        # vọng bình thường, KHÔNG phải bất thường. Bất thường là có >1
        # mixer event khác nhau (nhiều lần dùng nhiều mixer khác nhau).
        if len(mixer_events) > 1:
            return False, "multiple_mixer_events_unusual", None
    else:
        if mixer_events:
            return False, "unexpected_mixer_followup", None

    unique_dst = {e.dst for e in candidate_src_events}
    if len(unique_dst) > max_fan_out:
        return False, "fan_out_split_like_pattern", None

    total_raw = sum(abs(e.amount_norm) for e in candidate_src_events)
    if total_raw <= 0:
        return False, "zero_volume", None

    return True, "", first_touch_block


def mine_hard_negatives_for_incident(
    incident_id: str,
    incident_row: dict,
    target_count: int = 25,
    max_candidates_checked: int = 150,
    excluded_addresses: Optional[Set[str]] = None,
    do_collect: bool = True,
    min_candidate_events: int = 1,
    max_fan_out: int = 3,
) -> MiningReport:
    excluded = set(a.lower() for a in (excluded_addresses or set()))
    excluded.add(incident_row["seed_address"].lower())
    excluded |= load_known_malicious_addresses()

    contracts = INCIDENT_MINING_CONTRACTS.get(incident_id, [])
    if not contracts:
        raise ValueError(f"Không có mining contract cấu hình cho incident_id='{incident_id}'")

    protocol_map = load_protocol_map()
    bridge_index = build_verified_bridge_address_index(protocol_map)
    mixer_index = build_verified_mixer_address_index(protocol_map)

    report = MiningReport(parent_incident_id=incident_id)

    for chain, protocol_name, contract_address in contracts:
        if len(report.accepted) >= target_count:
            break
        start_block, end_block = _mining_window(chain, int(incident_row["start_block"]), incident_id)
        candidates = fetch_contract_counterparties(chain, contract_address, incident_id, start_block, end_block, do_collect=do_collect)
        is_mixer = contract_address.lower() in MIXER_CONTRACTS

        for candidate in candidates:
            if len(report.accepted) >= target_count or report.candidates_checked >= max_candidates_checked:
                break
            if candidate in excluded:
                continue
            report.candidates_checked += 1

            if do_collect:
                client = _make_client(chain)
                collect_address_raw_data(client, chain, candidate, incident_id, start_block, end_block)

            passed, reason, actual_block = _passes_structural_filter(
                chain, candidate, contract_address, incident_id, is_mixer, start_block, end_block, bridge_index, mixer_index,
                min_candidate_events=min_candidate_events, max_fan_out=max_fan_out,
            )
            result = MiningResult(
                address=candidate, chain=chain, contract_used=contract_address,
                protocol_name=protocol_name, block_number=actual_block if passed else start_block,
                reject_reason=None if passed else reason,
            )
            if passed:
                report.accepted.append(result)
                excluded.add(candidate)  # không dùng lại candidate này cho contract/incident khác trong cùng run
            else:
                report.rejected.append(result)

    return report


def mine_all_incidents(
    target_per_incident: int = 25,
    max_candidates_checked_per_incident: int = 150,
    do_collect: bool = True,
    registry_path: Path = REGISTRY_PATH,
) -> Dict[str, MiningReport]:
    """Mining cho MỌI incident positive trong registry, duy trì 1 tập
    excluded_addresses TOÀN CỤC để đảm bảo KHÔNG có address nào được dùng
    làm hard-negative cho >1 incident (group leakage).
    """
    df = pd.read_csv(registry_path)
    positive_rows = df[df["label"] == 1].to_dict("records")

    global_excluded = load_known_malicious_addresses()
    reports: Dict[str, MiningReport] = {}

    for row in positive_rows:
        incident_id = row["incident_id"]
        if incident_id not in INCIDENT_MINING_CONTRACTS:
            continue
        report = mine_hard_negatives_for_incident(
            incident_id, row, target_count=target_per_incident,
            max_candidates_checked=max_candidates_checked_per_incident,
            excluded_addresses=global_excluded, do_collect=do_collect,
        )
        reports[incident_id] = report
        global_excluded |= {r.address for r in report.accepted}

    return reports


def write_hard_negative_registry(
    reports: Dict[str, MiningReport], path: Path = HARD_NEGATIVE_REGISTRY_PATH, id_infix: str = "hn",
) -> None:
    """Ghi metadata/hard_negative_registry.csv — map hard-negative -> incident
    positive gốc (parent_incident_id), dùng làm group key khi split (KHÔNG
    gộp chung với incident_registry.csv để tránh nhầm 1 hard-negative với
    1 "incident" độc lập).

    `id_infix`: đổi phần "hn" trong hard_negative_id (vd "hnc" cho vòng mine
    bổ sung theo tiêu chí độ phức tạp — xem
    scripts/mine_hard_negatives_v2_complexity.py) để KHÔNG trùng id với vòng
    mine trước khi ghi ra file RIÊNG (path khác HARD_NEGATIVE_REGISTRY_PATH).
    """
    fieldnames = [
        "hard_negative_id", "parent_incident_id", "seed_address", "chain",
        "start_block", "contract_used", "protocol_name", "label",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for incident_id, report in reports.items():
            for i, result in enumerate(report.accepted):
                writer.writerow({
                    "hard_negative_id": f"{incident_id}__{id_infix}{i:03d}",
                    "parent_incident_id": incident_id,
                    "seed_address": result.address,
                    "chain": result.chain,
                    "start_block": result.block_number,
                    "contract_used": result.contract_used,
                    "protocol_name": result.protocol_name,
                    "label": 0,
                })
