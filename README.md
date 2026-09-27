# CAGI-ED

**Explainable Early Detection of Cross-Chain DeFi Laundering from Temporal Motifs** — phát hiện sớm hoạt động rửa tiền DeFi xuyên chuỗi từ *prefix* (đoạn đầu) của quỹ đạo giao dịch, trước khi tiền tới điểm đến cuối cùng.

## Bối cảnh & đóng góp

Các hệ thống truy vết rửa tiền DeFi hiện có (ví dụ AMLGuard, ISSTA'26) tập trung **trace toàn bộ quỹ đạo** từ seed đã biết đến điểm đến cuối cùng — tức chỉ hoạt động *sau khi* đã biết điểm đến. CAGI-ED chuyển trọng tâm sang bài toán **cảnh báo sớm**: chỉ quan sát một **phần đầu (prefix)** của quỹ đạo — trước khi điểm đến được xác nhận — và dự đoán mức độ rủi ro dựa trên các *typed temporal motif* (mô-típ hành vi có kiểu, theo thời gian: bridge→swap, split/merge, peel-chain...). Ground truth do nhóm **tự trace và tự gán** từ dữ liệu on-chain công khai, đối chiếu báo cáo điều tra công khai độc lập — không sao chép nhãn từ bất kỳ dataset độc quyền nào.

## Kết quả chính

**RQ1 — M1 (typed temporal motif) có vượt B3 (untyped/flat) không?**
Leave-one-incident-out, 15 fold, bootstrap CI 95% mức incident:

| Model | Mean PR-AUC |
|---|---|
| B3 (untyped/flat) | 0.6875 |
| M1 (typed motif) | 0.6911 | 

**RQ2 — Model có phát hiện được sớm (từ prefix) không?**
Mean PR-AUC (15 fold) theo % quỹ đạo đã quan sát:

| Mốc prefix | 25% | 50% | 75% | 100% |
|---|---|---|---|---|
| Mean PR-AUC | 0.9333 | 0.8491 | 0.9350 | 0.9407 |

→ Phát hiện tốt ngay ở 25% quỹ đạo đầu tiên (PR-AUC 0.93), xác nhận tính khả thi của early detection.

Ngoài ra: RQ3 (next-event prediction) không đạt data gate nên đã loại khỏi phạm vi chính thức; RQ4 xác nhận hiệu năng model CPU-only, latency dưới 30ms/trajectory kể cả ở độ dài lớn; đã bổ sung ablation (temporal/motif/bridge-context) và calibration xác suất.

## Cấu trúc dataset (freeze v2.0, 2026-08-28)

| | Giá trị |
|---|---|
| Incident positive | 15 (2021–2025, báo cáo công khai CertiK/SlowMist/Halborn/Chainalysis...) |
| Hard-negative dùng được | 612 (500 mining chính + 107 mining bổ sung + 5 control gốc) |
| Tổng prefix row | 3.354 |
| Chain | Ethereum, BSC, Arbitrum |
| Bridge family đã verify | 8 (Ronin Bridge, QBridge, FEG SmartBridge, Multichain, BSC Token Hub, LI.FI Diamond, Stargate, Across Protocol SpokePool) |

## Cấu trúc repo

```
cagi-ed/
├── src/            # Pipeline chính: collect → normalize → trajectories → features → models → evaluation
├── configs/        # Cấu hình model/feature/data (model.yaml, features.yaml, data.yaml)
├── metadata/       # incident_registry.csv, hard_negative_registry*.csv, protocol_map.yaml, split_manifest.json
├── data/           # Dataset đã xử lý (raw cache không commit — quá lớn)
├── results/        # tables/, figures/, reports/ — toàn bộ số liệu/hình/báo cáo đã freeze
├── tests/          # 197 test (pytest tests/ -v)
├── scripts/        # Script tái tạo/mining/đánh giá (reproduce_main.sh là điểm bắt đầu)
```

## Cách chạy / tái lập

```bash
pip install -r requirements.lock   # version chính xác đã dùng để tạo kết quả freeze
bash scripts/reproduce_main.sh     # tái tạo toàn bộ RQ1/RQ2/ablation/calibration — HOÀN TOÀN OFFLINE
python -m pytest tests/ -v         # xác nhận 197/197 test pass
```

**Không cần gọi API on-chain nào** để tái lập kết quả từ dữ liệu đã cache sẵn. Yêu cầu API key chỉ cần nếu muốn thu thập dữ liệu mới từ đầu — không cần cho việc tái lập số liệu đã công bố.

## Nguồn dữ liệu & đạo đức

Toàn bộ dữ liệu on-chain **công khai** (Ethereum/BSC/Arbitrum, qua Etherscan/BscScan API). Nhãn do nhóm **tự trace và tự gán**, đối chiếu báo cáo điều tra công khai (CertiK, SlowMist, Halborn...). **Không dùng ground truth AMLGuard** — dataset của họ chưa công khai tại thời điểm dự án bắt đầu (README AMLGuard ghi "release upon acceptance"); chỉ tham khảo seed list của họ (tên/chain/thời gian) làm gợi ý candidate ban đầu. Không deanonymize danh tính ngoài đời của bất kỳ ai.
