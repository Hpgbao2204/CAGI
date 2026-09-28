#!/usr/bin/env bash
# Regenerate every table (results/tables) and figure (paper/figures).
#
#   bash scripts/reproduce_main.sh          # from data/processed/trajectories_v3.jsonl.gz (no API)
#   bash scripts/reproduce_main.sh --raw    # rebuild trajectories from data/raw (extract data/raw_archive first)
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
export PYTHONPATH="$PWD" PYTHONIOENCODING=utf-8 PYTHONUTF8=1
PY="${PYTHON:-python}"

if [[ "${1:-}" == "--raw" ]]; then
  "$PY" scripts/run_experiments.py --stage dataset
else
  "$PY" scripts/run_experiments.py --stage dataset --from-export
fi
"$PY" scripts/run_experiments.py --stage rq1 spearman seq rq2 rq2paired calib explain stress synth gate runtime
# builder sensitivity rebuilds trajectories with other settings: needs data/raw
if [[ -d data/raw/eth ]]; then "$PY" scripts/run_experiments.py --stage builder; fi
"$PY" scripts/make_figures.py
echo "Done: results/tables/*, paper/figures/fig*.pdf (runtime.csv depends on the hardware)."
