"""
Schema validation tests. Đối chiếu với configs/features.yaml -> event_schema.
"""
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.normalize.schema import CanonicalEvent

VALID_KWARGS = dict(
    chain_id=1,
    block_number=18_000_000,
    timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
    tx_hash="0x" + "a" * 64,
    log_index=0,
    src="0x" + "1" * 40,
    dst="0x" + "2" * 40,
    event_type="transfer",
    amount_norm=1.23,
)


def test_valid_event_constructs():
    ev = CanonicalEvent(**VALID_KWARGS)
    assert ev.event_type == "transfer"
    assert ev.dedup_key() == (1, "0x" + "a" * 64, 0)


@pytest.mark.parametrize(
    "missing_field",
    [
        "chain_id",
        "block_number",
        "timestamp",
        "tx_hash",
        "log_index",
        "src",
        "dst",
        "event_type",
        "amount_norm",
    ],
)
def test_reject_missing_required_field(missing_field):
    kwargs = dict(VALID_KWARGS)
    del kwargs[missing_field]
    with pytest.raises(ValidationError):
        CanonicalEvent(**kwargs)


def test_reject_invalid_event_type():
    kwargs = dict(VALID_KWARGS, event_type="laundering_confirmed")
    with pytest.raises(ValidationError):
        CanonicalEvent(**kwargs)


def test_reject_naive_timestamp():
    kwargs = dict(VALID_KWARGS, timestamp=datetime(2024, 1, 1))
    with pytest.raises(ValidationError):
        CanonicalEvent(**kwargs)


def test_reject_raw_amount_not_normalized():
    # raw ERC-20 amount ở base unit, vd 1000 token với 18 decimals -> 1e21
    kwargs = dict(VALID_KWARGS, amount_norm=1_000_000_000_000_000_000_000.0)
    with pytest.raises(ValidationError):
        CanonicalEvent(**kwargs)


def test_reject_malformed_tx_hash():
    kwargs = dict(VALID_KWARGS, tx_hash="not_a_hash")
    with pytest.raises(ValidationError):
        CanonicalEvent(**kwargs)


def test_reject_malformed_address():
    kwargs = dict(VALID_KWARGS, src="0xshort")
    with pytest.raises(ValidationError):
        CanonicalEvent(**kwargs)


def test_reject_unknown_extra_field():
    kwargs = dict(VALID_KWARGS, unknown_field="x")
    with pytest.raises(ValidationError):
        CanonicalEvent(**kwargs)


def test_dedup_key_is_chain_tx_log_index():
    ev1 = CanonicalEvent(**VALID_KWARGS)
    ev2 = CanonicalEvent(**dict(VALID_KWARGS, src="0x" + "3" * 40))
    # same chain_id/tx_hash/log_index -> same dedup key even if other fields differ
    assert ev1.dedup_key() == ev2.dedup_key()

    ev3 = CanonicalEvent(**dict(VALID_KWARGS, log_index=1))
    assert ev1.dedup_key() != ev3.dedup_key()


def test_dedup_across_list_of_events():
    ev1 = CanonicalEvent(**VALID_KWARGS)
    ev2 = CanonicalEvent(**VALID_KWARGS)  # duplicate
    ev3 = CanonicalEvent(**dict(VALID_KWARGS, log_index=5))

    events = [ev1, ev2, ev3]
    deduped = {e.dedup_key(): e for e in events}
    assert len(deduped) == 2
