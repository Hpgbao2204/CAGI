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
        2                   19.9740               19.891253               23.63564      9.987000                       0.155755     353.730560    353.755136              15
        5                   18.2757               18.102573               19.77855      3.655140                       0.148789     353.787904    353.787904              15
        9                   18.6645               18.265220               19.09695      2.073833                       0.147271     353.787904    353.787904              15
       25                   18.7713               18.432127               19.26349      0.750852                       0.145996     353.787904    353.787904              15
       52                   19.2880               18.845573               19.93763      0.370923                       0.145472     353.787904    353.787904              15
      108                   20.2120               20.040900               22.12095      0.187148                       0.145251     353.787904    353.787904              15
      253                   22.8684               22.576300               25.24405      0.090389                       0.145183     353.787904    353.787904              15
      485                   29.7895               29.227987               30.75515      0.061422                       0.146680     353.787904    353.812480              15

## Kiểm tra tăng gần tuyến tính (H4) — diễn giải thủ công (số hồi quy tự động dễ gây hiểu lầm, xem lý do dưới)

Hệ số góc hồi quy log(latency) ~ log(n_events) = **0.062** — con số này KHÔNG có nghĩa "không tuyến tính rõ theo hướng xấu"; nó phản ánh đúng thực tế quan sát được: **latency gần như PHẲNG (dưới tuyến tính), không tăng mạnh theo độ dài** trong khoảng đã đo (2→485 event, tăng 242 lần): 20.0ms → 29.8ms (chỉ tăng ~1.49 lần). Nguyên nhân: mỗi lần gọi có **overhead cố định** (chủ yếu từ dựng `DataFrame` 1 dòng + gọi XGBoost booster) không phụ thuộc số event — phần tăng thêm theo độ dài (từ `extract_features` duyệt qua các action) chỉ đóng góp một phần nhỏ, chỉ rõ rệt khi trajectory khá dài.

**ms/event giảm dần theo độ dài là HỆ QUẢ TRỰC TIẾP** của overhead cố định chia cho số event tăng dần — không phải "biến động bất thường", mà cho thấy **throughput/event CẢI THIỆN** khi trajectory dài hơn (chi phí cố định được khấu hao trên nhiều event hơn).

**Kết luận cho H4:** đạt tinh thần giả thuyết (latency KHÔNG bùng nổ theo độ dài trong quy mô proof-of-concept, tổng latency luôn <31ms/trajectory kể cả ở kích thước lớn nhất đã đo) — thực tế còn tốt hơn "tuyến tính" (sub-linear/gần phẳng), nên diễn giải là "H4 được ủng hộ, với đặc điểm cụ thể: chi phí cố định/lần gọi chiếm ưu thế ở quy mô hiện tại" thay vì chỉ nói "gần tuyến tính".

**RAM:** `peak_ram_delta_mb_tracemalloc` giữ phẳng quanh 0.145–0.156MB bất kể độ dài — không đo được xu hướng tăng RAM theo độ dài trong khoảng đã test (dự đoán trên 1 trajectory tại 1 thời điểm, không phải batch lớn) — phù hợp "không cần GPU, chi phí bộ nhớ không đáng kể ở quy mô này".

**Không cần GPU** — toàn bộ benchmark chạy CPU-only (XGBoost CPU backend).

**Lưu ý về `total_ram_gb=7.78`** trong bảng hardware phía trên: đây là RAM mà `psutil` báo cáo trong MÔI TRƯỜNG CHẠY THẬT (có thể là VM/container giới hạn tài nguyên, không nhất thiết là RAM vật lý đầy đủ của máy host) — ghi nguyên trạng, không suy đoán thêm.
