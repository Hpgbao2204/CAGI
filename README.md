# CAGI-ED

**Early detection of cross-chain DeFi laundering from trajectory prefixes.**
CAGI-ED theo dõi một địa chỉ seed sau vụ exploit, decode mỗi giao dịch mới
thành một hành động có kiểu (transfer, swap, bridge, lending, split, merge,
mixer/exit), mở rộng dòng tiền bị đánh dấu (tainted value flow) và chấm điểm
lại *prefix* của trajectory sau mỗi hành động. Mục tiêu là cảnh báo **trước**
khi tiền tới điểm thoát (bridge, mixer, lending) — khác với các hệ thống truy
vết chỉ tái dựng dòng tiền sau khi mọi thứ đã xong.

## Cấu trúc repo

```
src/
  collect/        Etherscan V2 (eth, arbitrum) + NodeReal (bsc) client, hard-negative miner
  normalize/      decoder -> CanonicalEvent có kiểu, protocol map đã verify
  trajectories/   bounded value-flow builder
  pipeline/       collect -> decode -> build cho 1 incident; dataset_builder
  features/       37 feature prefix-safe (flat / typed action / motif)
  models/         B0-B3, B3', M1 (XGBoost), S1 (GRU)
  evaluation/     LOIO + calibration + bootstrap mức incident (loio.py)
  synth/          CAGI-Synth: bộ sinh dữ liệu TỔNG HỢP (báo cáo tách riêng)
scripts/
  crawl_all.py        crawl lại toàn bộ data/raw từ API (resume được)
  run_experiments.py  MỌI số liệu trong paper, 1 lần chạy
  make_figures.py     hình fig2a ... fig7b
  reproduce_main.sh   chạy lại toàn bộ
  mining/             script mining hard-negative (lịch sử)
metadata/         incident_registry.csv, hard_negative_registry*.csv, protocol_map.yaml, split_manifest.json
data/
  raw_archive/        toàn bộ cache API (tar.xz, 84 MB, giải nén ra 1.5 GB)
  processed/trajectories_v3.jsonl.gz   408 trajectory đã decode dùng trong paper
  processed/original_trace/            trace decode từ lần crawl gốc (fallback)
results/tables/   toàn bộ bảng số liệu (CSV/JSON) + run_manifest.json
paper/            LaTeX (LNCS), figures/, sections/
tests/            pytest (196 test)
```

## Tái lập

```bash
pip install -r requirements.lock
bash scripts/reproduce_main.sh          # từ trajectories_v3.jsonl.gz, không cần API
bash scripts/reproduce_main.sh --raw    # từ data/raw (giải nén data/raw_archive trước)
python -m pytest tests/ -q
cd paper && latexmk -pdf cagi_nss2026.tex
```

Crawl lại từ đầu (cần `ETHERSCAN_API_KEY`, `BSCTRACE_API_KEY` trong môi trường):

```bash
python scripts/crawl_all.py --chains eth arbitrum
python scripts/crawl_all.py --chains bsc
```

## Dữ liệu

* 15 incident cross-chain công khai (2021–2025; 8 BSC, 5 Arbitrum, 2 Ethereum).
  Nhãn do nhóm tự trace và đối chiếu với báo cáo công khai (CertiK, SlowMist,
  PeckShield, Chainalysis, ...). Danh sách 82 case của AMLGuard chỉ dùng để
  tìm ứng viên, không dùng ground truth của họ.
* 393 hard negative: counterparty của CÙNG bridge/DEX/mixer trong ±7 ngày,
  mở rộng với CÙNG collector/builder/độ sâu như incident.
* Quota NodeReal miễn phí hết giữa chừng: 223/272 negative BSC có cache chưa
  đủ bị loại; Paraluni dựng lại từ trace decode gốc. Chi tiết từng
  trajectory: `results/tables/dataset_provenance.json`.
* **CAGI-Synth** (`src/synth/`) là dữ liệu tổng hợp, chỉ dùng cho benchmark
  độ khó riêng, KHÔNG trộn vào kết quả trên dữ liệu thật.

## Đạo đức

Chỉ dùng dữ liệu on-chain công khai và nhãn từ báo cáo công khai; không
deanonymize danh tính thật của bất kỳ ai. Cảnh báo được thiết kế cho người
phân tích xem xét, không phải để tự động phong toả.
