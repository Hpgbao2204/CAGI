"""Re-collect data/raw from the explorer APIs for every trajectory listed in
metadata/ (incidents and hard negatives), using the same
expand_and_build_trajectory as the dataset builder. Resumable and shardable.

    python scripts/crawl_all.py --chains eth arbitrum   # Etherscan V2 (3 req/s free tier)
    python scripts/crawl_all.py --chains bsc            # NodeReal MegaNode
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from pathlib import Path

import pandas as pd
import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.collect.bsctrace_client import BscTraceClient  # noqa: E402
from src.collect.etherscan_client import EtherscanClient  # noqa: E402
from src.pipeline.dataset_builder import AUXILIARY_INCIDENT_IDS, HARD_NEGATIVE_REGISTRY_V2_COMPLEXITY_PATH  # noqa: E402
from src.collect.hard_negative_miner import HARD_NEGATIVE_REGISTRY_PATH  # noqa: E402
import src.pipeline.incident_pipeline as ip  # noqa: E402
from src.pipeline.incident_pipeline import RAW_DIR, REGISTRY_PATH, expand_and_build_trajectory  # noqa: E402

_orig_collect = ip.collect_address_raw_data


def _address_cache_complete(chain: str, address: str, scope: str) -> bool:
    """Cache 1 dia chi da day du chua (de chay tiep khong goi lai API).
    bsc: trang inbound cuoi (w1000+) phai khong con pageKey (hoac cham tran
    100 trang). eth/arbitrum: da co file txlistinternal (goi cuoi cung)."""
    d = RAW_DIR / chain / address.lower() / scope
    if not d.exists():
        return False
    if chain == "bsc":
        inbound = sorted(d.glob("assettransfers_w1*.json"), key=lambda f: int(f.stem.split("_w")[1]))
        inbound = [f for f in inbound if int(f.stem.split("_w")[1]) >= 1000]
        if not inbound:
            return False
        if len(inbound) >= 100:
            return True
        res = json.loads(inbound[-1].read_text())["response"].get("result") or {}
        return not res.get("pageKey") or not res.get("transfers")
    return ip.address_cache_complete(chain, address, scope)


def _collect_skip_complete(client, chain, address, incident_id, start_block, end_block):
    if _address_cache_complete(chain, address, incident_id):
        return
    _orig_collect(client, chain, address, incident_id, start_block, end_block)


ip.collect_address_raw_data = _collect_skip_complete

from src.trajectories.builder import load_trajectory_config  # noqa: E402

# CUNG so vong mo rong cho moi trajectory (configs/data.yaml::expand_iterations)
MAX_ITERATIONS = load_trajectory_config().expand_iterations


class ThrottledCountingSession(requests.Session):
    """Session dem so request va giu khoang cach toi thieu giua 2 request
    (Etherscan free: 3 req/s)."""

    def __init__(self, min_interval_sec: float) -> None:
        super().__init__()
        self.min_interval_sec = min_interval_sec
        self.n_requests = 0
        self._last = 0.0
        self._lock = threading.Lock()

    def request(self, *args, **kwargs):
        with self._lock:
            wait = self._last + self.min_interval_sec - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            self.n_requests += 1
        return super().request(*args, **kwargs)


def build_jobs(chains):
    jobs = []
    reg = pd.read_csv(REGISTRY_PATH)
    for _, r in reg.iterrows():
        if r["chain_primary"] in chains:
            jobs.append(dict(job_id=r["incident_id"], chain=r["chain_primary"], seed=r["seed_address"],
                             start_block=int(r["start_block"]), scope=r["incident_id"],
                             label=int(r["label"]), max_iterations=MAX_ITERATIONS))
    for path in (HARD_NEGATIVE_REGISTRY_PATH, HARD_NEGATIVE_REGISTRY_V2_COMPLEXITY_PATH):
        hn = pd.read_csv(path)
        hn = hn[~hn["parent_incident_id"].isin(AUXILIARY_INCIDENT_IDS)]
        for _, r in hn.iterrows():
            if r["chain"] in chains:
                jobs.append(dict(job_id=r["hard_negative_id"], chain=r["chain"], seed=r["seed_address"],
                                 start_block=int(r["start_block"]), scope=r["parent_incident_id"],
                                 label=0, max_iterations=MAX_ITERATIONS))
    return jobs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chains", nargs="+", default=["eth", "arbitrum", "bsc"])
    ap.add_argument("--limit", type=int, default=None, help="chi chay N job dau (thu nghiem)")
    ap.add_argument("--eth-min-interval", type=float, default=0.36,
                    help="giay giua 2 request Etherscan TRONG 1 tien trinh (n shard -> dat ~n*0.36)")
    ap.add_argument("--workers", type=int, default=1, help="so dia chi frontier crawl song song trong 1 job")
    ap.add_argument("--shard", default="0/1", help="i/n: chi chay job thu i, i+n, ... (chay song song)")
    args = ap.parse_args()

    si, sn = map(int, args.shard.split("/"))
    state_path = RAW_DIR / f"_crawl_state_{'_'.join(sorted(args.chains))}_{si}of{sn}.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {}

    eth_session = ThrottledCountingSession(min_interval_sec=args.eth_min_interval)
    bsc_session = ThrottledCountingSession(min_interval_sec=0.05)
    clients = {}
    if {"eth", "arbitrum"} & set(args.chains):
        ec = EtherscanClient(cache_dir=RAW_DIR, session=eth_session)
        clients["eth"] = clients["arbitrum"] = ec
    if "bsc" in args.chains:
        clients["bsc"] = BscTraceClient(cache_dir=RAW_DIR, session=bsc_session)

    jobs = build_jobs(set(args.chains))
    if args.limit:
        jobs = jobs[: args.limit]
    jobs = jobs[si::sn]
    done = {}
    for f in RAW_DIR.glob("_crawl_state_*.json"):
        done.update(json.loads(f.read_text()))
    todo = [j for j in jobs if j["job_id"] not in done]
    print(f"{len(jobs)} job, {len(jobs) - len(todo)} da xong, con {len(todo)}", flush=True)

    t0 = time.time()
    for i, j in enumerate(todo, 1):
        before = eth_session.n_requests + bsc_session.n_requests
        ts = time.time()
        try:
            traj, _, processed = expand_and_build_trajectory(
                j["chain"], j["seed"], j["start_block"], j["scope"], j["label"],
                do_collect=True, max_iterations=j["max_iterations"], client=clients[j["chain"]],
                request_delay_sec=0.0, collect_workers=args.workers,
            )
        except Exception as exc:  # ghi loi, chay tiep job khac
            print(f"[{i}/{len(todo)}] {j['job_id']} LOI: {exc!r}", flush=True)
            continue
        n_req = eth_session.n_requests + bsc_session.n_requests - before
        state[j["job_id"]] = dict(chain=j["chain"], n_actions=len(traj.actions), n_addresses=len(processed),
                                  n_requests=n_req, sec=round(time.time() - ts, 1))
        state_path.write_text(json.dumps(state, indent=1))
        print(f"[{i}/{len(todo)}] {j['job_id']} ({j['chain']}): {len(traj.actions)} action, "
              f"{len(processed)} addr, {n_req} req, tong req eth={eth_session.n_requests} "
              f"bsc={bsc_session.n_requests}, {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
