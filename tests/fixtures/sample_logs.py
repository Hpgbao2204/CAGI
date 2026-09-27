"""
10 transaction fixture cố định cho tests/test_decoders.py (Bước 3), mô
phỏng cấu trúc log thật của Etherscan-family `eth_getLogs` (topics/data hex)
— KHÔNG dùng bất kỳ address nào từ metadata/protocol_map.yaml (các address
đó vẫn CHƯA_VERIFY, xem src/normalize/decoder.py).
"""
from __future__ import annotations

from src.normalize.decoder import ERC20_TRANSFER_TOPIC0

CHAIN_ID = 1


def _addr(n: int) -> str:
    return "0x" + format(n, "040x")


def _topic_addr(n: int) -> str:
    return "0x" + format(n, "064x")


def _hex_value(v: int) -> str:
    return hex(v)


def _log(
    tx_idx: int,
    log_index: int,
    src_n: int,
    dst_n: int,
    raw_value: int,
    token_addr_n: int,
    block: int = 18_000_000,
    ts: int = 1_700_000_000,
):
    return {
        "address": _addr(token_addr_n),
        "topics": [ERC20_TRANSFER_TOPIC0, _topic_addr(src_n), _topic_addr(dst_n)],
        "data": _hex_value(raw_value),
        "blockNumber": str(block + tx_idx),
        "timeStamp": str(ts + tx_idx * 60),
        "transactionHash": "0x" + format(tx_idx, "064x"),
        "logIndex": str(log_index),
        "token_symbol": f"TOK{token_addr_n}",
    }


# tx 1-3: pure single-event transfer
TX1_TRANSFER = [_log(1, 0, src_n=1, dst_n=2, raw_value=10 ** 18, token_addr_n=100)]
TX2_TRANSFER = [_log(2, 0, src_n=2, dst_n=3, raw_value=5 * 10 ** 17, token_addr_n=100)]
TX3_TRANSFER = [_log(3, 0, src_n=3, dst_n=4, raw_value=2 * 10 ** 18, token_addr_n=100)]

# tx 4-5: swap (2 events, 2 different tokens, same counterparties -> in/out through a router)
TX4_SWAP = [
    _log(4, 0, src_n=5, dst_n=50, raw_value=3 * 10 ** 18, token_addr_n=100),  # user -> router (token A)
    _log(4, 1, src_n=50, dst_n=5, raw_value=2_900 * 10 ** 18, token_addr_n=200),  # router -> user (token B)
]
TX5_SWAP = [
    _log(5, 0, src_n=6, dst_n=50, raw_value=1 * 10 ** 18, token_addr_n=100),
    _log(5, 1, src_n=50, dst_n=6, raw_value=980 * 10 ** 18, token_addr_n=200),
]

# tx 6-7: split (1 src, 2 different dst, same token, same tx)
TX6_SPLIT = [
    _log(6, 0, src_n=7, dst_n=8, raw_value=1 * 10 ** 18, token_addr_n=100),
    _log(6, 1, src_n=7, dst_n=9, raw_value=1 * 10 ** 18, token_addr_n=100),
]
TX7_SPLIT = [
    _log(7, 0, src_n=10, dst_n=11, raw_value=2 * 10 ** 18, token_addr_n=100),
    _log(7, 1, src_n=10, dst_n=12, raw_value=3 * 10 ** 18, token_addr_n=100),
]

# tx 8: merge (2 src converge into 1 dst, same tx)
TX8_MERGE = [
    _log(8, 0, src_n=13, dst_n=14, raw_value=1 * 10 ** 18, token_addr_n=100),
    _log(8, 1, src_n=15, dst_n=14, raw_value=2 * 10 ** 18, token_addr_n=100),
]

# tx 9: bridge deposit candidate (decoded via decode_bridge_event with a
# LOCALLY-DEFINED verified protocol entry, không lấy từ protocol_map.yaml)
TX9_BRIDGE_DEPOSIT = [_log(9, 0, src_n=16, dst_n=999, raw_value=4 * 10 ** 18, token_addr_n=100)]

# tx 10: bridge withdraw candidate, dùng chung với entry CHƯA_VERIFY để test
# rằng decode_bridge_event PHẢI raise (không được decode).
TX10_BRIDGE_WITHDRAW = [_log(10, 0, src_n=999, dst_n=17, raw_value=39 * 10 ** 17, token_addr_n=100)]

ALL_FIXTURE_TXS = {
    "tx1_transfer": TX1_TRANSFER,
    "tx2_transfer": TX2_TRANSFER,
    "tx3_transfer": TX3_TRANSFER,
    "tx4_swap": TX4_SWAP,
    "tx5_swap": TX5_SWAP,
    "tx6_split": TX6_SPLIT,
    "tx7_split": TX7_SPLIT,
    "tx8_merge": TX8_MERGE,
    "tx9_bridge_deposit": TX9_BRIDGE_DEPOSIT,
    "tx10_bridge_withdraw": TX10_BRIDGE_WITHDRAW,
}
