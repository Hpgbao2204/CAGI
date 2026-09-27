"""
Sinh dữ liệu synthetic đúng CanonicalEvent schema để chạy end-to-end pipeline
(trajectory builder -> feature extractor -> baseline models -> evaluation)
mà không cần API key / dữ liệu on-chain thật.

Gồm:
- 3 trajectory dương tính (label=1): có pattern bridge -> swap -> split/mixer
  trong cửa sổ thời gian ngắn (điển hình laundering typology).
- 6 trajectory âm tính (label=0): benign high-activity (nhiều transfer/swap
  bình thường, không có bridge->swap->split nhanh, không chạm mixer).

Dữ liệu này KHÔNG phải dữ liệu on-chain thật, chỉ dùng để kiểm thử logic
pipeline (Bước 4-7) trước khi cắm API thật (Bước 2-3).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Tuple

from src.normalize.schema import CanonicalEvent

CHAIN_ID = 1
BASE_TIME = datetime(2024, 6, 1, tzinfo=timezone.utc)


def _addr(tag: str) -> str:
    """Tạo address hex hợp lệ (42 ký tự) ổn định từ một tag ngắn."""
    h = tag.encode("utf-8").hex()
    h = (h + "0" * 40)[:40]
    return "0x" + h


def _tx(tag: str) -> str:
    h = tag.encode("utf-8").hex()
    h = (h + "0" * 64)[:64]
    return "0x" + h


def _mk_event(
    idx: int,
    minutes_offset: int,
    src_tag: str,
    dst_tag: str,
    event_type: str,
    amount_norm: float,
    protocol: str = None,
    token: str = None,
) -> CanonicalEvent:
    return CanonicalEvent(
        chain_id=CHAIN_ID,
        block_number=18_000_000 + idx,
        timestamp=BASE_TIME + timedelta(minutes=minutes_offset),
        tx_hash=_tx(f"tx{idx}"),
        log_index=0,
        src=_addr(src_tag),
        dst=_addr(dst_tag),
        event_type=event_type,
        amount_norm=amount_norm,
        protocol=protocol,
        token=token,
    )


def make_positive_trajectory(seed_idx: int) -> Tuple[str, List[CanonicalEvent]]:
    """Bridge -> swap -> split/mixer trong cửa sổ thời gian ngắn."""
    seed = f"seed_pos_{seed_idx}"
    hop1 = f"pos_{seed_idx}_bridge_out"
    hop2 = f"pos_{seed_idx}_dex"
    hop3a = f"pos_{seed_idx}_split_a"
    hop3b = f"pos_{seed_idx}_split_b"
    mixer = f"pos_{seed_idx}_mixer"

    events = [
        _mk_event(seed_idx * 100 + 0, 0, seed, hop1, "bridge_deposit", 4.0, protocol="stargate", token="usdc"),
        _mk_event(seed_idx * 100 + 1, 5, hop1, hop1, "bridge_withdraw", 3.9, protocol="stargate", token="usdc"),
        _mk_event(seed_idx * 100 + 2, 10, hop1, hop2, "swap", 3.8, protocol="uniswap_v2", token="usdc"),
        _mk_event(seed_idx * 100 + 3, 15, hop2, hop3a, "split", 1.9, token="eth"),
        _mk_event(seed_idx * 100 + 4, 15, hop2, hop3b, "split", 1.8, token="eth"),
        _mk_event(seed_idx * 100 + 5, 25, hop3a, mixer, "mixer_or_exit", 1.85, token="eth"),
        _mk_event(seed_idx * 100 + 6, 26, hop3b, mixer, "mixer_or_exit", 1.75, token="eth"),
    ]
    return _addr(seed), events


def make_negative_trajectory(seed_idx: int) -> Tuple[str, List[CanonicalEvent]]:
    """Benign high-activity: nhiều transfer/swap bình thường, không mixer."""
    seed = f"seed_neg_{seed_idx}"
    counterparties = [f"neg_{seed_idx}_cp_{i}" for i in range(5)]

    events = []
    idx_base = 1000 + seed_idx * 100
    cur_src = seed
    for i, cp in enumerate(counterparties):
        events.append(
            _mk_event(
                idx_base + i,
                minutes_offset=i * 40,
                src_tag=cur_src,
                dst_tag=cp,
                event_type="transfer" if i % 2 == 0 else "swap",
                amount_norm=0.5 + 0.1 * i,
                protocol="uniswap_v2" if i % 2 == 1 else None,
                token="usdc",
            )
        )
        cur_src = cp
    return _addr(seed), events


def build_synthetic_dataset() -> List[dict]:
    """Trả về list dict {seed, events, incident_id, label} cho 3 positive + 6 negative."""
    dataset = []
    for i in range(1, 4):
        seed, events = make_positive_trajectory(i)
        dataset.append({"seed": seed, "events": events, "incident_id": f"incident_pos_{i}", "label": 1})
    for i in range(1, 7):
        seed, events = make_negative_trajectory(i)
        dataset.append({"seed": seed, "events": events, "incident_id": f"incident_neg_{i}", "label": 0})
    return dataset
