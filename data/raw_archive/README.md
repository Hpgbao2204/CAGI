# Raw API evidence cache

`raw_cache.tar.xz.part*` is the complete `data/raw/` directory produced by
`scripts/crawl_all.py` (Etherscan V2 for Ethereum/Arbitrum, NodeReal
`nr_getAssetTransfers` for BSC), collected 2026-09-27. Every JSON file
holds one API response verbatim with its request time and SHA-256.

Restore:

```bash
sha256sum -c data/raw_archive/SHA256SUMS
cat data/raw_archive/raw_cache.tar.xz.part* | tar -xJf - -C data/
python scripts/run_experiments.py --stage dataset   # rebuild trajectories from data/raw
```

The BSC part is incomplete (free NodeReal quota exhausted): trajectories
whose addresses are not fully cached are excluded, see
`results/tables/dataset_provenance.json`.
