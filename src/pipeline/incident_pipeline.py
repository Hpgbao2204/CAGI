"""
Pipeline tổng quát hóa: collect -> decode -> build trajectory cho MỘT
incident_id đọc trực tiếp từ metadata/incident_registry.csv — không hardcode
seed/address/chain trong code (khác với scripts/build_trajectory_from_raw.py
bản pilot, nay được thay thế bởi module này).

Thuật toán mở rộng: bounded value-flow expansion THẬT (không hardcode số hop
thủ công như bản pilot Ronin) — lặp: fetch dữ liệu cho frontier hiện tại ->
decode -> build_trajectory (áp dụng tainted-share/allowlist filter) -> lấy
dst của các action được CHẤP NHẬN làm frontier kế tiếp -> lặp tới khi
frontier hội tụ hoặc chạm max_iterations (mặc định = config.max_depth).

do_collect=False: không gọi mạng, chỉ dùng cache đã có sẵn trong data/raw/
(dùng cho test hồi quy — regression test — và cho việc build lại trajectory
từ dữ liệu đã crawl trước đó mà không tốn thêm quota API).
"""
from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.collect.bsctrace_client import BscTraceClient
from src.collect.etherscan_client import CHAIN_IDS, EtherscanClient
from src.normalize.decoder import (
    build_verified_bridge_address_index,
    build_verified_lending_address_index,
    build_verified_mixer_address_index,
    decode_bsctrace_transfer_row,
    decode_internal_tx_row,
    decode_normal_tx_row,
    decode_tokentx_row,
    load_protocol_map,
    merge_events_into_semantic_actions,
)
from src.normalize.schema import CanonicalEvent
from src.trajectories.builder import Trajectory, TrajectoryConfig, build_trajectory, load_trajectory_config

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "data" / "raw"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
REGISTRY_PATH = REPO_ROOT / "metadata" / "incident_registry.csv"

# Ước lượng thô block/giờ theo chain — CHỈ dùng để tính end_block cho cửa sổ
# collect (time_horizon_hours trong configs/data.yaml), KHÔNG dùng cho suy
# luận nghiệp vụ nào khác. Ghi rõ đây là xấp xỉ, không phải hằng số chính xác.
APPROX_BLOCKS_PER_HOUR = {
    "eth": 280,       # ~12.8s/block trung bình
    "bsc": 1200,      # ~3s/block
    "arbitrum": 4800,  # ~0.75s/block trung bình quan sát được, biến động nhiều theo L1
}


def compute_end_block(chain: str, start_block: int, config: TrajectoryConfig) -> int:
    return start_block + int(config.time_horizon_hours * APPROX_BLOCKS_PER_HOUR.get(chain, 280))


# ----------------------------------------------------------------------
# Đọc incident từ registry
# ----------------------------------------------------------------------
def load_incident_row(incident_id: str, registry_path: Path = REGISTRY_PATH) -> Dict[str, str]:
    with open(registry_path, "r", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["incident_id"] == incident_id:
                return row
    raise KeyError(f"incident_id='{incident_id}' không có trong {registry_path}")


# ----------------------------------------------------------------------
# Cache đọc/ghi thô (dùng chung giữa collect + decode)
# ----------------------------------------------------------------------
# Dedup key theo action_prefix — PHẢI khớp với dedup_key dùng khi phân
# trang trong EtherscanClient._fetch_all_pages (xem src/collect/etherscan_client.py).
# Bug thật phát hiện 2026-08-14 (rà soát cache/pagination hệ thống, xem
# annotation_guide.md mục 14): nếu 1 address có >1 file cache cho cùng
# action_prefix (vd cửa sổ block khác nhau, chồng lấn nhau — audit script
# widen window ghi file mới CẠNH file cũ thay vì đè lên), row trùng ở cả 2
# file bị nạp 2 LẦN vì trước đây hàm này chỉ extend không dedup -> merge
# lệch (vd amount_norm tính sai do nhân đôi leg trong cùng 1 tx). BSCTrace
# (_load_cached_bsctrace_rows) đã dedup đúng từ trước; hàm này thì chưa.
_ROW_DEDUP_KEY = {
    "tokentx": lambda r: (r.get("hash"), r.get("logIndex")),
    "txlist": lambda r: (r.get("hash"),),
    "txlistinternal": lambda r: (r.get("hash"), r.get("traceId")),
}


def _load_cached_rows(chain: str, address: str, incident_id: str, action_prefix: str) -> List[dict]:
    # Cache SCOPED theo incident_id (bug #6, xem annotation_guide.md mục 15)
    # — đọc ĐÚNG thư mục con của incident_id này, không đụng cache của
    # incident khác dùng chung địa chỉ (vd hạ tầng DEX phổ biến).
    d = RAW_DIR / chain / address.lower() / incident_id
    rows: List[dict] = []
    if not d.exists():
        return rows
    key_fn = _ROW_DEDUP_KEY.get(action_prefix)
    seen: set = set()
    for f in sorted(d.glob(f"{action_prefix}_w*.json")):
        payload = json.loads(f.read_text(encoding="utf-8"))
        for row in payload["response"].get("result", []):
            if key_fn is None:
                rows.append(row)
                continue
            key = key_fn(row)
            if key not in seen:
                seen.add(key)
                rows.append(row)
    return rows


def _load_cached_bsctrace_rows(address: str, incident_id: str) -> List[dict]:
    """BSCTrace cache có cấu trúc khác Etherscan: response.result là
    {"transfers": [...], "pageToken": ...} thay vì list trực tiếp.

    DEDUP theo (hash, category, logIndex): các file cache riêng lẻ (page
    outbound w0..wN, inbound w1000..) có thể chứa transfer TRÙNG NHAU nếu
    được fetch nhiều lần ở các thời điểm khác nhau (vd smoke test thăm dò
    trước đó) — bug thật phát hiện ở BSC Token Hub 2026-08-13: provenance
    event bị đếm 4 lần (8 thay vì 2) vì không dedup khi gộp nhiều file.

    Cache SCOPED theo incident_id (bug #6, xem annotation_guide.md mục 15).
    """
    d = RAW_DIR / "bsc" / address.lower() / incident_id
    rows: List[dict] = []
    seen = set()
    if not d.exists():
        return rows
    for f in sorted(d.glob("assettransfers_w*.json")):
        payload = json.loads(f.read_text(encoding="utf-8"))
        result = payload["response"].get("result") or {}
        for row in result.get("transfers", []):
            key = (row.get("hash"), row.get("category"), row.get("logIndex"))
            if key not in seen:
                seen.add(key)
                rows.append(row)
    return rows


def address_cache_complete(chain: str, address: str, incident_id: str) -> bool:
    """Cache cua 1 dia chi (scope incident_id) da DAY DU chua.
    bsc: trang inbound cuoi (w1000+) khong con pageKey (hoac cham tran 100
    trang — cung gioi han voi BscTraceClient). eth/arbitrum: da co file
    txlistinternal (loai goi CUOI CUNG trong collect_address_raw_data)."""
    d = RAW_DIR / chain / address.lower() / incident_id
    if not d.exists():
        return False
    if chain in BSC_CHAINS:
        inbound = [f for f in d.glob("assettransfers_w*.json") if int(f.stem.split("_w")[1]) >= 1000]
        if not inbound:
            return False
        if len(inbound) >= 100:
            return True
        last = max(inbound, key=lambda f: int(f.stem.split("_w")[1]))
        res = json.loads(last.read_text(encoding="utf-8"))["response"].get("result") or {}
        return not res.get("pageKey") or not res.get("transfers")
    return any(d.glob("txlistinternal_w*.json"))


# BSCTrace (MegaNode) dùng cho BSC vì Etherscan free-tier không hỗ trợ
# (xem src/collect/bsctrace_client.py). Client type khác nhau -> dispatch
# theo chain ở collect_address_raw_data/load_events_for_addresses.
BSC_CHAINS = {"bsc"}


def collect_address_raw_data(
    client, chain: str, address: str, incident_id: str, start_block: int, end_block: int
) -> None:
    """Gọi API thật cho 1 address, cache vào data/raw/{chain}/{address}/
    {incident_id}/ (idempotent — nếu đã cache từ trước, client vẫn gọi lại
    API nhưng ghi đè cache CỦA CHÍNH incident_id NÀY; không tự động skip vì
    có thể cần dữ liệu mới hơn).

    `incident_id` SCOPE cache riêng cho từng incident (bug #6, xem
    annotation_guide.md mục 15) — 2 incident dùng chung 1 địa chỉ hạ tầng
    phổ biến với cửa sổ khác nhau sẽ KHÔNG ghi đè cache của nhau nữa.

    `client` là EtherscanClient (eth/arbitrum) hoặc BscTraceClient (bsc) —
    interface khác nhau nên dispatch theo `chain`.
    """
    if chain in BSC_CHAINS:
        # from_block/to_block: KHÔNG có trong tài liệu công khai nhưng ĐÃ
        # XÁC NHẬN hoạt động thật (server lọc đúng) — bắt buộc truyền, nếu
        # không server trả theo thứ tự mặc định có thể bỏ sót hoàn toàn
        # khung thời gian mong muốn (bug thật gặp khi mining hard-negative
        # cho BSC Token Hub 2026-08-13: cache không dùng block filter chỉ
        # phủ block 1-1,021,501, bỏ sót khung ~21.7M-21.9M cần thiết).
        client.fetch_asset_transfers_bidirectional(address, incident_id, from_block=start_block, to_block=end_block)
    else:
        client.fetch_normal_txs(chain, address, incident_id, start_block=start_block, end_block=end_block)
        client.fetch_erc20_transfers(chain, address, incident_id, start_block=start_block, end_block=end_block)
        client.fetch_internal_txs(chain, address, incident_id, start_block=start_block, end_block=end_block)


# ----------------------------------------------------------------------
# Decode
# ----------------------------------------------------------------------
def load_events_for_addresses(
    chain: str, addresses: List[str], incident_id: str, bridge_index: dict, mixer_index: Optional[dict] = None,
    lending_index: Optional[dict] = None,
) -> List[CanonicalEvent]:
    """`addresses` PHẢI là list có thứ tự ổn định (không dùng set trực tiếp)
    để log_index giả (internal tx/BSCTrace) không đổi giữa các lần chạy —
    quan trọng cho khả năng tái lập (reproducibility).

    `incident_id`: đọc cache SCOPED theo incident này (bug #6, xem
    annotation_guide.md mục 15) — không lẫn dữ liệu của incident khác dùng
    chung địa chỉ.
    """
    if chain in BSC_CHAINS:
        return _load_events_bsctrace(chain, addresses, incident_id, bridge_index, mixer_index, lending_index)
    return _load_events_etherscan(chain, addresses, incident_id, bridge_index, mixer_index)


def _load_events_etherscan(
    chain: str, addresses: List[str], incident_id: str, bridge_index: dict, mixer_index: Optional[dict]
) -> List[CanonicalEvent]:
    chain_id = CHAIN_IDS[chain]
    events: List[CanonicalEvent] = []
    internal_seq = 0
    for addr in addresses:
        for row in _load_cached_rows(chain, addr, incident_id, "tokentx"):
            events.append(decode_tokentx_row(row, chain_id=chain_id, bridge_address_index=bridge_index))
        for row in _load_cached_rows(chain, addr, incident_id, "txlist"):
            ev = decode_normal_tx_row(row, chain_id=chain_id, mixer_address_index=mixer_index, bridge_address_index=bridge_index)
            if ev is not None:
                events.append(ev)
        for row in _load_cached_rows(chain, addr, incident_id, "txlistinternal"):
            ev = decode_internal_tx_row(row, chain_id=chain_id, sequence=internal_seq, bridge_address_index=bridge_index)
            internal_seq += 1
            if ev is not None:
                events.append(ev)
    return merge_events_into_semantic_actions(events)


def _load_events_bsctrace(
    chain: str, addresses: List[str], incident_id: str, bridge_index: dict, mixer_index: Optional[dict],
    lending_index: Optional[dict] = None,
) -> List[CanonicalEvent]:
    chain_id = CHAIN_IDS[chain]
    events: List[CanonicalEvent] = []
    for addr in addresses:
        for row in _load_cached_bsctrace_rows(addr, incident_id):
            ev = decode_bsctrace_transfer_row(
                row, chain_id=chain_id,
                bridge_address_index=bridge_index, mixer_address_index=mixer_index,
                lending_address_index=lending_index,
            )
            if ev is not None:
                events.append(ev)
    return merge_events_into_semantic_actions(events)


def find_provenance_bridge_events(chain: str, seed: str, incident_id: str, bridge_index: dict) -> List[CanonicalEvent]:
    """Sự kiện đưa tiền VÀO seed từ 1 bridge contract đã verify — bằng chứng
    seed là incident-linked, KHÔNG thuộc outbound trajectory (builder chỉ mở
    rộng forward từ seed). Xem docstring gốc trong pilot cũ.
    """
    chain_id = CHAIN_IDS[chain]
    events: List[CanonicalEvent] = []
    seq = 0

    if chain in BSC_CHAINS:
        for row in _load_cached_bsctrace_rows(seed, incident_id):
            # decode_bsctrace_transfer_row chỉ gắn nhãn bridge_withdraw cho
            # category="20" (ERC-20) — native BNB (external/internal) không
            # được classify tự động, nên kiểm tra thủ công from/to giống
            # nhánh Etherscan bên dưới (bug thật phát hiện ở BSC Token Hub
            # 2026-08-13: 2,000,000 BNB provenance là internal tx, bị bỏ sót
            # nếu chỉ dựa vào decode_bsctrace_transfer_row's event_type).
            if row.get("from", "").lower() in bridge_index and row.get("to", "").lower() == seed.lower():
                ev = decode_bsctrace_transfer_row(row, chain_id=chain_id, bridge_address_index=bridge_index)
                if ev is not None:
                    events.append(ev)
        return events

    for row in _load_cached_rows(chain, seed, incident_id, "tokentx"):
        ev = decode_tokentx_row(row, chain_id=chain_id, bridge_address_index=bridge_index)
        if ev.event_type == "bridge_withdraw" and ev.dst == seed.lower():
            events.append(ev)
    for row in _load_cached_rows(chain, seed, incident_id, "txlistinternal"):
        if row["from"].lower() in bridge_index and row["to"].lower() == seed.lower():
            ev = decode_internal_tx_row(row, chain_id=chain_id, sequence=seq)
            seq += 1
            if ev is not None:
                events.append(ev)
    return events


def find_swap_evidence(
    chain: str, addresses: List[str], incident_id: str, start_block: int, end_block: int, bridge_index: dict, mixer_index: Optional[dict] = None
) -> List[CanonicalEvent]:
    """Sự kiện swap thật (DEX) trong số các address đã xử lý, trong cửa sổ
    [start_block, end_block] — CHỈ dùng làm bằng chứng bổ sung cho gate
    check, KHÔNG ép vào outbound trajectory. Cùng lý do với
    find_provenance_bridge_events(): swap "chảy vào" 1 address (vd LP pool
    -> ví) không có src nằm trong node_depth của builder forward-only, nên
    tự nhiên bị loại khỏi trajectory dù là bằng chứng DEX thật.
    """
    all_events = load_events_for_addresses(chain, addresses, incident_id, bridge_index, mixer_index=mixer_index)
    return [e for e in all_events if e.event_type == "swap" and start_block <= e.block_number <= end_block]


# ----------------------------------------------------------------------
# Mở rộng frontier + build trajectory (bounded value-flow expansion thật)
# ----------------------------------------------------------------------
def expand_and_build_trajectory(
    chain: str,
    seed: str,
    start_block: int,
    incident_id: str,
    label: int,
    config: Optional[TrajectoryConfig] = None,
    do_collect: bool = True,
    max_iterations: Optional[int] = None,
    client: Optional[object] = None,
    request_delay_sec: float = 0.4,
    collect_workers: int = 1,
) -> Tuple[Trajectory, List[CanonicalEvent], List[str]]:
    """Lặp: fetch (nếu do_collect) -> decode -> build_trajectory -> lấy dst
    của action được chấp nhận làm frontier kế tiếp -> lặp tới khi hội tụ.

    `client`: EtherscanClient (eth/arbitrum) hoặc BscTraceClient (bsc). Nếu
    không truyền, tự khởi tạo đúng loại theo `chain`.

    Trả về (trajectory, provenance_events, addresses_processed).
    """
    if config is None:
        config = load_trajectory_config()
    if max_iterations is None:
        max_iterations = config.expand_iterations
    if client is None and do_collect:
        client = BscTraceClient(cache_dir=RAW_DIR) if chain in BSC_CHAINS else EtherscanClient(cache_dir=RAW_DIR)

    end_block = compute_end_block(chain, start_block, config)

    protocol_map = load_protocol_map()
    bridge_index = build_verified_bridge_address_index(protocol_map)
    mixer_index = build_verified_mixer_address_index(protocol_map)
    lending_index = build_verified_lending_address_index(protocol_map)
    known_protocol_allowlist = config.allowlist

    processed: List[str] = []
    processed_set: set = set()
    frontier = [seed.lower()]
    traj: Optional[Trajectory] = None

    for _ in range(max_iterations + 1):  # +1: iteration cuối chỉ để xác nhận hội tụ
        to_fetch = [a for a in frontier if a not in processed_set]
        if not to_fetch:
            break
        if do_collect and collect_workers > 1 and len(to_fetch) > 1:
            # Chi song song hoa buoc GOI API (moi dia chi 1 thu muc cache
            # rieng); thu tu `processed` van giu nguyen thu tu frontier.
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=collect_workers) as pool:
                list(pool.map(lambda a: collect_address_raw_data(client, chain, a, incident_id, start_block, end_block),
                              to_fetch))
        for addr in to_fetch:
            if do_collect and not (collect_workers > 1 and len(to_fetch) > 1):
                collect_address_raw_data(client, chain, addr, incident_id, start_block, end_block)
                time.sleep(request_delay_sec)
            processed.append(addr)
            processed_set.add(addr)

        events = load_events_for_addresses(chain, processed, incident_id, bridge_index, mixer_index=mixer_index, lending_index=lending_index)
        # Lọc event NGOÀI [start_block, end_block]: bắt buộc với BSCTrace
        # (không hỗ trợ lọc block-range server-side, trả về TOÀN BỘ lịch sử
        # của address) — nếu không lọc, event pool trải dài nhiều tuần/năm
        # thay vì đúng cửa sổ incident, gây 2 lỗi: (1) start_time lấy từ
        # event xa nhất trong lịch sử, sai lệch time_horizon_hours; (2)
        # outflow_by_src (mẫu số tainted-share) bị pha loãng bởi hàng trăm
        # giao dịch KHÔNG liên quan incident, khiến value_share của giao
        # dịch thật không bao giờ đạt min_tainted_share (bug thật phát hiện
        # khi chạy QBridge 2026-08-13: max_share=1.4% dù có 120 giao dịch
        # thật từ seed, do mẫu số cộng dồn cả 5 tuần thay vì ~72h).
        # Vô hại với Etherscan (đã lọc theo startblock/endblock ở tầng API,
        # lọc lại lần nữa ở đây chỉ là no-op).
        events = [e for e in events if start_block <= e.block_number <= end_block]
        traj = build_trajectory(
            events,
            seed_address=seed,
            config=config,
            incident_id=incident_id,
            label=label,
            trajectory_id=incident_id,
        )
        # Không fetch tiếp địa chỉ protocol đã verify (bridge/DEX/mixer) —
        # đây là hạ tầng dùng chung, build_trajectory cũng không mở rộng
        # node_depth qua chúng (xem src/trajectories/builder.py), fetch dữ
        # liệu của chính contract đó (vd toàn bộ tx của 1 DEX router) vừa
        # lãng phí quota vừa vô nghĩa.
        # Bug thật phát hiện 2026-08-14 (rà soát cache/pagination hệ thống,
        # xem annotation_guide.md mục 14): dùng set-comprehension trực tiếp
        # ({a.dst for a in traj.actions}) làm thứ tự lặp phụ thuộc hash-seed
        # ngẫu nhiên của Python, KHÁC NHAU giữa các lần chạy process riêng
        # biệt (do_collect=True lúc build vs do_collect=False lúc rebuild
        # test) — khiến thứ tự xử lý địa chỉ trong `processed` không ổn định,
        # có thể làm merge_events_into_semantic_actions cho kết quả khác
        # nhau dù cùng 1 bộ dữ liệu cache (vd wault_finance_2021: 11 vs 15
        # action tuỳ lần chạy). Dùng dict.fromkeys để khử trùng lặp NHƯNG
        # giữ đúng thứ tự xuất hiện đầu tiên trong traj.actions (ổn định,
        # tái lập được).
        frontier = [d for d in dict.fromkeys(a.dst for a in traj.actions) if d not in known_protocol_allowlist]

    if traj is None:
        # Không có action nào (seed không có dữ liệu) — vẫn trả trajectory rỗng
        traj = build_trajectory([], seed_address=seed, config=config, incident_id=incident_id, label=label, trajectory_id=incident_id)

    provenance_events = find_provenance_bridge_events(chain, seed, incident_id, bridge_index)
    return traj, provenance_events, processed


# ----------------------------------------------------------------------
# Entry point cấp incident (đọc từ registry)
# ----------------------------------------------------------------------
def run_incident_pipeline(
    incident_id: str,
    do_collect: bool = True,
    max_iterations: Optional[int] = None,
    registry_path: Path = REGISTRY_PATH,
    write_output: bool = True,
) -> Tuple[Trajectory, List[CanonicalEvent], List[str]]:
    row = load_incident_row(incident_id, registry_path=registry_path)
    chain = row["chain_primary"]
    seed = row["seed_address"]
    start_block = int(row["start_block"])
    label = int(row["label"])  # cột tường minh trong registry — không suy đoán từ tên incident_id

    config = load_trajectory_config()
    traj, provenance_events, processed = expand_and_build_trajectory(
        chain, seed, start_block, incident_id, label, config=config,
        do_collect=do_collect, max_iterations=max_iterations,
    )

    if write_output:
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        out_path = PROCESSED_DIR / f"{incident_id}_events.json"
        out_path.write_text(
            json.dumps([json.loads(a.model_dump_json()) for a in traj.actions], indent=2, default=str),
            encoding="utf-8",
        )

    return traj, provenance_events, processed
