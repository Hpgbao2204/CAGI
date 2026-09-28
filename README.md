# CAGI-ED

**Early warning for cross-chain DeFi laundering.**

After an exploit, stolen funds move through fresh wallets, DEX swaps and splits
into a bridge or mixer within minutes. CAGI-ED follows the funds from the
exploiter's address, types each new on-chain action (transfer, swap, bridge,
lending, split, merge, mixer/exit) and re-scores the growing trajectory after
every step with a calibrated model, so an alert can fire *before* the funds
leave. Each alert is explained with TreeSHAP attributions and MITRE AADAPT
techniques.

```
explorer APIs → evidence cache → semantic decoder → value-flow trajectory → prefix features → XGBoost + Platt → alert + SHAP
```

## Results

15 real incidents (2021–2025, Ethereum / BNB Chain / Arbitrum), 514 hard
negatives, leave-one-incident-out evaluation.

| Metric | Result |
|---|---|
| Incidents alerted, θ = 0.5 | 9 / 15 at 2.8 % false alerts |
| Incidents alerted, θ = 0.3 | 14 / 15 at 6.6 % false alerts; 5–114 min before exit in 3 of 6 feasible cases |
| First-minute PR-AUC, typed vs. untyped features | 0.39 vs. 0.17 (p = 0.03) |
| Calibration (ECE) | 0.057 → 0.013 with Platt scaling |
| Scoring latency | 12–30 ms on a 4-core CPU |

All numbers are generated into `results/tables/`.

## Quick start

```bash
pip install -r requirements.txt
python -m pytest tests -q
bash scripts/reproduce_main.sh          # all tables and figures, ~30 min, no API key needed
```

**Rebuild from raw API responses** (134k responses, 3.2 GB unpacked):

```bash
(cd data/raw_archive && sha256sum -c SHA256SUMS)
cat data/raw_archive/raw_cache.tar.xz.part* | tar -xJf - -C data/
bash scripts/reproduce_main.sh --raw
```

**Re-crawl from scratch:** copy `.env.example` to `.env`, fill in
`ETHERSCAN_API_KEY` and `BSCTRACE_API_KEY`, then run
`python scripts/crawl_all.py --chains eth arbitrum` and `--chains bsc`.

## Layout

| Path | Content |
|---|---|
| `src/collect` | Etherscan V2 / NodeReal clients, hard-negative miner |
| `src/normalize` | Event schema and semantic decoder |
| `src/trajectories` | Bounded value-flow trajectory builder |
| `src/features` | Prefix-safe features (actions 1..k only) |
| `src/models` | Baselines, GRU sequence model, CAGI-ED scorer |
| `src/evaluation` | Leave-one-incident-out, calibration, bootstrap |
| `src/synth` | Synthetic benchmark generator (reported separately) |
| `scripts` | Crawling, experiments, figures, one-command reproduction |
| `metadata` | Incident and hard-negative registries, protocol map, splits |
| `data` | Raw API archive and processed trajectories |
| `results/tables` | Result tables, run manifest, per-trajectory provenance |

## Data and ethics

Incidents are publicly documented exploits, labeled from on-chain evidence and
public reports (CertiK, SlowMist, PeckShield, Chainalysis, …). Hard negatives
are other users of the same bridges, DEXs and mixers within ±7 days.
Trajectories that could not be fully collected are excluded and listed in
`results/tables/dataset_provenance.json`. Only public data is used, no
real-world identities are inferred, and alerts are intended for human review.

## License

[MIT](LICENSE)
