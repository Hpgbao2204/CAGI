# Cross-review Log — CAGI-ED

## ⚠️ Giới hạn quan trọng — đọc trước khi dùng file này

Bước F trong quy trình gốc yêu cầu: **"Với nhóm 2 người: mỗi người review
lại incident do người kia thu thập (không tự review)."**

Phiên làm việc này được thực hiện **một mình** (người dùng + 1 agent AI hỗ
trợ pipeline), **không có người thứ 2 độc lập** để thực hiện review chéo
đúng nghĩa. Agent AI đã tự kiểm tra lại công việc của chính mình trong quá
trình làm (vd tự tìm ra và sửa 5 bug thật trong `builder.py`/
`incident_pipeline.py`, tự đối chiếu số liệu với báo cáo công khai) —
nhưng đây **không thay thế được** review độc lập bởi một người khác, vì:

- Cùng một người/agent có xu hướng lặp lại cùng loại sai lầm hoặc bỏ sót
  cùng loại giả định sai (không có góc nhìn khác để phát hiện).
- Không có ai xác nhận độc lập rằng cách diễn giải bằng chứng (vd chấp
  nhận bridge+mixer thay bridge+DEX cho FEG, chấp nhận provenance/evidence
  ngoài trajectory cho QBridge) là hợp lý — các quyết định này đã được
  **người dùng phê duyệt qua AskUserQuestion**, nhưng người dùng cũng là
  người duy nhất tham gia thu thập, không phải người "review lại" độc lập.

**Kết luận: `annotator_2` trong `incident_registry.csv` vẫn để trống cho
TẤT CẢ 10 incident.** Đây là điều kiện cần hoàn thành trước khi coi
dataset là "final" cho luận văn, đặc biệt nếu dataset được dùng để báo cáo
kết quả benchmark (RQ1-RQ4) — annotation không qua review chéo có rủi ro
thiên lệch (bias) cao hơn.

## Việc CÓ thể làm ngay khi có người thứ 2

Khi có 1 người khác tham gia (bạn cùng nhóm, giảng viên hướng dẫn, hoặc
reviewer khác), quy trình review chéo nên làm:

1. Người B đọc lại **từ đầu** `metadata/incident_registry.csv` (không xem
   trước `notes` do người A viết) và tự chạy
   `python scripts/run_incident_pipeline.py --incident-id <id> --no-collect`
   cho từng incident người A thu thập.
2. Người B tự đối chiếu source_url với dữ liệu on-chain đã cache trong
   `data/raw/` — xác nhận độc lập số liệu (tx hash, amount) khớp báo cáo
   công khai, không tin vào `notes` đã viết sẵn.
3. Người B đặc biệt kiểm tra các quyết định "chấp nhận evidence thay thế"
   (mục 5 trong `metadata/annotation_guide.md`) — đây là nơi dễ thiên lệch
   nhất (áp lực "cần đủ 6 incident" có thể khiến người thu thập tự nới
   lỏng chuẩn mà không nhận ra).
4. Ghi agreement/bất đồng vào bảng dưới đây, theo từng incident.
5. Nếu bất đồng, thảo luận và quyết định: giữ, sửa notes/confidence, hoặc
   loại khỏi registry — ghi rõ quyết định cuối và lý do.

## Bảng kết quả (điền khi có review chéo thật)

| incident_id | Người thu thập (annotator_1) | Người review (annotator_2) | Agreement | Ghi chú bất đồng |
|---|---|---|---|---|
| ronin_bridge_2022 | AI-assisted pipeline | _(chưa có)_ | — | — |
| ronin_benign_control_2022 | AI-assisted pipeline | _(chưa có)_ | — | — |
| qbridge_qubit_2022 | AI-assisted pipeline | _(chưa có)_ | — | — |
| feg_bridge_2024 | AI-assisted pipeline | _(chưa có)_ | — | — |
| deltaprime_arbitrum_2024 | AI-assisted pipeline | _(chưa có)_ | — | — |
| bsc_token_hub_2022 | AI-assisted pipeline | _(chưa có)_ | — | — |
| qbridge_benign_control_2022 | AI-assisted pipeline | _(chưa có)_ | — | — |
| feg_benign_control_2024 | AI-assisted pipeline | _(chưa có)_ | — | — |
| deltaprime_benign_control_2024 | AI-assisted pipeline | _(chưa có)_ | — | — |
| bsc_token_hub_benign_control_2022 | AI-assisted pipeline | _(chưa có)_ | — | — |

## Đề xuất ưu tiên review khi có người thứ 2

Xếp theo mức độ rủi ro thiên lệch, ưu tiên review trước:

1. **feg_bridge_2024** — chấp nhận bridge+mixer thay bridge+DEX (quyết
   định "nới lỏng" rõ ràng nhất, cần người khác xác nhận đây là hợp lý
   chứ không phải hạ chuẩn).
2. **qbridge_qubit_2022** — bridge/DEX evidence nằm ngoài outbound
   trajectory (pattern phức tạp nhất để hiểu đúng).
3. **bsc_token_hub_2022** và **deltaprime_arbitrum_2024** — evidence mạnh
   nhất (khớp số liệu chính xác), rủi ro thấp hơn nhưng vẫn nên xác nhận
   độc lập vì đây là 2 incident có confidence "high" trong dataset.
4. 5 hard-negative — rủi ro chọn nhầm địa chỉ vẫn liên quan tới incident
   (dù đã kiểm tra) là rủi ro lớn nhất với nhóm này.
