# Reproducibility sprint v1.0 — Tuần 10

Mục tiêu: đảm bảo người khác (hoặc chính người thực hiện sau này) chạy lại
được toàn bộ kết quả chính từ snapshot Tuần 9 (freeze v1.0), không cần kiến
thức ngầm.

## Bước 1 — Clean environment

- `requirements.lock` (mới): pin CHÍNH XÁC version mọi dependency, sinh từ
  1 venv HOÀN TOÀN SẠCH (không phải môi trường Python dùng chung trên máy —
  môi trường đó có hàng trăm gói không liên quan dự án: `frida`, `pwntools`,
  `volatility3`, `mysql-connector-python`...).
- **Phát hiện: `requirements.txt` cũ SAI** — liệt kê `polars`, `networkx`,
  `responses` nhưng **KHÔNG hề được cài, và grep xác nhận KHÔNG được import
  ở BẤT KỲ đâu trong `src/`/`scripts/`/`tests/`** — 3 gói chết, có lẽ dự
  kiến dùng từ đầu dự án nhưng chưa từng dùng thật. Đồng thời **thiếu**
  `joblib`, `psutil`, `scipy` — dùng trực tiếp trong code nhưng chưa liệt kê.
  Đã sửa `requirements.txt` (bỏ 3 gói chết, thêm 3 gói thiếu).
- `numpy` ghim thủ công `==2.2.4` trong `requirements.lock` — nếu không
  ghim, `pip` tự resolve ra `2.5.2` (mới hơn, đã thử — xem Bước 5).
- `.gitignore` đã rà soát: `*.parquet` và `data/raw/*` loại đúng (dữ liệu
  lớn, regenerable từ cache/API — không phải code/config cần thiết). Không
  phát hiện file CẦN THIẾT nào bị loại nhầm.

## Bước 2 — One-command reproduction

`scripts/reproduce_main.sh` — viết lại THẬT (thay placeholder cũ chỉ in
`echo "TODO..."`). Chạy 12 bước tuần tự (RQ1 → ceiling check → M1 final →
error analysis → RQ2 prefix eval → leakage check → lead time → RQ2 figures
→ ablation E4/E5 → E6 robustness → calibration → efficiency benchmark),
HOÀN TOÀN OFFLINE (không gọi API on-chain nào — xác nhận qua code review:
`run_e6_robustness.py` dùng `fetch_contract_counterparties(...,
do_collect=False)`, mọi script khác chỉ đọc `features_v2.parquet`/cache).

**Đã chạy dry-run thật** (không phải chỉ viết script rồi tin là đúng):
- Lần 1: crash `UnicodeEncodeError` (xem Bước 5/6 — lỗi thật, đã sửa).
- Lần 2 (sau khi sửa): **chạy thành công, 1087 giây (~18 phút)**, toàn bộ
  10 file output chính đều được tạo, số liệu khớp Tuần 9 (xem Bước 5).

## Bước 3 — Xóa thông tin cá nhân, kiểm tra license

- **API key**: rà soát toàn bộ file tracked (`git grep`) + toàn bộ
  `data/raw/` cache (filesystem grep) — **KHÔNG phát hiện key thật nào bị
  lộ**. `.env` chưa từng được commit (xác nhận qua `git log --all`).
  `.env.example` chỉ chứa placeholder (`your_key_here`).
- **Path cá nhân — phát hiện 1 vụ, đã sửa**: `scripts/
  migrate_cache_to_incident_scoped.py` (commit `18090d5`, script migration
  MỘT LẦN đã chạy xong từ trước) có hardcode đường dẫn scratchpad phiên làm
  việc cũ, chứa username Windows cá nhân + session ID. Đã sửa file (redact
  đường dẫn + ghi chú rõ đây là script lịch sử không còn chạy lại được).
  **KHÔNG rewrite git history** (quyết định có cân nhắc): đây là username
  Windows local + session UUID ngẫu nhiên (không phải credential/bí mật
  thật), rewrite history sẽ phá vỡ mọi commit hash đã được ghi lại xuyên
  suốt dự án (freeze_v1.0.json, model_card_m1.md...) — chi phí rủi ro cao
  hơn hẳn lợi ích của việc xóa 1 username không nhạy cảm. Nếu người dùng
  muốn rewrite history, đây là quyết định cần xác nhận riêng.
- **License/sharing**: `data/dataset_card.md` mục "License / sử dụng" đã
  viết lại đầy đủ hơn — phân biệt rõ dữ liệu ĐƯỢC PHÉP chia sẻ (on-chain
  data công khai + nhãn tự gán) vs KHÔNG chứa (ground truth AMLGuard độc
  quyền) vs CHƯA XÁC NHẬN (license figshare AMLGuard cho `AML_Incidents.csv`/
  `SOTA-Tool.zip`; ToS Etherscan/BscScan/NodeReal cho việc redistribute raw
  response — ghi rõ đây là điểm CHƯA rà soát, không giả định compliance).

## Bước 4 — Checksum, seed, hardware note

- `artifact_manifest.json` (mới, repo root): liệt kê TOÀN BỘ artifact trong
  `results/tables/`, `results/figures/`, `results/reports/`, `results/models/`
  kèm sha256, size, mtime, trạng thái git-tracked, commit hash. Khác
  `freeze_v1.0.json` (Tuần 9 — chỉ 16 file "đóng cứng chính thức") — file
  này bao quát TOÀN BỘ, dùng để audit tổng thể.
- **Random seed** — rà soát toàn bộ `src/`/`scripts/` (grep `random_state`/
  `seed`/`default_rng`): **thống nhất `42`** ở mọi nơi có tính ngẫu nhiên
  (bootstrap CI, paired bootstrap, XGBoost/RandomForest `random_state`).
  Không có lời gọi `np.random.seed()` toàn cục nào (dùng
  `np.random.default_rng()` cục bộ — tránh ô nhiễm state toàn cục giữa các
  lần gọi). `PYTHONHASHSEED` không cần set — thứ tự lặp dict đã được xử lý
  bằng `dict.fromkeys()` (khử phụ thuộc hash-seed ngẫu nhiên, xem
  `src/pipeline/incident_pipeline.py`).
- **Hardware benchmark (RQ4)**: xem `results/reports/runtime_v1.md` mục
  Hardware — Windows-11, AMD64 8-core vật lý/16-thread, Python 3.13.0.
  `total_ram_gb=7.78` được ghi chú rõ có thể là giới hạn VM/container, không
  chắc là RAM vật lý đầy đủ.
- **Expected runtime cho `reproduce_main.sh`**: đo thật **1087 giây (~18
  phút)** trên hardware trên — đã ghi vào chính script + README.

## Bước 5 — Clean rerun thật

- Tạo venv sạch (`.venv_clean_test`, đã xóa sau khi test xong — không phải
  artifact commit), cài `requirements.lock` (numpy ghim `2.2.4` thủ công —
  pip tự resolve `2.5.2` nếu không ghim, đã xác nhận).
- **Chạy CHÍNH THỨC `reproduce_main.sh` BÊN TRONG venv sạch** (không chỉ
  dry-run ở môi trường hiện tại): **THÀNH CÔNG, 814 giây (~13 phút)**,
  toàn bộ 10 file output chính đều được tạo.
- **`pytest tests/ -v` CHẠY TRONG ĐÚNG VENV SẠCH ĐÓ: 177/177 PASS.**
- Đối chiếu số liệu output của lần chạy venv-sạch với kết quả Tuần 9 —
  **khớp chính xác** (không phải "gần đúng"):
  - RQ1 paired M1 vs B3: mean diff -0.0065, CI [-0.0883,+0.0813] — khớp.
  - Ablation M1_no_temporal: diff +0.0194 [-0.0609,+0.1269] — khớp.
  - E6 robustness: diff -0.1343 [-0.2535,-0.0270], p=0.0254 — khớp.
- Trước đó, dry-run ở môi trường hiện tại (đã cài `requirements.lock`,
  KHÔNG phải venv riêng biệt) cũng xác nhận số liệu khớp Tuần 9:
  - RQ1 (`main_table.csv`): M1=0.7190, B3=0.6890 — khớp 100%.
  - Lead time: median=1.00h IQR=[0.82,1.17] — khớp 100%.
  - Ablation (`ablation_table.csv`): M1_no_temporal/no_motif/no_bridge_context
    — Mean PR-AUC + paired diff khớp 100% (vd no_temporal: 0.6769
    [0.4828,0.8653], diff=+0.0194).
  - `runtime_table.csv` (RQ4): **latency dao động nhỏ giữa các lần chạy**
    (vd n_events=2: 15.5ms → 18.5ms → 19.4ms qua 3 lần chạy) — ĐÚNG NHƯ DỰ
    ĐOÁN (hardware timing noise, không phải randomness thiếu seed — không
    có gì cần seed ở benchmark latency). Không phải lỗi tái lập.
- **2 lỗi/vấn đề THẬT phát hiện khi clean rerun (không phải giả định):**
  1. **`UnicodeEncodeError`** khi chạy trên Windows console không set UTF-8
     — sửa gốc bằng cách thêm `export PYTHONIOENCODING=utf-8` +
     `PYTHONUTF8=1` vào đầu `reproduce_main.sh` (đã dùng thủ công suốt các
     tuần trước mà CHƯA từng ghi chính thức — đúng tinh thần "không kiến
     thức ngầm" của Tuần 10).
  2. **Narrative bị mất khi rerun script**: `run_efficiency_benchmark.py`
     và `run_e6_robustness.py` có phần diễn giải đã sửa tay ở Tuần 9 (sau
     khi chạy script) — chạy lại script XÓA MẤT phần sửa tay đó (script chỉ
     ghi lại phần diễn giải "mặc định" ban đầu). Đây LÀ lỗi tái lập thật
     (không phải số liệu sai, mà là tài liệu/diễn giải không bền vững qua
     rerun) — đã sửa gốc: đưa diễn giải ĐÚNG vào chính logic sinh report của
     2 script (tính động từ dữ liệu, không hardcode), xác nhận lại bằng
     cách chạy lại 2 script — nội dung đúng, đầy đủ, khớp bản đã điều tra ở
     Tuần 9. Áp dụng CÙNG cách sửa cho `diagnose_ceiling_effect_v1.py`
     (Bước 3 — điều tra `paraluni_2022` — cũng bị mất khi rerun, cùng lỗi).

  3. **Phát hiện phụ (không phải bug, nhưng đáng chú ý):** sau khi sửa
     `diagnose_ceiling_effect_v1.py` để tính Bước 3 ĐỘNG (không hardcode),
     kết quả tính lại **MÂU THUẪN với kết luận cũ Tuần 6** — trước đó ghi
     `paraluni_2022`'s hard-negative median length = 25 (≥ positive = 24,
     "giải thích" vì sao tín hiệu độ dài mất tác dụng); tính lại bằng dữ
     liệu hiện tại cho median = 5 (KHÔNG còn ≥ positive). Nguyên nhân: bug
     `generate_prefixes` (Tuần 7, đã sửa) từng khiến CHỈ 10/31 hard-negative
     của `paraluni_2022` có dòng `ratio_100` (trajectory ngắn bị loại khỏi
     bucket này) — sau khi sửa, cả 31 đều có, kéo median xuống hẳn. **Kết
     luận cũ về nguyên nhân `paraluni_2022` khó phân biệt (dựa trên độ dài)
     đã LỖI THỜI** — không tự ý điều tra lại nguyên nhân mới (ngoài phạm vi
     Tuần 10, đã ghi nhận trung thực trong `rq1_ceiling_sensitivity.md`).

## Bước 6 — Troubleshooting note

Đã ghi vào `README.md` mục "Troubleshooting" — 6 mục cụ thể (Unicode,
`PYTHONPATH`, `features_v2.parquet` thiếu, numpy version, `runtime_table.csv`
không khớp hardware, narrative bị mất khi rerun) — TẤT CẢ đều là lỗi/hiện
tượng THẬT gặp trong lúc test (không viết trước theo suy đoán).

## Tổng kết

`pytest tests/ -v` chạy SAU clean rerun (Bước 5) để xác nhận môi trường mới
vẫn pass đầy đủ — xem kết quả cuối trong lịch sử commit Tuần 10 (tách riêng
khỏi việc tái tạo số liệu, đúng nguyên tắc "code đúng" ≠ "số liệu khớp").
