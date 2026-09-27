"""CAGI-Synth: bo sinh trajectory TONG HOP (khong phai du lieu that) de kiem
tra do ben cua detector o do kho co the dieu chinh.

Moi "incident tong hop" gom 1 trajectory rua tien (label=1) va N trajectory
binh thuong (label=0) cung chain/khung thoi gian. Cau truc duoc lay mau tu
cac typology cong khai (MITRE AADAPT: peel chain, siphon/split, layering
qua DEX, cross-chain hopping, anonymizing service) va cac kieu hanh vi binh
thuong (nguoi dung bridge, trader DEX, chi tra/airdrop, gom quy, arbitrage
bot, nguoi dung mixer).

Nut do kho `difficulty` d in [0, 1]:
  * negative: voi xac suat d, trajectory binh thuong duoc lay tu cac kieu
    "giong rua tien" (bridge->swap->split nhanh, gom -> bridge) thay vi kieu
    thong thuong;
  * positive: voi xac suat d moi buoc, ke tan cong chen transfer "moi nhu"
    gia tri nho va gian nhip thoi gian (tang khoang cach, giam burstiness).
Du lieu nay CHI dung cho benchmark tong hop, bao cao TACH RIENG khoi ket qua
tren du lieu that.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from src.normalize.schema import CanonicalEvent
from src.trajectories.builder import Trajectory

CHAINS = {"eth": 1, "bsc": 56, "arbitrum": 42161}
BRIDGES = ["Stargate (LayerZero)", "Across Protocol SpokePool", "LI.FI Diamond", "Multichain (AnySwap)",
           "BSC Token Hub", "Wormhole Token Bridge (Portal)"]
DEXES = ["Uniswap V3 SwapRouter", "PancakeSwap V2", "1inch v4 AggregationRouter"]
NATIVE = {"eth": "ETH", "bsc": "BNB", "arbitrum": "ETH"}
STABLES = ["USDC", "USDT", "DAI", "BUSD"]
VOLATILE = ["WETH", "WBTC", "LINK", "UNI", "ARB", "CAKE"]


@dataclass
class SynthItem:
    trajectory: Trajectory
    group_id: str
    label: int
    chain: str
    kind: str
    source_id: str


class _Builder:
    """Ghi action lan luot, tu quan ly thoi gian/dia chi/so du token."""

    def __init__(self, rng: random.Random, chain: str, t0: datetime, seed: str):
        self.rng, self.chain, self.t = rng, chain, t0
        self.chain_id = CHAINS[chain]
        self.block = rng.randint(10_000_000, 20_000_000)
        self.actions: List[CanonicalEvent] = []
        self.seed = seed

    def addr(self) -> str:
        return "0x" + format(self.rng.getrandbits(160), "040x")

    def tick(self, mean_sec: float):
        dt = self.rng.expovariate(1.0 / max(mean_sec, 1.0))
        self.t += timedelta(seconds=max(1.0, dt))
        self.block += max(1, int(dt / 3))

    def emit(self, src, dst, etype, amount, token, protocol=None, same_tx=False):
        tx = self.actions[-1].tx_hash if (same_tx and self.actions) else "0x" + format(self.rng.getrandbits(256), "064x")
        li = (self.actions[-1].log_index + 1) if (same_tx and self.actions) else 0
        self.actions.append(CanonicalEvent(
            chain_id=self.chain_id, block_number=self.block, timestamp=self.t, tx_hash=tx, log_index=li,
            src=src, dst=dst, event_type=etype, amount_norm=math.log1p(max(amount, 0.0)), token=token,
            protocol=protocol))


# ----------------------------------------------------------------------
# Typology rua tien
# ----------------------------------------------------------------------
def _decoy(b: _Builder, src: str, amount: float, token: str, p: float):
    """Chen transfer moi nho + nhip thoi gian cham (mimicry)."""
    if b.rng.random() < p:
        for _ in range(b.rng.randint(1, 3)):
            b.tick(b.rng.uniform(600, 5400))
            b.emit(src, b.addr(), "transfer", amount * b.rng.uniform(0.001, 0.02), token)


def _laundering(b: _Builder, d: float):
    rng = b.rng
    tok = NATIVE[b.chain]
    amount = 10 ** rng.uniform(4.5, 7.5)  # USD-tuong duong lon
    cur = b.seed
    mean_gap = 60 + d * 1800  # d cao -> nhip cham hon, giong nguoi dung
    typ = rng.choice(["peel_bridge", "split_swap_bridge", "swap_mixer", "nested_bridge", "lend_bridge"])
    # buoc 1: tach khoi vi exploiter qua 1-3 vi trung gian moi
    for _ in range(rng.randint(1, 3)):
        nxt = b.addr()
        b.tick(mean_gap)
        b.emit(cur, nxt, "transfer", amount, tok)
        _decoy(b, cur, amount, tok, d)
        cur = nxt
    if typ == "peel_bridge":
        for _ in range(rng.randint(3, 8)):
            nxt = b.addr()
            peel = amount * rng.uniform(0.02, 0.1)
            b.tick(mean_gap)
            b.emit(cur, b.addr(), "transfer", peel, tok)
            amount -= peel
            b.tick(mean_gap / 3)
            b.emit(cur, nxt, "transfer", amount, tok)
            _decoy(b, cur, amount, tok, d)
            cur = nxt
        b.tick(mean_gap)
        b.emit(cur, b.addr(), "bridge_deposit", amount, tok, protocol=rng.choice(BRIDGES))
    elif typ == "split_swap_bridge":
        k = rng.randint(3, 10)
        outs = [b.addr() for _ in range(k)]
        b.tick(mean_gap)
        for i, o in enumerate(outs):
            b.emit(cur, o, "split", amount / k, tok, same_tx=i > 0)
        br = rng.choice(BRIDGES)
        for o in outs:
            st = rng.choice(STABLES)
            b.tick(mean_gap)
            b.emit(o, o, "swap", amount / k, st, protocol=rng.choice(DEXES))
            _decoy(b, o, amount / k, st, d)
            b.tick(mean_gap)
            b.emit(o, b.addr(), "bridge_deposit", amount / k, st, protocol=br)
    elif typ == "swap_mixer":
        b.tick(mean_gap)
        b.emit(cur, cur, "swap", amount, tok, protocol=rng.choice(DEXES))
        for _ in range(rng.randint(2, 8)):
            b.tick(mean_gap / 2)
            b.emit(cur, b.addr(), "mixer_or_exit", rng.choice([10, 100]) * 1000, tok, protocol="Tornado Cash Router")
            _decoy(b, cur, amount, tok, d)
    elif typ == "nested_bridge":
        b1, b2 = rng.sample(BRIDGES, 2)
        b.tick(mean_gap)
        b.emit(cur, b.addr(), "bridge_withdraw", amount, tok, protocol=b1)
        b.tick(mean_gap)
        b.emit(cur, cur, "swap", amount, rng.choice(STABLES), protocol=rng.choice(DEXES))
        _decoy(b, cur, amount, tok, d)
        b.tick(mean_gap)
        b.emit(cur, b.addr(), "bridge_deposit", amount, rng.choice(STABLES), protocol=b2)
    else:  # lend_bridge
        b.tick(mean_gap)
        b.emit(cur, b.addr(), "lending_deposit", amount, tok, protocol="Venus Protocol")
        b.tick(mean_gap)
        b.emit(b.addr(), cur, "lending_withdraw", amount * 0.6, rng.choice(STABLES), protocol="Venus Protocol")
        _decoy(b, cur, amount, tok, d)
        b.tick(mean_gap)
        b.emit(cur, b.addr(), "bridge_deposit", amount * 0.6, rng.choice(STABLES), protocol=rng.choice(BRIDGES))
    return typ


# ----------------------------------------------------------------------
# Hanh vi binh thuong
# ----------------------------------------------------------------------
def _benign(b: _Builder, hard: bool):
    rng = b.rng
    tok = NATIVE[b.chain]
    amount = 10 ** rng.uniform(1.5, 6.5)
    cur = b.seed
    if hard:
        typ = rng.choice(["power_bridge_swap_split", "consolidate_bridge", "fast_rotation"])
    else:
        typ = rng.choice(["bridge_user", "dex_trader", "payroll_split", "consolidation", "arb_bot", "mixer_user"])
    gap = {"arb_bot": 15, "fast_rotation": 90}.get(typ, rng.uniform(300, 7200))
    # hoat dong thuong ngay (nhan/gui nho, swap le) de do dai negative chong
    # lan voi positive — tranh model phan biet chi nho do dai
    for _ in range(rng.randint(0, 25 if hard else 15)):
        b.tick(rng.uniform(120, 3600))
        if rng.random() < 0.7:
            b.emit(cur, b.addr(), "transfer", amount * rng.uniform(0.001, 0.05), tok)
        else:
            b.emit(cur, cur, "swap", amount * rng.uniform(0.01, 0.1), rng.choice(STABLES + VOLATILE),
                   protocol=rng.choice(DEXES))
    if typ == "bridge_user":
        b.tick(gap)
        b.emit(cur, b.addr(), "bridge_deposit", amount, tok, protocol=rng.choice(BRIDGES))
    elif typ == "dex_trader":
        for _ in range(rng.randint(1, 6)):
            b.tick(gap)
            b.emit(cur, cur, "swap", amount, rng.choice(STABLES + VOLATILE), protocol=rng.choice(DEXES))
    elif typ == "payroll_split":
        k = rng.randint(2, 12)
        b.tick(gap)
        for i in range(k):
            b.emit(cur, b.addr(), "split", amount / k, rng.choice(STABLES), same_tx=i > 0)
    elif typ == "consolidation":
        b.tick(gap)
        for i in range(rng.randint(2, 6)):
            b.emit(b.addr(), cur, "merge", amount / 4, tok, same_tx=i > 0)
        b.tick(gap)
        b.emit(cur, b.addr(), "transfer", amount, tok)
    elif typ == "arb_bot":
        for _ in range(rng.randint(4, 20)):
            b.tick(gap)
            b.emit(cur, cur, "swap", amount, rng.choice(VOLATILE + STABLES), protocol=rng.choice(DEXES))
    elif typ == "mixer_user":
        b.tick(gap)
        b.emit(cur, b.addr(), "mixer_or_exit", 1000, tok, protocol="Tornado Cash Router")
    elif typ == "power_bridge_swap_split":
        b.tick(gap)
        b.emit(b.addr(), cur, "bridge_withdraw", amount, tok, protocol=rng.choice(BRIDGES))
        b.tick(gap)
        b.emit(cur, cur, "swap", amount, rng.choice(STABLES), protocol=rng.choice(DEXES))
        k = rng.randint(2, 6)
        b.tick(gap)
        for i in range(k):
            b.emit(cur, b.addr(), "split", amount / k, rng.choice(STABLES), same_tx=i > 0)
    elif typ == "consolidate_bridge":
        for _ in range(rng.randint(2, 5)):
            nxt = b.addr()
            b.tick(gap)
            b.emit(cur, nxt, "transfer", amount, tok)
            cur = nxt
        b.tick(gap)
        b.emit(cur, b.addr(), "bridge_deposit", amount, tok, protocol=rng.choice(BRIDGES))
    else:  # fast_rotation
        for _ in range(rng.randint(3, 8)):
            nxt = b.addr()
            b.tick(gap)
            b.emit(cur, nxt, "transfer", amount * rng.uniform(0.9, 1.0), rng.choice([tok] + STABLES))
            cur = nxt
    return typ


def generate(n_incidents: int = 30, negatives_per_incident: int = 40, difficulty: float = 0.5,
             seed: int = 2026) -> List[SynthItem]:
    rng = random.Random(seed)
    items: List[SynthItem] = []
    base = datetime(2023, 1, 1, tzinfo=timezone.utc)
    for i in range(n_incidents):
        gid = f"synth_{i:03d}"
        chain = rng.choice(list(CHAINS))
        t0 = base + timedelta(days=rng.uniform(0, 900))
        b = _Builder(rng, chain, t0, "0x" + format(rng.getrandbits(160), "040x"))
        typ = _laundering(b, difficulty)
        items.append(SynthItem(Trajectory(trajectory_id=gid, seed_address=b.seed, actions=b.actions, label=1),
                               gid, 1, chain, f"synthetic_positive:{typ}", gid))
        for j in range(negatives_per_incident):
            hard = rng.random() < difficulty
            bn = _Builder(rng, chain, t0 + timedelta(hours=rng.uniform(-72, 72)), "0x" + format(rng.getrandbits(160), "040x"))
            ntyp = _benign(bn, hard)
            if not bn.actions:
                continue
            items.append(SynthItem(Trajectory(trajectory_id=gid, seed_address=bn.seed, actions=bn.actions, label=0),
                                   gid, 0, chain, f"synthetic_negative:{ntyp}", f"{gid}__n{j:03d}"))
    return items
