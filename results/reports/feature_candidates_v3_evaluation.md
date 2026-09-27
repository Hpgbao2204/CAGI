# Feature ứng viên v3 — đánh giá Giai đoạn A (Tuần 11, Bước 2-3)

**KHÔNG mining thêm dữ liệu** — dùng đúng 11 incident + hard-negative đã có (cùng tập trajectory sinh ra `features_v2.parquet`). **KHÔNG ảnh hưởng RQ1/RQ2 chính thức** (main_table.csv freeze v1.0 giữ nguyên, không ghi đè).

## Sanity check: tái tạo M1 chính thức (6 nhóm cũ)

Mean PR-AUC tái tạo = 0.7130 vs official = 0.7130 (|lệch|=0.000000) — ✅ KHỚP.

## Bảng tổng hợp (Mean PR-AUC, 95% CI, paired diff vs M1_v3_full)

| Model | Mean PR-AUC | 95% CI | Diff vs v3_full | Paired 95% CI | Wilcoxon p |
|---|---|---|---|---|---|
| M1_v2_official | 0.7130 | [0.5315, 0.8742] | -0.0041 | [-0.0187, +0.0096] | 0.6406 |
| M1_v3_full | 0.7117 | [0.5312, 0.8710] | — | — | — |
| M1_v3_no_cross_chain | 0.7117 | [0.5312, 0.8710] | +0.0000 | [+0.0000, +0.0000] | — |
| M1_v3_no_token_diversity_filtered | 0.7081 | [0.5319, 0.8681] | +0.0034 | [-0.0097, +0.0167] | 0.9414 |
| M1_v3_no_local_centrality | 0.7163 | [0.5340, 0.8746] | +0.0055 | [-0.0041, +0.0181] | 0.3984 |
| M1_v3_no_percentile | 0.7142 | [0.5278, 0.8765] | +0.0026 | [-0.0226, +0.0263] | 0.8125 |

**Cách đọc bảng ablation:** `M1_v3_no_{group}` càng TỆ HƠN (PR-AUC thấp hơn, diff âm rõ rệt, CI không chứa 0) so với `M1_v3_full` thì nhóm đó càng ĐÓNG GÓP THẬT. Nếu `M1_v3_no_{group}` gần bằng hoặc TỐT HƠN `M1_v3_full`, nhóm đó KHÔNG đóng góp (có thể chỉ thêm nhiễu).

## Coverage nhanh (nhóm feature mới, toàn bộ dataset)

- `cross_chain_distinct_count`: xuất hiện (>0) ở 11/11 incident positive
- `cross_chain_expansion_rate`: xuất hiện (>0) ở 0/11 incident positive
- `token_category_diversity_filtered`: xuất hiện (>0) ở 11/11 incident positive
- `token_value_entropy_filtered`: xuất hiện (>0) ở 7/11 incident positive
- `seed_betweenness_centrality`: xuất hiện (>0) ở 10/11 incident positive
- `seed_closeness_centrality`: xuất hiện (>0) ở 11/11 incident positive
- `mean_betweenness_centrality`: xuất hiện (>0) ở 10/11 incident positive
- `local_centrality_capped`: xuất hiện (>0) ở 0/11 incident positive

## Kết luận từng nhóm (Bước 3)

- **cross_chain**: DEAD — bo nhom nay cho ket qua GIONG HET (predictions byte-identical), khong dong gop gi.
- **token_diversity_filtered**: KHONG CO BANG CHUNG DONG GOP — bo nhom nay PR-AUC bang hoac TOT HON (diff=+0.0034, CI chua 0).
- **local_centrality**: KHONG CO BANG CHUNG DONG GOP — bo nhom nay PR-AUC bang hoac TOT HON (diff=+0.0055, CI chua 0).
- **percentile_normalized**: KHONG CO BANG CHUNG DONG GOP — bo nhom nay PR-AUC bang hoac TOT HON (diff=+0.0026, CI chua 0).

## Đề xuất (Bước 3 — KHÔNG tự ý sang Giai đoạn B)

**CẢ 4 NHÓM đều KHÔNG có bằng chứng đóng góp thật trên dataset hiện tại (11 incident)** — thậm chí `M1_v3_full` (0.7117) còn THẤP HƠN `M1_v2_official` (0.7130), dù không có ý nghĩa thống kê (CI 2 model chồng lấn nhiều). Khuyến nghị: **KHÔNG mang bất kỳ nhóm nào trong 4 nhóm này sang Giai đoạn B as-is**. Diễn giải riêng từng nhóm:

1. `cross_chain` — DEAD do giới hạn KIẾN TRÚC (mọi trajectory chỉ có 1 chain, xác nhận thực nghiệm đúng như dự đoán trong `features_v3_candidate.yaml`) — chỉ có thể sống lại nếu thay đổi cách thu thập dữ liệu (fetch chain đích của bridge event), NGOÀI PHẠM VI Giai đoạn A/B hiện tại.
2. `token_diversity_filtered` — không đóng góp đo được trên N=11, nhưng vẫn PHÁT HIỆN đúng 1 hạn chế/bug tiềm ẩn thật của `token_category_diversity` cũ (không lọc dust) — đáng sửa độc lập với quyết định carry-forward nhóm mới, khi dataset đủ lớn để dust thực sự gây nhiễu đo được.
3. `local_centrality` — CI paired sát ranh giới 0 (không loại trừ khả năng có tín hiệu thật bị che khuất bởi phương sai mẫu nhỏ, giống pattern đã thấy ở toàn bộ RQ1) — có thể đáng thử lại SAU KHI mở rộng dataset (Giai đoạn B), không kết luận dứt khoát "vô dụng" chỉ từ N=11.
4. `percentile_normalized` — tương tự, CI sát 0 nhưng nghiêng về hướng "bỏ đi tốt hơn" — không đủ bằng chứng ủng hộ.

**Không có nhóm nào đạt ngưỡng "bằng chứng đóng góp thật" (CI loại trừ 0 theo hướng có lợi)** — nhưng đây CŨNG là 1 phát hiện có giá trị: nhất quán với kết luận RQ1 (mẫu 11 incident hiện tại có phương sai lớn, khó phân biệt đóng góp feature dù typed hay flat) — gợi ý rằng vấn đề cốt lõi có thể là THIẾU DỮ LIỆU hơn là thiếu loại feature, cần cân nhắc khi quyết định trọng tâm Giai đoạn B.

**KHÔNG tự ý chuyển sang Giai đoạn B** — báo cáo này chờ quyết định người dùng.
