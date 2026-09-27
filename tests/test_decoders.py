"""
Unit tests cho decoder (Bước 3), dùng 10 transaction cố định làm fixture
(tests/fixtures/sample_logs.py), assert decode ra đúng event_type và
amount_norm. Đồng thời test cơ chế chặn cứng khi protocol_map.yaml entry
chưa verify (KHÔNG được dùng address CHƯA_VERIFY để decode bridge event).
"""
import math
from datetime import datetime, timezone

import pytest

from src.normalize.schema import CanonicalEvent
from src.normalize.decoder import (
    ProtocolMapNotVerifiedError,
    build_verified_bridge_address_index,
    build_verified_mixer_address_index,
    decode_bridge_event,
    decode_bsctrace_transfer_row,
    decode_erc20_transfer_log,
    decode_internal_tx_row,
    decode_normal_tx_row,
    decode_tokentx_row,
    list_unverified_entries,
    load_protocol_map,
    merge_events_into_semantic_actions,
    require_verified_entry,
)
from tests.fixtures.sample_logs import (
    ALL_FIXTURE_TXS,
    CHAIN_ID,
    TX1_TRANSFER,
    TX2_TRANSFER,
    TX3_TRANSFER,
    TX4_SWAP,
    TX5_SWAP,
    TX6_SPLIT,
    TX7_SPLIT,
    TX8_MERGE,
    TX9_BRIDGE_DEPOSIT,
    TX10_BRIDGE_WITHDRAW,
)

VERIFIED_TEST_ENTRY = {"name": "TestBridge_Verified", "verify_status": "verified"}
UNVERIFIED_TEST_ENTRY = {"name": "TestBridge_Unverified", "verify_status": "CHƯA_VERIFY — cần kiểm tra"}


def test_fixture_has_exactly_10_transactions():
    assert len(ALL_FIXTURE_TXS) == 10


@pytest.mark.parametrize(
    "logs,expected_amount_norm",
    [
        (TX1_TRANSFER, math.log1p(1.0)),
        (TX2_TRANSFER, math.log1p(0.5)),
        (TX3_TRANSFER, math.log1p(2.0)),
    ],
)
def test_decode_plain_transfer(logs, expected_amount_norm):
    ev = decode_erc20_transfer_log(logs[0], chain_id=CHAIN_ID)
    assert ev.event_type == "transfer"
    assert ev.amount_norm == pytest.approx(expected_amount_norm, rel=1e-6)
    assert ev.chain_id == CHAIN_ID
    assert ev.src.startswith("0x") and len(ev.src) == 42
    assert ev.dst.startswith("0x") and len(ev.dst) == 42


def test_decode_transfer_src_dst_parsed_from_topics():
    ev = decode_erc20_transfer_log(TX1_TRANSFER[0], chain_id=CHAIN_ID)
    assert ev.src == "0x" + "1".zfill(40)
    assert ev.dst == "0x" + "2".zfill(40)


def test_reject_non_transfer_topic0():
    bad_log = dict(TX1_TRANSFER[0])
    bad_log["topics"] = ["0x" + "0" * 64] + bad_log["topics"][1:]
    with pytest.raises(ValueError):
        decode_erc20_transfer_log(bad_log, chain_id=CHAIN_ID)


def _decode_all(logs):
    return [decode_erc20_transfer_log(l, chain_id=CHAIN_ID) for l in logs]


def test_merge_events_classifies_swap_tx4_and_tx5():
    events = _decode_all(TX4_SWAP) + _decode_all(TX5_SWAP)
    merged = merge_events_into_semantic_actions(events)

    tx4_hash = TX4_SWAP[0]["transactionHash"]
    tx5_hash = TX5_SWAP[0]["transactionHash"]
    tx4_result = [e for e in merged if e.tx_hash == tx4_hash]
    tx5_result = [e for e in merged if e.tx_hash == tx5_hash]

    assert len(tx4_result) == 1
    assert tx4_result[0].event_type == "swap"
    assert len(tx5_result) == 1
    assert tx5_result[0].event_type == "swap"


def test_merge_events_classifies_split_tx6_and_tx7():
    events = _decode_all(TX6_SPLIT) + _decode_all(TX7_SPLIT)
    merged = merge_events_into_semantic_actions(events)

    tx6_hash = TX6_SPLIT[0]["transactionHash"]
    tx6_result = [e for e in merged if e.tx_hash == tx6_hash]
    assert len(tx6_result) == 2
    assert all(e.event_type == "split" for e in tx6_result)
    assert len({e.dst for e in tx6_result}) == 2  # 2 nhánh split, 2 dst khác nhau


def test_merge_events_classifies_merge_tx8():
    events = _decode_all(TX8_MERGE)
    merged = merge_events_into_semantic_actions(events)
    assert len(merged) == 2
    assert all(e.event_type == "merge" for e in merged)
    assert len({e.src for e in merged}) == 2
    assert len({e.dst for e in merged}) == 1


def test_merge_events_keeps_single_event_tx_unchanged():
    events = _decode_all(TX1_TRANSFER)
    merged = merge_events_into_semantic_actions(events)
    assert len(merged) == 1
    assert merged[0].event_type == "transfer"


def test_merge_events_swap_representative_uses_outbound_leg_not_log_index_order():
    """Regression test cho bug thật phát hiện 2026-08-13: representative của
    swap PHẢI là leg xuất phát từ địa chỉ tự tham chiếu (trader chi ra rồi
    nhận lại trong cùng tx), KHÔNG được phụ thuộc thứ tự log_index — vì
    log_index của leg native (external/internal) chỉ là placeholder giả
    (offset cố định), không phản ánh thứ tự ngữ nghĩa thật của swap. Trước
    khi sửa, nếu leg outbound có log_index LỚN hơn leg inbound (đúng trường
    hợp BSCTrace sau khi sửa offset +600000), representative bị đảo thành
    leg inbound (src=pool, KHÔNG phải trader) -> build_trajectory loại bỏ
    action vì src không nằm trong node_depth (mất action thật, xem
    metadata/annotation_guide.md mục 9)."""
    trader = "0x" + "a" * 40
    router = "0x" + "b" * 40
    pool = "0x" + "c" * 40
    ts = datetime(2022, 1, 1, tzinfo=timezone.utc)

    # leg outbound (trader chi BNB) - log_index CỐ Ý lớn hơn leg inbound,
    # mô phỏng đúng tình huống offset native BSC sau khi sửa bug traceIndex.
    leg_out = CanonicalEvent(
        chain_id=CHAIN_ID, block_number=1, timestamp=ts, tx_hash="0x" + "1" * 64,
        log_index=600_000, src=trader, dst=router, event_type="transfer",
        amount_norm=1.0, token="BNB",
    )
    # leg inbound (pool trả USDT về trader) - log_index thật, nhỏ hơn nhiều.
    leg_in = CanonicalEvent(
        chain_id=CHAIN_ID, block_number=1, timestamp=ts, tx_hash="0x" + "1" * 64,
        log_index=105, src=pool, dst=trader, event_type="transfer",
        amount_norm=2.0, token="USDT",
    )

    merged = merge_events_into_semantic_actions([leg_in, leg_out])  # thứ tự input không quan trọng
    assert len(merged) == 1
    assert merged[0].event_type == "swap"
    assert merged[0].src == trader, (
        "representative phải là leg XUẤT PHÁT từ trader (outbound), không phải leg inbound từ pool, "
        "bất kể log_index leg nào lớn hơn"
    )
    assert merged[0].dst == router


def test_merge_events_ambiguous_two_party_roundtrip_prefers_native_outbound_leg():
    """Regression test cho bug thật phát hiện 2026-08-13 khi thêm Venus
    Protocol: tx có ĐÚNG 2 leg giữa 2 địa chỉ (A->B native, B->A ERC-20) —
    CẢ 2 địa chỉ đều "tự tham chiếu" (self_addresses={A,B}), không rõ leg nào
    là outbound thật nếu chỉ dựa self-referencing. Phải ưu tiên leg NATIVE
    (token='BNB'/'ETH') làm representative vì bên gửi native luôn là actor
    thật chi tiền (khác leg ERC-20 'phản hồi' như mint receipt token) — bất
    kể log_index thế nào."""
    ts = datetime(2022, 1, 1, tzinfo=timezone.utc)
    tx_hash = "0x" + "4" * 64
    seed = "0x" + "d" * 40
    lending_contract = "0x" + "e" * 40

    leg_native_out = CanonicalEvent(
        chain_id=CHAIN_ID, block_number=1, timestamp=ts, tx_hash=tx_hash,
        log_index=600_000, src=seed, dst=lending_contract, event_type="lending_deposit",
        amount_norm=math.log1p(900_000), token="BNB", protocol="Venus Protocol",
    )
    leg_receipt_in = CanonicalEvent(
        chain_id=CHAIN_ID, block_number=1, timestamp=ts, tx_hash=tx_hash,
        log_index=105, src=lending_contract, dst=seed, event_type="transfer",
        amount_norm=math.log1p(900_000), token="vBNB",
    )

    merged = merge_events_into_semantic_actions([leg_receipt_in, leg_native_out])
    assert len(merged) == 1
    assert merged[0].src == seed, "phải ưu tiên leg native (seed chi BNB), không phải leg ERC-20 phản hồi"
    assert merged[0].dst == lending_contract
    # event_type protocol-specific (lending_deposit) đã gắn nhãn đúng qua
    # protocol_map.yaml KHÔNG được ghi đè thành 'swap' chung chung.
    assert merged[0].event_type == "lending_deposit"
    assert merged[0].protocol == "Venus Protocol"
    # amount_norm PHẢI là giá trị leg native gốc (không trung bình với leg
    # receipt vBNB — decimals/tỷ giá khác hẳn, trung bình sẽ sai lệch giá trị
    # deposit thật, xem comment trong merge_events_into_semantic_actions).
    assert merged[0].amount_norm == pytest.approx(leg_native_out.amount_norm, rel=1e-9)


def test_decode_bridge_event_succeeds_with_verified_entry():
    ev = decode_bridge_event(
        TX9_BRIDGE_DEPOSIT[0],
        chain_id=CHAIN_ID,
        protocol_entry=VERIFIED_TEST_ENTRY,
        direction="deposit",
    )
    assert ev.event_type == "bridge_deposit"
    assert ev.protocol == "TestBridge_Verified"


def test_decode_bridge_event_blocked_when_entry_unverified():
    with pytest.raises(ProtocolMapNotVerifiedError):
        decode_bridge_event(
            TX10_BRIDGE_WITHDRAW[0],
            chain_id=CHAIN_ID,
            protocol_entry=UNVERIFIED_TEST_ENTRY,
            direction="withdraw",
        )


def test_require_verified_entry_passes_for_verified():
    require_verified_entry(VERIFIED_TEST_ENTRY)  # không raise


def test_require_verified_entry_raises_for_unverified():
    with pytest.raises(ProtocolMapNotVerifiedError):
        require_verified_entry(UNVERIFIED_TEST_ENTRY)


SAMPLE_TOKENTX_ROW = {
    "hash": "0x" + "9" * 64,
    "from": "0x" + "1" * 40,
    "to": "0x" + "2" * 40,
    "value": str(25_500_000 * 10 ** 6),
    "tokenDecimal": "6",
    "tokenSymbol": "USDC",
    "blockNumber": "14442840",
    "timeStamp": "1648042264",
    "logIndex": "3",
}

SAMPLE_NORMAL_TX_ROW = {
    "hash": "0x" + "8" * 64,
    "from": "0x" + "3" * 40,
    "to": "0x" + "4" * 40,
    "value": str(173_600 * 10 ** 18),
    "blockNumber": "14442776",
    "timeStamp": "1648041600",
}

SAMPLE_ZERO_VALUE_TX_ROW = dict(SAMPLE_NORMAL_TX_ROW, value="0")


def test_decode_tokentx_row_plain_transfer_no_bridge_index():
    ev = decode_tokentx_row(SAMPLE_TOKENTX_ROW, chain_id=CHAIN_ID)
    assert ev.event_type == "transfer"
    assert ev.token == "USDC"
    assert ev.amount_norm == pytest.approx(math.log1p(25_500_000), rel=1e-6)


def test_decode_tokentx_row_classifies_bridge_withdraw_when_src_is_verified_bridge():
    bridge_entry = {"name": "TestBridge", "verify_status": "verified"}
    index = {SAMPLE_TOKENTX_ROW["from"].lower(): bridge_entry}
    ev = decode_tokentx_row(SAMPLE_TOKENTX_ROW, chain_id=CHAIN_ID, bridge_address_index=index)
    assert ev.event_type == "bridge_withdraw"
    assert ev.protocol == "TestBridge"


def test_decode_tokentx_row_classifies_bridge_deposit_when_dst_is_verified_bridge():
    bridge_entry = {"name": "TestBridge", "verify_status": "verified"}
    index = {SAMPLE_TOKENTX_ROW["to"].lower(): bridge_entry}
    ev = decode_tokentx_row(SAMPLE_TOKENTX_ROW, chain_id=CHAIN_ID, bridge_address_index=index)
    assert ev.event_type == "bridge_deposit"
    assert ev.protocol == "TestBridge"


def test_decode_tokentx_row_null_log_index_uses_stable_content_hash_not_zero():
    """Regression test cho bug thật phát hiện 2026-08-13: Etherscan API V2
    `tokentx` KHÔNG trả logIndex thật cho BẤT KỲ dòng nào (xác nhận: 100%
    dòng tokentx đã cache, cả eth lẫn arbitrum, logIndex=null) — dùng
    `int(row.get("logIndex", 0) or 0)` như cũ khiến MỌI event tokentx có
    log_index=0 cố định, cùng họ bug với BSCTrace logIndex=0 cho native
    transfer. Fix: hash nội dung leg (from/to/value/contractAddress) làm
    log_index giả ỔN ĐỊNH — cùng 1 leg thật decode nhiều lần (vd 2 địa chỉ
    cùng tham gia 1 tx đều nằm trong danh sách đang trace) phải ra CÙNG
    log_index (để dedup đúng); 2 leg THẬT khác nhau trong cùng tx phải ra
    log_index KHÁC NHAU (để không bị gộp nhầm)."""
    row_no_log_index = dict(SAMPLE_TOKENTX_ROW, logIndex=None)
    ev = decode_tokentx_row(row_no_log_index, chain_id=CHAIN_ID)
    assert ev.log_index != 0
    assert ev.log_index >= 800_000

    # cùng 1 leg (from/to/value/contractAddress giống hệt) decode LẦN THỨ 2
    # (mô phỏng bị fetch độc lập từ cache của 2 địa chỉ khác nhau) -> log_index
    # giả PHẢI giống hệt lần đầu, để merge_events_into_semantic_actions dedup
    # đúng thành 1 bản ghi thay vì tính trùng.
    ev_refetched = decode_tokentx_row(dict(row_no_log_index), chain_id=CHAIN_ID)
    assert ev_refetched.log_index == ev.log_index

    # leg KHÁC (from/to/value khác) cùng tx_hash -> log_index giả PHẢI khác,
    # không được gộp nhầm thành 1 leg.
    other_leg_row = dict(
        row_no_log_index, hash=row_no_log_index["hash"],
        **{"from": row_no_log_index["to"], "to": row_no_log_index["from"], "value": "111"},
    )
    ev_other = decode_tokentx_row(other_leg_row, chain_id=CHAIN_ID)
    assert ev_other.log_index != ev.log_index


def test_merge_events_into_semantic_actions_dedups_leg_fetched_from_both_addresses():
    """Regression test: khi 1 tx có 2 leg thật (vd swap USDC->WBTC), và CẢ
    2 địa chỉ tham gia đều nằm trong danh sách đang trace, mỗi leg bị decode
    2 LẦN ĐỘC LẬP (1 lần từ cache mỗi địa chỉ) trước khi tới
    merge_events_into_semantic_actions — nếu không dedup trước khi gộp theo
    tx_hash, total_amount/len(tx_events) ở nhánh 'swap' tính SAI (chia cho 4
    thay vì 2). Bug thật phát hiện 2026-08-13 khi verify bsc_token_hub_2022
    (value_share dao động giữa các lần build_trajectory tùy frontier đã mở
    rộng tới đâu)."""
    ts = datetime(2022, 1, 1, tzinfo=timezone.utc)
    tx_hash = "0x" + "2" * 64
    addr_a = "0x" + "a" * 40
    addr_b = "0x" + "b" * 40

    leg1 = CanonicalEvent(
        chain_id=CHAIN_ID, block_number=1, timestamp=ts, tx_hash=tx_hash,
        log_index=10, src=addr_a, dst=addr_b, event_type="transfer",
        amount_norm=math.log1p(100), token="USDC",
    )
    leg2 = CanonicalEvent(
        chain_id=CHAIN_ID, block_number=1, timestamp=ts, tx_hash=tx_hash,
        log_index=20, src=addr_b, dst=addr_a, event_type="transfer",
        amount_norm=math.log1p(50), token="WBTC",
    )
    # mô phỏng: cả leg1 và leg2 bị decode ĐỘC LẬP từ cache của addr_a lẫn
    # addr_b (mỗi leg xuất hiện 2 lần, giống hệt nhau) trước khi vào merge.
    duplicated_pool = [leg1, leg1.model_copy(), leg2, leg2.model_copy()]

    merged = merge_events_into_semantic_actions(duplicated_pool)
    assert len(merged) == 1
    assert merged[0].event_type == "swap"
    # amount_norm đúng = trung bình 2 leg THẬT (không phải 4 bản trùng)
    expected = (leg1.amount_norm + leg2.amount_norm) / 2
    assert merged[0].amount_norm == pytest.approx(expected, rel=1e-9)


def test_decode_normal_tx_row_native_eth_transfer():
    ev = decode_normal_tx_row(SAMPLE_NORMAL_TX_ROW, chain_id=CHAIN_ID)
    assert ev is not None
    assert ev.event_type == "transfer"
    assert ev.token == "ETH"
    assert ev.amount_norm == pytest.approx(math.log1p(173_600), rel=1e-6)


def test_decode_normal_tx_row_skips_zero_value_contract_calls():
    ev = decode_normal_tx_row(SAMPLE_ZERO_VALUE_TX_ROW, chain_id=CHAIN_ID)
    assert ev is None


SAMPLE_INTERNAL_TX_ROW = {
    "hash": "0x" + "7" * 64,
    "from": "0x" + "5" * 40,
    "to": "0x" + "6" * 40,
    "value": str(300 * 10 ** 18),
    "blockNumber": "14442960",
    "timeStamp": "1648043880",
    "traceId": "2_2",
    "isError": "0",
}


def test_decode_internal_tx_row_native_eth():
    ev = decode_internal_tx_row(SAMPLE_INTERNAL_TX_ROW, chain_id=CHAIN_ID, sequence=0)
    assert ev is not None
    assert ev.event_type == "transfer"
    assert ev.token == "ETH"
    assert ev.amount_norm == pytest.approx(math.log1p(300), rel=1e-6)
    assert ev.log_index == 900_000


def test_decode_internal_tx_row_skips_reverted():
    row = dict(SAMPLE_INTERNAL_TX_ROW, isError="1")
    assert decode_internal_tx_row(row, chain_id=CHAIN_ID, sequence=0) is None


def test_decode_internal_tx_row_skips_zero_value():
    row = dict(SAMPLE_INTERNAL_TX_ROW, value="0")
    assert decode_internal_tx_row(row, chain_id=CHAIN_ID, sequence=0) is None


def test_decode_internal_tx_row_sequence_avoids_log_index_collision():
    ev0 = decode_internal_tx_row(SAMPLE_INTERNAL_TX_ROW, chain_id=CHAIN_ID, sequence=0)
    ev1 = decode_internal_tx_row(dict(SAMPLE_INTERNAL_TX_ROW, hash=SAMPLE_INTERNAL_TX_ROW["hash"]), chain_id=CHAIN_ID, sequence=1)
    assert ev0.log_index != ev1.log_index


def test_internal_tx_and_tokentx_same_tx_hash_merge_into_swap():
    """Trường hợp thật: chân 'token ra' (tokentx) + chân 'ETH vào' (internal
    tx) cùng tx_hash -> phải được merge thành 1 action event_type='swap'.

    Round-trip THẬT: user (SAMPLE_TOKENTX_ROW['from']) chi token ra (tokentx),
    router (SAMPLE_TOKENTX_ROW['to']) trả ETH lại CHO CHÍNH user đó (internal
    tx) — địa chỉ user PHẢI xuất hiện vừa là src (leg tokentx) vừa là dst
    (leg internal) để thỏa điều kiện self-referencing bắt buộc cho 'swap'
    (xem merge_events_into_semantic_actions, bug thật phát hiện 2026-08-13:
    2 leg tới TỪ 2 nguồn hoàn toàn không liên quan, hội tụ vào 1 địa chỉ,
    không phải la round-trip thật -> phải là 'merge', không phải 'swap')."""
    tokentx_row = dict(SAMPLE_TOKENTX_ROW, hash="0x" + "f" * 64)
    internal_row = dict(
        SAMPLE_INTERNAL_TX_ROW, hash="0x" + "f" * 64,
        **{"from": SAMPLE_TOKENTX_ROW["to"], "to": SAMPLE_TOKENTX_ROW["from"]},
    )

    ev_out = decode_tokentx_row(tokentx_row, chain_id=CHAIN_ID)
    ev_in = decode_internal_tx_row(internal_row, chain_id=CHAIN_ID, sequence=0)

    merged = merge_events_into_semantic_actions([ev_out, ev_in])
    assert len(merged) == 1
    assert merged[0].event_type == "swap"


def test_merge_events_two_different_senders_two_different_tokens_one_dst_is_merge_not_swap():
    """Regression test cho bug thật phát hiện 2026-08-13 khi verify
    bsc_token_hub_2022: 2 địa chỉ HOÀN TOÀN KHÔNG LIÊN QUAN (không ai vừa
    gửi vừa nhận) cùng gửi 2 TOKEN KHÁC NHAU hội tụ vào 1 địa chỉ đích trong
    CÙNG 1 tx — đây là 'merge' theo đúng định nghĩa (dsts==1, srcs>=2), dù
    tokens>=2 và srcs<=2/dsts<=2 cũng đúng (dễ lọt nhầm vào nhánh 'swap' cũ).
    KHÔNG được gộp giá trị trung bình 2 token không liên quan thành 1 action
    'swap' giả — phải giữ riêng từng leg với event_type='merge'."""
    ts = datetime(2022, 1, 1, tzinfo=timezone.utc)
    tx_hash = "0x" + "3" * 64
    sender_a = "0x" + "a" * 40  # vd: seed
    sender_b = "0x" + "b" * 40  # vd: DEX router — KHÔNG liên quan gì tới sender_a
    dst = "0x" + "c" * 40  # địa chỉ trung gian nhận cả 2

    leg_a = CanonicalEvent(
        chain_id=CHAIN_ID, block_number=1, timestamp=ts, tx_hash=tx_hash,
        log_index=18, src=sender_a, dst=dst, event_type="transfer",
        amount_norm=math.log1p(100), token="TOKEN_A",
    )
    leg_b = CanonicalEvent(
        chain_id=CHAIN_ID, block_number=1, timestamp=ts, tx_hash=tx_hash,
        log_index=21, src=sender_b, dst=dst, event_type="transfer",
        amount_norm=math.log1p(50), token="TOKEN_B",
    )

    merged = merge_events_into_semantic_actions([leg_a, leg_b])
    assert len(merged) == 2, "phải giữ riêng 2 leg (merge), không gộp thành 1 'swap' trung bình"
    assert all(e.event_type == "merge" for e in merged)
    # amount_norm PHẢI giữ nguyên giá trị gốc từng leg, không bị chia trung bình
    amounts = {round(e.amount_norm, 6) for e in merged}
    assert amounts == {round(leg_a.amount_norm, 6), round(leg_b.amount_norm, 6)}


def test_decode_normal_tx_row_classifies_mixer_when_dst_is_verified_mixer():
    mixer_entry = {"name": "TestMixer", "verify_status": "verified"}
    index = {SAMPLE_NORMAL_TX_ROW["to"].lower(): mixer_entry}
    ev = decode_normal_tx_row(SAMPLE_NORMAL_TX_ROW, chain_id=CHAIN_ID, mixer_address_index=index)
    assert ev.event_type == "mixer_or_exit"
    assert ev.protocol == "TestMixer"


def test_decode_normal_tx_row_stays_transfer_when_dst_not_mixer():
    ev = decode_normal_tx_row(SAMPLE_NORMAL_TX_ROW, chain_id=CHAIN_ID, mixer_address_index={})
    assert ev.event_type == "transfer"


def test_build_verified_mixer_address_index_excludes_unverified():
    protocol_map = {
        "mixers_exit_services": [
            {"name": "Verified", "verify_status": "verified", "contract_addresses": {"eth": "0xCCC"}},
            {"name": "Unverified", "verify_status": "CHƯA_VERIFY", "contract_addresses": {"eth": "0xDDD"}},
        ]
    }
    index = build_verified_mixer_address_index(protocol_map)
    assert "0xccc" in index
    assert "0xddd" not in index


def test_real_protocol_map_has_verified_tornado_cash_router():
    protocol_map = load_protocol_map()
    index = build_verified_mixer_address_index(protocol_map)
    assert "0xd90e2f925da726b50c4ed8d0fb90ad053324f31b" in index


# Schema THẬT xác nhận qua smoke_test() với key thật ngày 2026-08-13 (địa chỉ
# QBridge exploiter 0xd01ae1a708614948b2b5e0b7ab5be6afa01325c7) — value là hex
# RAW base-unit, blockTimeStamp unix int ở top-level, logIndex có sẵn.
SAMPLE_BSCTRACE_NATIVE_ROW = {
    "id": 1,
    "category": "external",
    "blockNum": "0x100",
    "from": "0x" + "1" * 40,
    "to": "0x" + "2" * 40,
    "value": "0x14d1120d7b160000",  # 1.5 * 10**18 wei
    "asset": "BNB",
    "hash": "0x" + "b" * 64,
    "contractAddress": "0x" + "0" * 40,
    "blockTimeStamp": 1643320487,
    "logIndex": 0,
    "traceIndex": 0,
}

SAMPLE_BSCTRACE_ERC20_ROW = {
    "id": 2,
    "category": "20",
    "blockNum": "0x100",
    "from": "0x" + "1" * 40,
    "to": "0x" + "2" * 40,
    "value": "0xde0b6b3a7640000",  # 1 * 10**18 base unit
    "asset": "USDC",
    "hash": "0x" + "c" * 64,
    "contractAddress": "0x" + "3" * 40,
    "decimal": "18",
    "blockTimeStamp": 1643320487,
    "logIndex": 42,
}


def test_decode_bsctrace_transfer_row_native():
    ev = decode_bsctrace_transfer_row(SAMPLE_BSCTRACE_NATIVE_ROW, chain_id=56)
    assert ev is not None
    assert ev.event_type == "transfer"
    assert ev.token == "BNB"
    assert ev.amount_norm == pytest.approx(math.log1p(1.5), rel=1e-6)
    assert ev.block_number == 256  # 0x100
    # category="external" -> dùng traceIndex (không phải logIndex, luôn=0
    # cho native transfer) + offset để tránh đụng logIndex thật của ERC-20
    assert ev.log_index == 600_000 + 0  # offset "external" + traceIndex=0


def test_decode_bsctrace_transfer_row_skips_zero_value():
    row = dict(SAMPLE_BSCTRACE_NATIVE_ROW, value="0x0")
    assert decode_bsctrace_transfer_row(row, chain_id=56) is None


def test_decode_bsctrace_transfer_row_uses_real_log_index():
    ev = decode_bsctrace_transfer_row(SAMPLE_BSCTRACE_ERC20_ROW, chain_id=56)
    assert ev.log_index == 42  # field thật, không phải offset giả


def test_decode_bsctrace_transfer_row_erc20_decimals_and_bridge_classification():
    bridge_entry = {"name": "TestBSCBridge", "verify_status": "verified"}
    index = {SAMPLE_BSCTRACE_ERC20_ROW["from"].lower(): bridge_entry}
    ev = decode_bsctrace_transfer_row(SAMPLE_BSCTRACE_ERC20_ROW, chain_id=56, bridge_address_index=index)
    assert ev.amount_norm == pytest.approx(math.log1p(1.0), rel=1e-6)  # 1e18 / 10**18 = 1.0
    assert ev.event_type == "bridge_withdraw"
    assert ev.protocol == "TestBSCBridge"
    assert ev.token == "USDC"


def test_decode_bsctrace_transfer_row_native_bridge_classification():
    """Bridge có thể chuyển native token (BNB) — bug thật BSC Token Hub
    2026-08-13: classification trước đây chỉ áp dụng cho category='20'."""
    bridge_entry = {"name": "TestBSCBridge", "verify_status": "verified"}
    index = {SAMPLE_BSCTRACE_NATIVE_ROW["from"].lower(): bridge_entry}
    ev = decode_bsctrace_transfer_row(SAMPLE_BSCTRACE_NATIVE_ROW, chain_id=56, bridge_address_index=index)
    assert ev.event_type == "bridge_withdraw"
    assert ev.protocol == "TestBSCBridge"


def test_decode_bsctrace_transfer_row_native_legs_use_trace_index_not_log_index():
    """Bug thật (hard-negative mining 2026-08-13): category='external'/
    'internal' luôn có logIndex=0 (không phải EVM log thật) — 2 leg khác
    nhau cùng tx_hash (vd 'seed->router' và 'router->seed' của 1 swap) đều
    logIndex=0, bị CanonicalEvent._dedup() coi là trùng nếu dùng logIndex
    làm log_index. Phải dùng traceIndex (field thật phân biệt từng leg).
    """
    leg1 = dict(SAMPLE_BSCTRACE_NATIVE_ROW, category="external", logIndex=0, traceIndex=0)
    leg2 = dict(SAMPLE_BSCTRACE_NATIVE_ROW, category="internal", logIndex=0, traceIndex=12,
                hash=SAMPLE_BSCTRACE_NATIVE_ROW["hash"])  # cùng tx_hash

    ev1 = decode_bsctrace_transfer_row(leg1, chain_id=56)
    ev2 = decode_bsctrace_transfer_row(leg2, chain_id=56)

    assert ev1.log_index != ev2.log_index
    assert ev1.dedup_key() != ev2.dedup_key()


def test_decode_bsctrace_transfer_row_erc20_still_uses_real_log_index():
    """category='20' có logIndex thật (real EVM log) — KHÔNG chuyển sang
    dùng traceIndex, giữ nguyên hành vi cũ."""
    row = dict(SAMPLE_BSCTRACE_ERC20_ROW, logIndex=42, traceIndex=0)
    ev = decode_bsctrace_transfer_row(row, chain_id=56)
    assert ev.log_index == 42


def test_decode_bsctrace_transfer_row_missing_timestamp_raises():
    row = dict(SAMPLE_BSCTRACE_NATIVE_ROW)
    del row["blockTimeStamp"]
    with pytest.raises(ValueError):
        decode_bsctrace_transfer_row(row, chain_id=56)


def test_build_verified_bridge_address_index_excludes_unverified():
    protocol_map = {
        "bridges": [
            {"name": "Verified", "verify_status": "verified", "contract_addresses": {"eth": "0xAAA"}},
            {"name": "Unverified", "verify_status": "CHƯA_VERIFY", "contract_addresses": {"eth": "0xBBB"}},
        ]
    }
    index = build_verified_bridge_address_index(protocol_map)
    assert "0xaaa" in index
    assert "0xbbb" not in index


def test_real_protocol_map_yaml_entries_are_now_verified():
    """Người dùng đã tự đối chiếu 5 address (Ronin, Wormhole, Stargate,
    Uniswap V2, PancakeSwap V2) với block explorer thật và cập nhật
    verify_status="verified_2026-08-13" (2026-08-13). Test này xác nhận
    require_verified_entry() không còn chặn các entry đó — nếu ai thêm entry
    mới mà quên set verify_status, test sẽ fail và nhắc lại yêu cầu verify.
    """
    protocol_map = load_protocol_map()
    unverified = list_unverified_entries(protocol_map)
    assert unverified == [], (
        f"Entry sau đây vẫn CHƯA_VERIFY, cần đối chiếu on-chain trước khi dùng "
        f"để crawl/decode bridge thật: {unverified}"
    )
    for category in ("bridges", "dexes"):
        for entry in protocol_map.get(category, []) or []:
            require_verified_entry(entry)  # không raise
