"""
Normalizer/decoder — Bước 3. Xem metadata/protocol_map.yaml.

QUAN TRỌNG — chặn cứng trước khi dùng bridge/DEX address thật:
Mọi entry trong metadata/protocol_map.yaml hiện có `verify_status` bắt đầu
bằng "CHƯA_VERIFY" — các địa chỉ này được điền từ memory của LLM, CHƯA được
đối chiếu với block explorer thật. `load_protocol_map()` sẽ raise
`ProtocolMapNotVerifiedError` nếu bất kỳ entry nào cần dùng để decode bridge
event vẫn còn ở trạng thái này — đây là hành vi ĐÚNG Ý ĐỊNH (DỪNG LẠI và báo
người dùng), không phải bug. Chỉ sau khi người dùng tự đối chiếu on-chain và
cập nhật `verify_status` thành "verified" (hoặc tương đương) thì
`decode_bridge_event` mới được phép chạy với entry đó.

Việc decode `transfer` (ERC-20 Transfer log chuẩn EIP, topic0 cố định theo
spec — không phải địa chỉ hợp đồng cụ thể nào) và phân loại swap/split/merge
generic (dựa trên cấu trúc tx: đổi token, fan-out, fan-in) KHÔNG phụ thuộc
vào protocol_map.yaml nên có thể chạy ngay.
"""
from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import yaml

from src.normalize.schema import CanonicalEvent

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROTOCOL_MAP_PATH = REPO_ROOT / "metadata" / "protocol_map.yaml"

# Chuẩn ERC-20 Transfer(address indexed from, address indexed to, uint256 value)
# keccak256("Transfer(address,address,uint256)") — hằng số theo spec Solidity/EIP-20,
# KHÔNG phải địa chỉ hợp đồng, không cần verify_status.
ERC20_TRANSFER_TOPIC0 = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

UNVERIFIED_MARKER = "CHƯA_VERIFY"


class ProtocolMapNotVerifiedError(RuntimeError):
    """Raised khi cố dùng một protocol_map entry chưa được người dùng verify."""


def load_protocol_map(path: Path = DEFAULT_PROTOCOL_MAP_PATH) -> Dict[str, List[Dict[str, Any]]]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _is_verified(entry: Dict[str, Any]) -> bool:
    status = str(entry.get("verify_status", "")).strip()
    return bool(status) and not status.upper().startswith(UNVERIFIED_MARKER)


def require_verified_entry(entry: Dict[str, Any]) -> None:
    """Chặn cứng: raise nếu entry chưa được verify.

    Gọi hàm này TRƯỚC khi dùng contract_addresses/router_addresses của entry
    để crawl hoặc decode bridge/DEX event thật.
    """
    if not _is_verified(entry):
        raise ProtocolMapNotVerifiedError(
            f"Protocol map entry '{entry.get('name')}' có verify_status="
            f"'{entry.get('verify_status')}' — CHƯA được đối chiếu on-chain thật. "
            "DỪNG LẠI: không được dùng address này để crawl/decode cho tới khi "
            "người dùng tự verify và cập nhật verify_status trong "
            "metadata/protocol_map.yaml."
        )


def list_unverified_entries(protocol_map: Dict[str, List[Dict[str, Any]]]) -> List[str]:
    """Trả về danh sách tên entry còn CHƯA_VERIFY, để cảnh báo người dùng."""
    names = []
    for category in ("bridges", "dexes"):
        for entry in protocol_map.get(category, []) or []:
            if not _is_verified(entry):
                names.append(entry["name"])
    return names


# ----------------------------------------------------------------------
# ERC-20 transfer decoding (không phụ thuộc protocol_map.yaml)
# ----------------------------------------------------------------------
def _topic_to_address(topic: str) -> str:
    # topic là 32-byte hex; address là 20 byte cuối
    return "0x" + topic[-40:]


def decode_erc20_transfer_log(
    log: Dict[str, Any],
    chain_id: int,
    decimals: int = 18,
) -> CanonicalEvent:
    """Decode một ERC-20 Transfer log (dạng eth_getLogs / Etherscan `tokentx`
    row đã có topics) thành CanonicalEvent event_type='transfer'.

    `log` kỳ vọng có: topics (list[str], topics[0]==ERC20_TRANSFER_TOPIC0),
    data (hex string uint256 value), address (token contract), blockNumber,
    timeStamp (unix seconds), transactionHash, logIndex.
    """
    topics = log["topics"]
    if topics[0].lower() != ERC20_TRANSFER_TOPIC0.lower():
        raise ValueError(f"topic0 không phải ERC-20 Transfer: {topics[0]}")

    src = _topic_to_address(topics[1]).lower()
    dst = _topic_to_address(topics[2]).lower()
    raw_value = int(log["data"], 16) if isinstance(log["data"], str) else int(log["data"])
    amount_norm = _log_scale_amount(raw_value, decimals)

    return CanonicalEvent(
        chain_id=chain_id,
        block_number=int(log["blockNumber"], 16) if str(log["blockNumber"]).startswith("0x") else int(log["blockNumber"]),
        timestamp=_to_utc_datetime(log["timeStamp"]),
        tx_hash=log["transactionHash"],
        log_index=int(log["logIndex"], 16) if str(log["logIndex"]).startswith("0x") else int(log["logIndex"]),
        src=src,
        dst=dst,
        event_type="transfer",
        amount_norm=amount_norm,
        token=log.get("token_symbol") or log.get("address"),
        source_confidence=1.0,
    )


def _log_scale_amount(raw_value: int, decimals: int) -> float:
    """log1p(raw_value / 10**decimals) — chuẩn hóa raw ERC-20 amount thành
    thang log, đúng yêu cầu amount_norm không phải raw amount (Bước 1)."""
    scaled = raw_value / (10 ** decimals)
    return math.log1p(scaled)


def _to_utc_datetime(ts: Any) -> datetime:
    if isinstance(ts, datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    return datetime.fromtimestamp(int(ts), tz=timezone.utc)


# ----------------------------------------------------------------------
# Adapter cho response THẬT của Etherscan-family API (module=account,
# action=txlist/tokentx/txlistinternal) — khác format với eth_getLogs
# (không có topics/data, đã có sẵn from/to/value/tokenDecimal dạng phẳng).
# Không phụ thuộc protocol_map.yaml để decode transfer thô; chỉ dùng
# protocol_map (đã verify) để GẮN NHÃN bridge_deposit/bridge_withdraw khi
# from/to khớp đúng 1 contract address đã verify.
# ----------------------------------------------------------------------
def build_verified_bridge_address_index(
    protocol_map: Dict[str, List[Dict[str, Any]]]
) -> Dict[str, Dict[str, Any]]:
    """address (lowercase) -> protocol_entry, CHỈ gồm entry đã verify.

    Entry chưa verify bị loại khỏi index (không raise ở đây — loader chỉ
    xây "danh bạ" để tra cứu; require_verified_entry() vẫn là chặn cứng khi
    thật sự decode một bridge event).
    """
    index: Dict[str, Dict[str, Any]] = {}
    for entry in protocol_map.get("bridges", []) or []:
        if not _is_verified(entry):
            continue
        for addr in (entry.get("contract_addresses") or {}).values():
            index[addr.lower()] = entry
    return index


def build_verified_mixer_address_index(
    protocol_map: Dict[str, List[Dict[str, Any]]]
) -> Dict[str, Dict[str, Any]]:
    """address (lowercase) -> mixer/exit-service entry, CHỈ gồm entry đã
    verify trong `mixers_exit_services` (metadata/protocol_map.yaml)."""
    index: Dict[str, Dict[str, Any]] = {}
    for entry in protocol_map.get("mixers_exit_services", []) or []:
        if not _is_verified(entry):
            continue
        for addr in (entry.get("contract_addresses") or {}).values():
            index[addr.lower()] = entry
    return index


def build_verified_lending_address_index(
    protocol_map: Dict[str, List[Dict[str, Any]]]
) -> Dict[str, Dict[str, Any]]:
    """address (lowercase) -> lending/money-market protocol entry, CHỈ gồm
    entry đã verify trong `lending_protocols` (metadata/protocol_map.yaml).
    Thêm 2026-08-13 (Venus Protocol) để bắt dòng tiền "gửi vào lending market
    làm collateral" — cùng vai trò "sink" như bridge_deposit nhưng KHÔNG phải
    bridge/DEX/mixer."""
    index: Dict[str, Dict[str, Any]] = {}
    for entry in protocol_map.get("lending_protocols", []) or []:
        if not _is_verified(entry):
            continue
        for addr in (entry.get("contract_addresses") or {}).values():
            index[addr.lower()] = entry
    return index


# Etherscan API V2 (unified) `module=account&action=tokentx` KHÔNG trả field
# `logIndex` thật cho BẤT KỲ dòng nào (xác nhận 2026-08-13: 100% dòng tokentx
# đã cache, cả eth lẫn arbitrum, có logIndex=null/thiếu — không phải lỗi cache
# 1 địa chỉ cụ thể). Nếu dùng `int(row.get("logIndex", 0) or 0)` như cũ, MỌI
# tokentx event đều có log_index=0 cố định -> dedup_key trùng bất cứ khi nào 1
# tx có >=2 leg ERC-20 (rất phổ biến với swap qua router/aggregator) -> bug
# CÙNG HỌ với bug traceIndex/logIndex của BSCTrace (xem
# _bsctrace_effective_log_index ở decode_bsctrace_transfer_row), nhưng phía
# Etherscan. Không có field per-log ordering nào khác trong response (không có
# traceIndex tương đương) — dùng hash nội dung leg (from/to/value/token contract)
# làm chỉ số giả ỔN ĐỊNH: cùng 1 leg thật, dù được decode LẦN THỨ MẤY (vd khi
# cả 2 địa chỉ tham gia tx đều nằm trong danh sách đang trace, tx đó bị fetch
# ĐỘC LẬP từ cache của CẢ 2 địa chỉ — xem merge_events_into_semantic_actions,
# bug thật phát hiện khi verify bsc_token_hub_2022/ronin_benign_control_2022
# 2026-08-13), luôn hash ra CÙNG 1 log_index giả -> dedup đúng thành 1 bản ghi;
# 2 leg THẬT khác nhau trong cùng tx (khác from/to/value) hash ra log_index
# giả KHÁC NHAU -> không bị gộp nhầm.
def _tokentx_effective_log_index(row: Dict[str, Any]) -> int:
    raw_log_index = row.get("logIndex")
    if raw_log_index not in (None, ""):
        return int(raw_log_index)
    basis = f"{row.get('from','')}|{row.get('to','')}|{row.get('value','')}|{row.get('contractAddress','')}"
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()
    return 800_000 + (int(digest[:8], 16) % 100_000)


def decode_tokentx_row(
    row: Dict[str, Any],
    chain_id: int,
    bridge_address_index: Optional[Dict[str, Dict[str, Any]]] = None,
) -> CanonicalEvent:
    """Decode 1 dòng kết quả `module=account&action=tokentx` (ERC-20
    transfer, đã có sẵn from/to/value/tokenDecimal — không cần parse topics).

    Nếu `from`/`to` khớp 1 bridge contract đã verify trong
    `bridge_address_index` (xem build_verified_bridge_address_index), gắn
    event_type bridge_withdraw (tiền RA khỏi bridge) / bridge_deposit (tiền
    VÀO bridge) tương ứng; ngược lại giữ event_type='transfer'.
    """
    decimals = int(row.get("tokenDecimal", 18))
    raw_value = int(row["value"])
    src = row["from"].lower()
    dst = row["to"].lower()

    event_type = "transfer"
    protocol = None
    if bridge_address_index:
        if src in bridge_address_index:
            event_type = "bridge_withdraw"
            protocol = bridge_address_index[src]["name"]
        elif dst in bridge_address_index:
            event_type = "bridge_deposit"
            protocol = bridge_address_index[dst]["name"]

    return CanonicalEvent(
        chain_id=chain_id,
        block_number=int(row["blockNumber"]),
        timestamp=_to_utc_datetime(row["timeStamp"]),
        tx_hash=row["hash"],
        log_index=_tokentx_effective_log_index(row),
        src=src,
        dst=dst,
        event_type=event_type,
        amount_norm=_log_scale_amount(raw_value, decimals),
        protocol=protocol,
        token=row.get("tokenSymbol"),
        source_confidence=1.0,
    )


def decode_normal_tx_row(
    row: Dict[str, Any],
    chain_id: int,
    mixer_address_index: Optional[Dict[str, Dict[str, Any]]] = None,
    bridge_address_index: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Optional[CanonicalEvent]:
    """Decode 1 dòng kết quả `module=account&action=txlist` (native ETH tx).

    Trả về None nếu `value`==0 VÀ không có ETH thực sự di chuyển (vd contract
    call thuần với payload trong `input`, giá trị ETH đã được phản ánh riêng
    qua ERC-20 tokentx/log) — tránh tạo event rác event_type='transfer'
    amount 0 gây nhiễu feature/motif.

    Nếu `to` khớp 1 mixer/exit-service đã verify trong `mixer_address_index`
    (xem build_verified_mixer_address_index), gắn event_type='mixer_or_exit'
    thay vì 'transfer'. Nếu `to`/`from` khớp 1 bridge đã verify trong
    `bridge_address_index`, gắn event_type='bridge_deposit'/'bridge_withdraw'
    — nhiều hàm bridge (vd Multichain `anySwapOutNative`, Stargate `swapETH`)
    nhận native ETH trực tiếp kèm call, KHÔNG qua ERC-20 transfer log, nên
    PHẢI check ở đây (native tx), không chỉ ở decode_tokentx_row. Bug thật
    phát hiện 2026-08-14 khi thêm Chibi Finance: thiếu check này khiến bridge
    deposit 400+156 ETH bị decode thành 'transfer' chung chung, mất hoàn
    toàn bằng chứng bridge trong outbound trajectory dù dữ liệu on-chain có
    đủ (tương tự decode_bsctrace_transfer_row đã check MỌI category từ
    trước, không chỉ ERC-20 — xem comment ở đó).
    """
    raw_value = int(row.get("value", 0))
    if raw_value == 0:
        return None
    src = row["from"].lower()
    dst = row["to"].lower()
    event_type = "transfer"
    protocol = None
    if bridge_address_index:
        if src in bridge_address_index:
            event_type = "bridge_withdraw"
            protocol = bridge_address_index[src]["name"]
        elif dst in bridge_address_index:
            event_type = "bridge_deposit"
            protocol = bridge_address_index[dst]["name"]
    if event_type == "transfer" and mixer_address_index and dst in mixer_address_index:
        event_type = "mixer_or_exit"
        protocol = mixer_address_index[dst]["name"]
    return CanonicalEvent(
        chain_id=chain_id,
        block_number=int(row["blockNumber"]),
        timestamp=_to_utc_datetime(row["timeStamp"]),
        tx_hash=row["hash"],
        log_index=0,  # txlist không có log_index (không phải log ERC-20); dùng 0 quy ước cho native ETH tx
        src=src,
        dst=dst,
        event_type=event_type,
        amount_norm=_log_scale_amount(raw_value, decimals=18),
        protocol=protocol,
        token="ETH",
        source_confidence=1.0,
    )


# log_index giả cho internal tx (không có log_index thật vì không phải
# ERC-20 log) — offset lớn để không đụng log_index thật của event ERC-20
# cùng tx_hash (vd chân "ETH nhận về" của 1 swap, cùng hash với chân "USDC
# gửi đi" đã có log_index nhỏ từ tokentx).
_INTERNAL_TX_LOG_INDEX_OFFSET = 900_000


def decode_internal_tx_row(
    row: Dict[str, Any],
    chain_id: int,
    sequence: int,
    bridge_address_index: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Optional[CanonicalEvent]:
    """Decode 1 dòng kết quả `module=account&action=txlistinternal`.

    `sequence`: số thứ tự internal tx trong batch đang decode (client tự
    quản lý, tăng dần), dùng để tạo log_index giả duy nhất — Etherscan
    không trả log_index thật cho internal tx (chỉ có `traceId` dạng chuỗi
    không đồng nhất giữa các internal tx tool).

    Trả về None nếu `isError`=='1' (tx internal bị revert, không có value
    thực sự di chuyển) hoặc value==0.

    `bridge_address_index`: cùng lý do với decode_normal_tx_row — 1 số bridge
    forward native ETH qua internal call (không phải external tx trực tiếp)
    — thêm 2026-08-14 để đồng bộ 3 decoder ETH-side (tokentx/normal_tx/
    internal_tx) đều check bridge_address_index như BSCTrace đã làm.
    """
    if str(row.get("isError", "0")) == "1":
        return None
    raw_value = int(row.get("value", 0))
    if raw_value == 0:
        return None
    src = row["from"].lower()
    dst = row["to"].lower()
    event_type = "transfer"
    protocol = None
    if bridge_address_index:
        if src in bridge_address_index:
            event_type = "bridge_withdraw"
            protocol = bridge_address_index[src]["name"]
        elif dst in bridge_address_index:
            event_type = "bridge_deposit"
            protocol = bridge_address_index[dst]["name"]
    return CanonicalEvent(
        chain_id=chain_id,
        block_number=int(row["blockNumber"]),
        timestamp=_to_utc_datetime(row["timeStamp"]),
        tx_hash=row["hash"],
        log_index=_INTERNAL_TX_LOG_INDEX_OFFSET + sequence,
        src=src,
        dst=dst,
        event_type=event_type,
        amount_norm=_log_scale_amount(raw_value, decimals=18),
        protocol=protocol,
        token="ETH",
        source_confidence=1.0,
    )


# ----------------------------------------------------------------------
# Adapter cho BSCTrace/MegaNode (src/collect/bsctrace_client.py) — dùng cho
# BSC khi Etherscan free-tier không hỗ trợ.
#
# Schema dưới đây đã XÁC NHẬN qua smoke_test() với key thật ngày 2026-08-13
# (địa chỉ 0xd01ae1a708614948b2b5e0b7ab5be6afa01325c7 — QBridge exploiter),
# KHÔNG phải suy đoán:
#   - category hợp lệ: {external, internal, 20, 721, 1155, state, deposit,
#     withdraw} — "20" là ERC-20 (KHÔNG phải "erc20")
#   - `value`: hex string RAW base-unit (vd "0x0ac9ae05a71ebc0000"), cần
#     int(value,16) rồi chia 10**decimal — KHÔNG phải decimal có sẵn
#   - `decimal`: string số thập phân (vd "18"), CHỈ có ở category="20"
#     (native external/internal luôn 18 decimals, không có field này)
#   - `blockNum`: hex string ("0x...")
#   - `blockTimeStamp`: unix timestamp (int) Ở TOP-LEVEL, KHÔNG nested
#     trong "metadata" như giả định ban đầu
#   - `logIndex`: field THẬT có sẵn (int) — không cần offset giả như
#     decode_internal_tx_row của Etherscan
#   - `asset`: token symbol (native "BNB" hoặc ERC-20 symbol)
#   - pageKey (không phải pageToken) dùng cho phân trang — xem bsctrace_client.py
# ----------------------------------------------------------------------
def decode_bsctrace_transfer_row(
    row: Dict[str, Any],
    chain_id: int,
    bridge_address_index: Optional[Dict[str, Dict[str, Any]]] = None,
    mixer_address_index: Optional[Dict[str, Dict[str, Any]]] = None,
    lending_address_index: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Optional[CanonicalEvent]:
    """Decode 1 record từ BSCTrace `nr_getAssetTransfers` thành CanonicalEvent.

    Trả về None nếu raw value == 0 (dust/contract-call thuần, tương tự
    decode_normal_tx_row/decode_internal_tx_row).
    """
    category = row.get("category", "external")
    raw_value_hex = row.get("value")
    if raw_value_hex is None:
        return None
    raw_value = int(raw_value_hex, 16) if str(raw_value_hex).startswith("0x") else int(raw_value_hex)
    if raw_value == 0:
        return None

    decimals = int(row["decimal"]) if category == "20" and "decimal" in row else 18
    src = row["from"].lower()
    dst = row["to"].lower()

    event_type = "transfer"
    protocol = None
    # Bridge có thể chuyển native token (BNB) hoặc ERC-20 — áp dụng phân
    # loại cho MỌI category, không chỉ "20" (bug thật phát hiện ở BSC Token
    # Hub 2026-08-13: provenance 2,000,000 BNB là category="internal", bị
    # bỏ sót nếu chỉ classify cho ERC-20).
    if bridge_address_index:
        if src in bridge_address_index:
            event_type = "bridge_withdraw"
            protocol = bridge_address_index[src]["name"]
        elif dst in bridge_address_index:
            event_type = "bridge_deposit"
            protocol = bridge_address_index[dst]["name"]
    if event_type == "transfer" and mixer_address_index and dst in mixer_address_index:
        event_type = "mixer_or_exit"
        protocol = mixer_address_index[dst]["name"]
    # Lending protocol (vd Venus) — gửi vào (mint/supply collateral) hoặc rút
    # ra (redeem). Thêm 2026-08-13 để bắt dòng tiền chính bị bỏ sót ở
    # bsc_token_hub_2022 (900,000 BNB vào Venus, xem protocol_map.yaml).
    if event_type == "transfer" and lending_address_index:
        if dst in lending_address_index:
            event_type = "lending_deposit"
            protocol = lending_address_index[dst]["name"]
        elif src in lending_address_index:
            event_type = "lending_withdraw"
            protocol = lending_address_index[src]["name"]

    block_num_raw = row["blockNum"]
    block_number = int(block_num_raw, 16) if str(block_num_raw).startswith("0x") else int(block_num_raw)

    ts_raw = row.get("blockTimeStamp")
    if ts_raw is None:
        raise ValueError(f"Thiếu blockTimeStamp trong BSCTrace transfer row: {row!r}")
    timestamp = datetime.fromtimestamp(int(ts_raw), tz=timezone.utc)

    return CanonicalEvent(
        chain_id=chain_id,
        block_number=block_number,
        timestamp=timestamp,
        tx_hash=row["hash"],
        log_index=_bsctrace_effective_log_index(row, category),
        src=src,
        dst=dst,
        event_type=event_type,
        amount_norm=_log_scale_amount(raw_value, decimals),
        protocol=protocol,
        token=row.get("asset") or ("BNB" if category in ("external", "internal") else None),
        source_confidence=1.0,
    )


# category="external"/"internal" (native BNB) không phải EVM log thật ->
# BSCTrace trả `logIndex=0` CỐ ĐỊNH cho MỌI leg loại này trong cùng tx_hash
# (không phải giá trị duy nhất per-leg) — nếu dùng logIndex=0 làm khóa dedup
# (chain_id, tx_hash, log_index), 2 leg khác nhau (vd "seed gửi BNB vào
# router" và "router trả BNB về seed", cùng tx_hash) bị coi là TRÙNG NHAU và
# CanonicalEvent._dedup() chỉ giữ lại 1 leg, làm mất event thật.
# Bug thật phát hiện 2026-08-13 (hard-negative mining): qbridge_qubit_2022
# và bsc_token_hub_2022 mất tổng 9/17 trajectory rỗng vì lý do này — event
# "seed -> PancakeSwap" (traceIndex=0, logIndex=0) bị dedup mất bởi event
# "PancakeSwap -> seed" (traceIndex=12, logIndex=0) cùng tx_hash.
# Field `traceIndex` MỚI là định danh thật duy nhất cho từng leg native
# trong 1 tx (xác nhận qua dữ liệu thật: traceIndex=0 vs traceIndex=12 cho
# 2 leg khác nhau cùng tx_hash) — dùng traceIndex thay logIndex cho 2
# category này, cộng offset để không đụng logIndex thật của category="20"
# (ERC-20 log thật) trong cùng tx_hash.
_BSCTRACE_NATIVE_LOG_INDEX_OFFSET = {"external": 600_000, "internal": 700_000}


def _bsctrace_effective_log_index(row: Dict[str, Any], category: str) -> int:
    if category in _BSCTRACE_NATIVE_LOG_INDEX_OFFSET:
        trace_index = int(row.get("traceIndex", 0) or 0)
        return _BSCTRACE_NATIVE_LOG_INDEX_OFFSET[category] + trace_index
    return int(row.get("logIndex", 0) or 0)


# ----------------------------------------------------------------------
# Bridge decoding — CHẶN CỨNG cho tới khi entry được verify
# ----------------------------------------------------------------------
def decode_bridge_event(
    log: Dict[str, Any],
    chain_id: int,
    protocol_entry: Dict[str, Any],
    direction: str,
    decimals: int = 18,
) -> CanonicalEvent:
    """Decode một bridge deposit/withdraw log, dùng contract address đã
    VERIFY trong `protocol_entry` (metadata/protocol_map.yaml).

    `direction` in {"deposit", "withdraw"}. Raise ProtocolMapNotVerifiedError
    nếu protocol_entry chưa qua verify — xem require_verified_entry().
    """
    require_verified_entry(protocol_entry)
    if direction not in ("deposit", "withdraw"):
        raise ValueError("direction phải là 'deposit' hoặc 'withdraw'")

    base = decode_erc20_transfer_log(log, chain_id=chain_id, decimals=decimals)
    return base.model_copy(
        update={
            "event_type": "bridge_deposit" if direction == "deposit" else "bridge_withdraw",
            "protocol": protocol_entry["name"],
        }
    )


# ----------------------------------------------------------------------
# Gộp event trong cùng transaction thành 1 semantic action (generic, không
# cần protocol_map.yaml — dựa trên cấu trúc tx: đổi token, fan-out, fan-in).
# ----------------------------------------------------------------------
# event_type đã gắn nhãn qua địa chỉ contract đã verify (protocol_map.yaml) —
# đáng tin hơn heuristic cấu trúc 'swap' chung, không được ghi đè khi merge.
_PROTOCOL_SPECIFIC_EVENT_TYPES = frozenset({
    "bridge_deposit", "bridge_withdraw", "lending_deposit", "lending_withdraw", "mixer_or_exit",
})
def merge_events_into_semantic_actions(events: Sequence[CanonicalEvent]) -> List[CanonicalEvent]:
    """Gộp các CanonicalEvent cùng tx_hash thành 1 action đại diện/tx khi có
    thể suy ra rõ ràng cấu trúc (swap/split/merge); giữ nguyên nếu tx chỉ có
    1 event hoặc cấu trúc không rõ ràng (an toàn, tránh suy đoán sai).
    """
    # Dedup TRƯỚC khi gộp theo tx_hash — bắt buộc vì caller
    # (_load_events_bsctrace/_load_events_etherscan trong incident_pipeline.py)
    # gọi hàm này với events gộp từ NHIỀU địa chỉ (`addresses`), và 1 giao
    # dịch giữa 2 địa chỉ ĐANG TRACE (vd hop 1 -> hop 2) xuất hiện ĐỘC LẬP
    # trong lịch sử của CẢ 2 địa chỉ (BSCTrace/Etherscan trả về tx theo góc
    # nhìn từng address, không loại trừ tx mà address kia cũng có) -> cùng 1
    # leg bị decode 2 LẦN (1 lần từ cache mỗi địa chỉ), tạo ra 2
    # CanonicalEvent giống hệt nhau (cùng dedup_key). Bug thật phát hiện
    # 2026-08-13 khi verify bsc_token_hub_2022: representative fix (xem
    # comment dưới) tự nó ĐÚNG, nhưng total_amount/len(tx_events) ở nhánh
    # 'swap' tính SAI vì len(tx_events) bị nhân đôi bởi bản sao trùng ->
    # value_share/amount_norm dao động giữa các lần build_trajectory tùy
    # `processed` (frontier) đã mở rộng tới bao nhiêu địa chỉ tại thời điểm
    # đó (builder._dedup() KHÔNG cứu được vì nó chạy SAU merge, khi bản sao
    # đã bị gộp sai thành 1 giá trị trung bình sai). Dedup ở ĐÂY (trước khi
    # gộp theo tx) mới xử lý đúng gốc.
    seen_keys: set = set()
    deduped_events: List[CanonicalEvent] = []
    for ev in events:
        key = ev.dedup_key()
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped_events.append(ev)

    by_tx: Dict[str, List[CanonicalEvent]] = defaultdict(list)
    for ev in deduped_events:
        by_tx[ev.tx_hash].append(ev)

    merged: List[CanonicalEvent] = []
    for tx_hash, tx_events in by_tx.items():
        tx_events = sorted(tx_events, key=lambda e: e.log_index)
        if len(tx_events) == 1:
            merged.append(tx_events[0])
            continue

        tokens = {e.token for e in tx_events if e.token}
        srcs = {e.src for e in tx_events}
        dsts = {e.dst for e in tx_events}
        total_amount = sum(e.amount_norm for e in tx_events)

        # Representative: ưu tiên leg XUẤT PHÁT từ địa chỉ "tự tham chiếu"
        # (self-referencing) — địa chỉ xuất hiện vừa là src của 1 leg vừa là
        # dst của leg còn lại trong CÙNG tx (pattern round-trip chuẩn của 1
        # swap: trader chi token A ra, nhận token B về). KHÔNG dùng
        # tx_events[0] (sort theo log_index) làm mặc định nữa — log_index
        # của leg native (external/internal) là placeholder giả (offset cố
        # định hoặc 0, xem decode_bsctrace_transfer_row/decode_internal_tx_row),
        # KHÔNG phản ánh thứ tự ngữ nghĩa của swap. Bug thật phát hiện
        # 2026-08-13: sau khi sửa log_index native BSC (offset +600000 để hết
        # dedup nhầm), thứ tự sort đảo ngược so với trước, khiến representative
        # đổi từ leg outbound (src=seed) sang leg inbound (src=LP pool) một
        # cách im lặng, làm build_trajectory loại bỏ action vì src không còn
        # nằm trong node_depth — trajectory bsc_token_hub_2022 mất 4/14 action
        # thật. Nếu không tìm được địa chỉ tự tham chiếu (trường hợp hiếm,
        # cấu trúc không rõ ràng), fallback về leg đầu sau khi sort log_index
        # như cũ (an toàn, giữ hành vi cũ khi không xác định được hướng).
        #
        # Trường hợp ĐỐI XỨNG (2 leg, cả 2 địa chỉ đều tự tham chiếu — vd A
        # gửi cho B, B gửi lại cho A, chỉ 2 bên) — outbound_legs có >=2 ứng
        # viên, không rõ bên nào là "trader" thật. Bug thật phát hiện
        # 2026-08-13 khi thêm Venus Protocol (lending_deposit): seed gửi BNB
        # NATIVE vào vBNB contract (leg1, log_index offset lớn) rồi NHẬN LẠI
        # vBNB (leg2, log_index thật nhỏ) — sort tăng dần chọn leg2 (src=vBNB
        # contract) làm representative, SAI (vBNB contract không nằm trong
        # node_depth -> action bị loại, mất toàn bộ 900,000 BNB deposit khỏi
        # trajectory). Ưu tiên leg NATIVE thật (token='BNB'/'ETH') trong số
        # outbound_legs khi ambiguous — bên gửi native LUÔN là actor thật sự
        # gọi hàm payable (chi tiền), khác với leg ERC-20 "phản hồi" (mint
        # receipt token/token đầu ra swap — luôn do contract trả lại, không
        # phải actor). Nếu không có leg native nào trong số ứng viên (vd swap
        # token-token thuần), giữ hành vi cũ (leg đầu sau sort log_index).
        self_addresses = srcs & dsts
        outbound_legs = [e for e in tx_events if e.src in self_addresses]
        if len(outbound_legs) > 1:
            native_outbound = [e for e in outbound_legs if e.token in ("BNB", "ETH")]
            representative = native_outbound[0] if native_outbound else outbound_legs[0]
        else:
            representative = outbound_legs[0] if outbound_legs else tx_events[0]

        # 'swap' CHỈ hợp lệ khi có 1 địa chỉ tự tham chiếu thật (round-trip:
        # 1 bên vừa gửi vừa nhận trong cùng tx) — bổ sung `and self_addresses`
        # 2026-08-13 sau khi phát hiện: 2 nguồn KHÁC NHAU (vd seed và 1 DEX
        # router) cùng gửi 2 TOKEN KHÁC NHAU hội tụ vào 1 địa chỉ đích (đúng
        # pattern 'merge' theo định nghĩa — dsts==1, srcs>=2) vẫn lọt qua điều
        # kiện 'swap' cũ (len(tokens)>=2, len(srcs)<=2, len(dsts)<=2 đều đúng
        # dù không ai thực sự "trade" gì) vì check 'swap' đứng TRƯỚC check
        # 'merge' trong if/elif. Hệ quả thật phát hiện khi verify
        # bsc_token_hub_2022: tx có leg seed->0x46ed8b4a (BNBHACK) + leg
        # router->0x46ed8b4a (WBNB) bị gộp SAI thành 1 'swap' trung bình 2
        # giá trị không liên quan, khiến value_share/outflow_by_src của seed
        # dao động phụ thuộc frontier đã fetch tới 0x46ed8b4a hay chưa (không
        # ổn định, không tái lập được). self_addresses rỗng ở case này (không
        # ai vừa src vừa dst) -> đúng ra phải rơi xuống nhánh 'merge' (giữ
        # riêng từng leg, KHÔNG gộp giá trị) như TX8_MERGE cùng token đã làm.
        if len(tokens) >= 2 and len(srcs) <= 2 and len(dsts) <= 2 and self_addresses:
            # token đổi trong cùng tx, ít counterparty, có round-trip thật -> swap.
            # NGOẠI LỆ: nếu representative đã được gắn nhãn protocol-specific
            # THẬT (bridge_deposit/withdraw, lending_deposit/withdraw,
            # mixer_or_exit — dựa trên địa chỉ contract đã verify trong
            # protocol_map.yaml, đáng tin hơn heuristic cấu trúc 'swap'
            # chung), GIỮ NGUYÊN nhãn đó, không ghi đè thành 'swap'. Bug thật
            # phát hiện 2026-08-13: seed gửi BNB vào Venus (leg1, đã gắn nhãn
            # lending_deposit đúng) + nhận vBNB về (leg2) bị nhánh này ghi đè
            # thành event_type='swap' vô nghĩa, mất nhãn "đây là lending
            # deposit" dù representative/src/dst/amount vẫn đúng.
            is_protocol_specific = representative.event_type in _PROTOCOL_SPECIFIC_EVENT_TYPES
            final_type = representative.event_type if is_protocol_specific else "swap"
            # amount_norm: nhánh 'swap' chung lấy TRUNG BÌNH 2 leg (ước lượng
            # "quy mô giao dịch" khi không rõ token nào là chuẩn). Với event
            # protocol-specific (bridge/lending/mixer deposit-withdraw) thì
            # GIỮ NGUYÊN amount_norm CỦA REPRESENTATIVE (không trung bình với
            # leg receipt/response) — vì đây là 1 khoản deposit/withdraw thật,
            # con số cần báo cáo đúng là số tiền GỬI VÀO/RÚT RA (leg chính),
            # không phải trung bình với token nhận lại (vd receipt token như
            # vBNB thường có decimals/tỷ giá KHÁC hẳn token gốc — trung bình
            # sẽ làm sai lệch giá trị thật). Bug thật phát hiện 2026-08-13:
            # deposit 600,000 BNB vào Venus (log1p(600000)=13.30) bị trung
            # bình với leg vBNB thành amount_norm=15.22 (tương đương ~4 triệu
            # đơn vị thô — sai gần 7 lần).
            final_amount = representative.amount_norm if is_protocol_specific else total_amount / len(tx_events)
            merged.append(
                representative.model_copy(
                    update={"event_type": final_type, "amount_norm": final_amount}
                )
            )
        elif len(srcs) == 1 and len(dsts) >= 2:
            # 1 nguồn, nhiều đích trong cùng tx -> split (giữ từng nhánh riêng,
            # chỉ gắn nhãn event_type='split' cho từng event thay vì gộp giá trị)
            for e in tx_events:
                merged.append(e.model_copy(update={"event_type": "split"}))
        elif len(dsts) == 1 and len(srcs) >= 2:
            # nhiều nguồn hội tụ 1 đích trong cùng tx -> merge
            for e in tx_events:
                merged.append(e.model_copy(update={"event_type": "merge"}))
        else:
            merged.extend(tx_events)

    merged.sort(key=lambda e: (e.timestamp, e.block_number, e.tx_hash, e.log_index))
    return merged
