# Raw API evidence cache

`raw_cache.tar.xz.part*` is the complete `data/raw/` directory produced by
`scripts/crawl_all.py` (Etherscan V2 for Ethereum/Arbitrum, NodeReal
`nr_getAssetTransfers` for BSC). Every JSON file holds one API response
verbatim with its request time and SHA-256.

The archive is the union of two crawls: the 2026-08-27/28 crawl (most of the
BSC hard negatives) and the 2026-09-27 re-collection (current window
parameters for Ethereum and Arbitrum). Where both crawls cached the same key,
the 2026-09-27 response is kept; the two responses differ only in request time
and NodeReal page keys. In total 134,270 responses, 3.2 GB unpacked
(3.9k Arbitrum, 125.0k BSC, 5.4k Ethereum files), split into parts under 100 MB
for GitHub.

Restore:

```bash
(cd data/raw_archive && sha256sum -c SHA256SUMS)
cat data/raw_archive/raw_cache.tar.xz.part* | tar -xJf - -C data/
python scripts/run_experiments.py --stage dataset   # rebuild trajectories from data/raw
```

Trajectories whose addresses are not fully cached are excluded (95 BSC
candidates and one each on Ethereum and Arbitrum), see
`results/tables/dataset_provenance.json`.
