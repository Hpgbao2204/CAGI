# CAGI-ED: early warning for cross-chain DeFi laundering

After a DeFi exploit, the attacker moves the stolen funds through fresh wallets,
DEX swaps and splits into a bridge, mixer or lending market, often within
minutes. Existing tracers reconstruct that path **after** it is complete.
CAGI-ED raises the alarm **while it is happening**: it follows the funds from
the exploiter's address, types every new on-chain action (transfer, swap,
bridge, lending, split, merge, mixer/exit), and re-scores the growing
trajectory after each action with a calibrated model. Each alert comes with the
features and MITRE AADAPT techniques that triggered it.

```
explorer APIs ─► evidence cache ─► semantic decoder ─► value-flow trajectory ─► prefix features ─► XGBoost + Platt ─► alert + TreeSHAP
(Etherscan V2,    (raw JSON +        (typed actions,      (follow tainted value     (37 features:      (p̂_k ≥ θ ?)
 NodeReal)         SHA-256)           verified contracts)  from the seed)            flat/typed/motif)
```

## Results (15 real incidents, 393 hard negatives, leave-one-incident-out)

| | |
|---|---|
| Incidents alerted (θ = 0.5) | 12 / 15, false alerts on 5.8% of hard negatives |
| Alert before the exit | 3 of the 6 incidents where it is possible, 5–114 min early |
| First minute of a flow | typed features double PR-AUC vs. the same model on untyped features (0.42 vs 0.22, p = 0.01) |
| Over all prefixes | typed 0.48 vs untyped 0.52 (not significant); rule-based typology score 0.21 |
| Calibration | ECE 0.071 → 0.015 with Platt scaling |
| Cost | 12–24 ms per scoring on a 4-core CPU, no GPU |

Full analysis: `paper/cagi_nss2026.tex`. Every number comes from `results/tables/`.

## Quick start

```bash
pip install -r requirements.txt
bash scripts/reproduce_main.sh     # all tables + figures from the released trajectories (~30 min, no API key)
python -m pytest tests -q
cd paper && latexmk -pdf cagi_nss2026.tex
```

To rebuild from the raw API responses instead:
`cat data/raw_archive/raw_cache.tar.xz.part* | tar -xJf - -C data/ && bash scripts/reproduce_main.sh --raw`.
To re-crawl from scratch, set `ETHERSCAN_API_KEY` and `BSCTRACE_API_KEY` (see `.env.example`)
and run `python scripts/crawl_all.py --chains eth arbitrum` and `--chains bsc`.

## Repository

| Path | Content |
|---|---|
| `src/collect` | Etherscan V2 / NodeReal clients, hard-negative miner |
| `src/normalize` | event schema and semantic decoder |
| `src/trajectories` | bounded value-flow trajectory builder |
| `src/features` | prefix-safe features (uses actions 1..k only) |
| `src/models` | baselines B0–B3, B3′, GRU (S1), CAGI-ED scorer (M1) |
| `src/evaluation` | leave-one-incident-out, calibration, incident-level bootstrap |
| `src/synth` | CAGI-Synth synthetic generator (reported separately, never mixed with real data) |
| `scripts` | `crawl_all.py`, `run_experiments.py`, `make_figures.py`, `reproduce_main.sh` |
| `metadata` | incident registry, hard-negative registries, verified protocol map, group splits |
| `data` | raw API cache (`raw_archive/`, 135 MB → 2.4 GB) and decoded trajectories (`processed/`) |
| `results/tables` | every result table, run manifest and provenance of each trajectory |
| `paper` | LNCS manuscript, sections and figures |

## Data

15 publicly documented incidents (2021–2025) on Ethereum, BNB Smart Chain and
Arbitrum, labeled by the authors from on-chain evidence and public reports
(CertiK, SlowMist, PeckShield, Chainalysis, …). Hard negatives are other users
of the same bridges, DEXs and mixers within ±7 days, expanded exactly like the
incidents. Part of the BSC data could not be collected on the free NodeReal
quota; those trajectories are excluded and listed in
`results/tables/dataset_provenance.json`.

Only public data is used; no real-world identities are inferred. Alerts are
meant for human review, not automatic enforcement.

License: MIT.
