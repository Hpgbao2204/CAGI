# Efficiency benchmark — M1 (Tuần 9, Bước 6, bằng chứng RQ4)

**CHỈ đo model processing latency** (extract_features + predict_proba) — KHÔNG đo data-availability delay (thời gian chờ API) hay alert lead time (RQ2). Không đồng nhất với "near real-time <60s" — 2 khái niệm khác nhau (đúng ràng buộc `research_questions.md` mục RQ4).

Đo sau 20 lần warm-up, 15 lần đo/bucket độ dài, dùng trajectory THẬT từ dataset (không tổng hợp giả định).

## Hardware / môi trường

```
platform: Windows-11-10.0.26200-SP0
processor: AMD64 Family 25 Model 68 Stepping 1, AuthenticAMD
python_version: 3.13.0
cpu_count_logical: 16
cpu_count_physical: 8
total_ram_gb: 7.781593088
sklearn_version: 1.9.0
xgboost_version: 3.4.0
process_count: 1
```

## Kết quả theo số event/trajectory

 n_events  median_ms_per_trajectory  mean_ms_per_trajectory  p95_ms_per_trajectory  ms_per_event  peak_ram_delta_mb_tracemalloc  rss_mb_before  rss_mb_after  n_measurements
        2                   16.6157               16.647420               18.65058      8.307850                       0.153684     418.226176    418.250752              15
        5                   19.7225               19.605433               22.66822      3.944500                       0.147830     418.283520    418.283520              15
       10                   18.2968               18.325060               20.56976      1.829680                       0.145799     418.283520    418.283520              15
       24                   19.0996               18.672027               20.56702      0.795817                       0.144530     418.283520    418.283520              15
       46                   18.8960               19.552633               24.35543      0.410783                       0.145921     418.283520    418.283520              15
      102                   18.8930               19.030380               21.75075      0.185225                       0.145293     418.283520    418.283520              15
      248                   20.9787               20.437100               21.95939      0.084592                       0.146034     418.283520    418.283520              15
      496                   29.0007               28.617993               30.12170      0.058469                       0.144730     418.283520    418.283520              15

## Kiểm tra tăng gần tuyến tính (H4) — diễn giải thủ công (số hồi quy tự động dễ gây hiểu lầm, xem lý do dưới)

Hệ số góc hồi quy log(latency) ~ log(n_events) = **0.066** — con số này KHÔNG có nghĩa "không tuyến tính rõ theo hướng xấu"; nó phản ánh đúng thực tế quan sát được: **latency gần như PHẲNG (dưới tuyến tính), không tăng mạnh theo độ dài** trong khoảng đã đo (2→496 event, tăng 248 lần): 16.6ms → 29.0ms (chỉ tăng ~1.75 lần). Nguyên nhân: mỗi lần gọi có **overhead cố định** (chủ yếu từ dựng `DataFrame` 1 dòng + gọi XGBoost booster) không phụ thuộc số event — phần tăng thêm theo độ dài (từ `extract_features` duyệt qua các action) chỉ đóng góp một phần nhỏ, chỉ rõ rệt khi trajectory khá dài.

**ms/event giảm dần theo độ dài là HỆ QUẢ TRỰC TIẾP** của overhead cố định chia cho số event tăng dần — không phải "biến động bất thường", mà cho thấy **throughput/event CẢI THIỆN** khi trajectory dài hơn (chi phí cố định được khấu hao trên nhiều event hơn).

**Kết luận cho H4:** đạt tinh thần giả thuyết (latency KHÔNG bùng nổ theo độ dài trong quy mô proof-of-concept, tổng latency luôn <30ms/trajectory kể cả ở kích thước lớn nhất đã đo) — thực tế còn tốt hơn "tuyến tính" (sub-linear/gần phẳng), nên diễn giải là "H4 được ủng hộ, với đặc điểm cụ thể: chi phí cố định/lần gọi chiếm ưu thế ở quy mô hiện tại" thay vì chỉ nói "gần tuyến tính".

**RAM:** `peak_ram_delta_mb_tracemalloc` giữ phẳng quanh 0.145–0.154MB bất kể độ dài — không đo được xu hướng tăng RAM theo độ dài trong khoảng đã test (dự đoán trên 1 trajectory tại 1 thời điểm, không phải batch lớn) — phù hợp "không cần GPU, chi phí bộ nhớ không đáng kể ở quy mô này".

**Không cần GPU** — toàn bộ benchmark chạy CPU-only (XGBoost CPU backend).

**Lưu ý về `total_ram_gb=7.78`** trong bảng hardware phía trên: đây là RAM mà `psutil` báo cáo trong MÔI TRƯỜNG CHẠY THẬT (có thể là VM/container giới hạn tài nguyên, không nhất thiết là RAM vật lý đầy đủ của máy host) — ghi nguyên trạng, không suy đoán thêm.

## So sánh với N=11 (2026-08-19, TRƯỚC khi loại bridge_context)

Cùng hardware/môi trường (platform, CPU, RAM đều khớp — không đổi máy).
Bucket độ dài tự động chọn theo trajectory GẦN NHẤT với mốc mục tiêu
(2/5/10/25/50/100/250/500) trong dữ liệu hiện có — dataset đổi (N=15) nên
độ dài trajectory sẵn có cũng đổi nhẹ, không lệch mốc mục tiêu đáng kể:

| Mốc mục tiêu | n_events N=11 (cũ) | median ms N=11 | n_events N=15 (mới) | median ms N=15 |
|---|---|---|---|---|
| ~2 | 2 | 19.974 | 2 | 16.616 |
| ~5 | 5 | 18.276 | 5 | 19.722 |
| ~10 | 9 | 18.664 | 10 | 18.297 |
| ~25 | 25 | 18.771 | 24 | 19.100 |
| ~50 | 52 | 19.288 | 46 | 18.896 |
| ~100 | 108 | 20.212 | 102 | 18.893 |
| ~250 | 253 | 22.868 | 248 | 20.979 |
| ~500 | 485 | 29.790 | 496 | 29.001 |

**Kết luận KHÔNG đổi**: latency vẫn phẳng/sub-linear theo độ dài (chênh
lệch giữa 2 lần đo ở cùng mốc chỉ trong khoảng nhiễu đo đạc bình thường,
±2-3ms), tổng latency vẫn <30ms/trajectory ở mốc lớn nhất. M1 sau khi loại
9 cột `bridge_context` dùng **29 feature** (so với nhiều hơn ở bản cũ) —
việc giảm số cột KHÔNG tạo khác biệt latency đáng kể (chi phí chủ yếu là
overhead cố định dựng DataFrame/gọi XGBoost booster, không phải số cột).
RAM vẫn phẳng quanh 0.145-0.154MB, không đổi so với N=11 (0.145-0.156MB).
Bản N=11 gốc giữ nguyên tại
`results/reports/runtime_v1_N11_PRE_N15FREEZE_backup.md`.
