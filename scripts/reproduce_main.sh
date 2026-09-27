#!/usr/bin/env bash
# Tai tao TOAN BO so lieu + hinh cua paper.
#
#   bash scripts/reproduce_main.sh            # tu data/processed/trajectories_v3.jsonl.gz (khong can API)
#   bash scripts/reproduce_main.sh --raw      # build lai trajectory tu data/raw/ (giai nen data/raw_archive/ truoc)
#
# Crawl lai data/raw tu dau (can ETHERSCAN_API_KEY, BSCTRACE_API_KEY):
#   python scripts/crawl_all.py --chains eth arbitrum
#   python scripts/crawl_all.py --chains bsc
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
export PYTHONPATH="$PWD" PYTHONIOENCODING=utf-8 PYTHONUTF8=1
PY="${PYTHON:-python}"

if [[ "${1:-}" == "--raw" ]]; then
  "$PY" scripts/run_experiments.py --stage dataset
else
  "$PY" scripts/run_experiments.py --stage dataset --from-export
fi
"$PY" scripts/run_experiments.py --stage rq1 seq rq2 calib explain stress builder synth gate runtime
"$PY" scripts/make_figures.py
echo "Xong: results/tables/*.csv, paper/figures/fig*.pdf"
echo "Luu y: runtime.csv phu thuoc phan cung (xem results/tables/runtime_hardware.json)."
