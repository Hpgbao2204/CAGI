# Điều tra: `bridge_context` gây hại cho M1 (phát hiện từ ablation 15-incident)

**Bối cảnh**: ablation trên 15 incident (Giai đoạn B, Bước 3) phát hiện loại
bỏ nhóm feature `bridge_context` khỏi M1 cải thiện PR-AUC có ý nghĩa thống
kê — khác hẳn E4 (no-temporal)/E5 (no-motif), CI luôn chứa 0. Báo cáo này
điều tra nguyên nhân và đề xuất quyết định feature set chính thức.

**✅ ĐÃ ÁP DỤNG (2026-08-28, xác nhận từ người dùng)**: M1 chính thức đã loại
bỏ 9 cột `bridge_context` (xem `src/models/baselines.py::BRIDGE_CONTEXT_COLS_EXCLUDED`,
tham số `include_bridge_context` để tái tạo hành vi cũ khi cần đối chiếu).
Đã rerun toàn bộ RQ1/RQ2/ablation trên M1 mới, xác nhận đối xứng hoàn hảo:
`M1_with_bridge_context` (thêm lại 9 cột) cho diff = **-0.0638**, 95% CI
**[-0.1501, -0.0101]** (loại trừ 0, p=0.036) — đúng độ lớn, ngược dấu so với
phát hiện gốc, và PR-AUC=0.6325 khớp chính xác `M1_full` CŨ trước khi sửa.
197/197 test PASS.

## Bước 1 — Xác nhận và định lượng

### 1a. Ablation trên 15 incident (xác nhận lại)

| Model | Mean PR-AUC | 95% CI | Diff vs M1_full | Paired 95% CI | Wilcoxon p |
|---|---|---|---|---|---|
| M1_full | 0.6325 | [0.4808, 0.8724] | 0 | — | — |
| M1_no_temporal | 0.6250 | [0.4747, 0.8770] | +0.0098 | [-0.0138, +0.0352] | 0.657 |
| M1_no_motif | 0.6499 | [0.5016, 0.8815] | +0.0502 | [-0.0125, +0.1410] | 0.445 |
| **M1_no_bridge_context** | **0.6624** | **[0.5234, 0.8864]** | **+0.0638** | **[+0.0101, +0.1501]** | **0.036** |

Xác nhận lại đúng con số đã báo cáo — chỉ `no_bridge_context` có CI loại
trừ 0.

### 1b. Câu hỏi quan trọng nhất: M1-không-bridge_context so với B3, RQ1 có đổi không?

| So sánh | Mean diff | 95% CI | Wilcoxon p | Kết luận |
|---|---|---|---|---|
| M1_full vs B3 (RQ1 gốc) | -0.0282 | [-0.1565, +0.0902] | — | KHÔNG ĐỦ BẰNG CHỨNG |
| **M1_no_bridge_context vs B3** | **+0.0355** | **[-0.0286, +0.1288]** | **0.638** | **VẪN KHÔNG ĐỦ BẰNG CHỨNG** |

**Trả lời**: KHÔNG, kết luận RQ1 KHÔNG đổi — CI vẫn chứa 0 dù điểm ước
lượng dịch chuyển đúng hướng M1 (~+0.064, khớp mức cải thiện đo được ở
Bước 1a). M1-không-bridge_context KHÔNG vượt B3 có ý nghĩa thống kê, nhưng
cũng không còn thua kém — về bản chất đưa M1 và B3 về mức "ngang nhau" hơn
so với trước.

## Bước 2 — Nguyên nhân: overfitting theo protocol cụ thể, được N khuếch đại

### 2a. Coverage từng feature con (15 incident positive)

| Feature | Coverage (nonzero) | Ghi chú |
|---|---|---|
| `time_to_first_bridge` | 14/15 | Cao, nhưng TRÙNG với nhóm temporal (xem lưu ý overlap) |
| `action_count_bridge_deposit_ratio` | 7/15 | Đúng bằng nhóm incident có bridge_deposit thật |
| `num_bridge_families` | 7/15 | Tương quan với dòng trên |
| `swap_after_bridge` | 3/15 | Thấp |
| `motif_bridge_then_swap` | 3/15 | Thấp, TRÙNG với nhóm motif |
| `motif_nested_bridge` | 2/15 | Rất thấp (sát ngưỡng lọc coverage=2) |
| `action_count_bridge_withdraw(_ratio)` | **0/15** | **Hằng số tuyệt đối — vô dụng hoàn toàn** |

`action_count_bridge_deposit` (bản thô) không phải feature của M1 (đã loại
theo quy tắc chung "loại cột thô, giữ bản `_ratio`").

### 2b. Bộ lọc `min_positive_incident_coverage=2` của M1 đã bắt được gì?

M1 vốn ĐÃ có bộ lọc coverage=2 (tính trên train fold, giống B2) — kiểm tra
qua từng fold LOGO xác nhận: bộ lọc CHỈ bắt được `action_count_bridge_withdraw_ratio`
(luôn bị loại) và `motif_nested_bridge` (bị loại ở 2 fold: khi held-out là
`chibi_finance_2023` hoặc `xkingdom_2024` — 2 incident DUY NHẤT có feature
này khác 0, nên loại 1 trong 2 khỏi train làm coverage tụt xuống 1).

**Ngưỡng coverage=2 KHÔNG bắt được** `swap_after_bridge`/`motif_bridge_then_swap`
(3/15, qua được ngưỡng) — đây chính là các cột vẫn lọt lưới dù coverage rất
thấp trên tập 15 incident (2/15 ≈ 13%, so với khi ngưỡng này được đặt ra ở
Tuần 5 lúc N còn nhỏ hơn nhiều, tỷ lệ coverage tối thiểu cao hơn đáng kể).

### 2c. SHAP contribution qua từng fold — bằng chứng trực tiếp overfitting theo protocol

Chỉ 2/9 cột bridge_context thực sự có đóng góp khác 0 trong cây
(`time_to_first_bridge`, `action_count_bridge_deposit_ratio`) — 5 cột còn
lại (`num_bridge_families`, `swap_after_bridge`, `motif_bridge_then_swap`,
`motif_nested_bridge`) có SHAP contribution **CHÍNH XÁC BẰNG 0** ở MỌI fold
— XGBoost gần như không bao giờ chọn các cột này để split (không đóng góp
trực tiếp, nhưng có thể ảnh hưởng gián tiếp qua thứ tự chọn split).

**Phát hiện chính**: SHAP của `time_to_first_bridge` trên CHÍNH dòng
positive của từng fold held-out:

| Held-out incident | SHAP (positive row) | Hướng |
|---|---|---|
| chibi_finance_2023 | +0.469 | ✅ Đúng hướng |
| deltaprime_arbitrum_2024 | +0.323 | ✅ Đúng hướng |
| utopiasphere_2024 | +0.347 | ✅ Đúng hướng |
| magic_abracadabra_arbitrum_2025 | +0.267 | ✅ Đúng hướng |
| radiant_capital_arbitrum_2024 | +0.127 | ✅ Đúng hướng |
| **9 incident còn lại** (bsc_token_hub, feg_bridge, hackerdao, new_free_dao, paraluni, qbridge, ronin, wault, xkingdom) | **-0.05 đến -0.15** | **❌ SAI HƯỚNG** |

**Kết luận rõ ràng**: `time_to_first_bridge` chỉ học ĐÚNG cho ĐÚNG 5 incident
Arbitrum có bridge_deposit thật (chibi, deltaprime, magic, radiant,
utopiasphere — toàn bộ đều dùng LI.FI/Stargate/Across) — với 9/15 incident
khác (chủ yếu BSC, dùng PancakeSwap/mixer TornadoProxyLight thay vì
bridge), feature này ĐẨY SAI HƯỚNG, làm giảm điểm của chính dòng positive
thật.

### 2d. Xác nhận hiệu ứng tăng theo N (đúng giả thuyết đã nêu)

| Thời điểm | N | Diff (no_bridge_context - full) | 95% CI | Có ý nghĩa? |
|---|---|---|---|---|
| Trước fix value_share | 11 | +0.0024 | [-0.0120, +0.0211] | Không |
| Trước mining radiant | 12 | +0.0068 | [-0.0083, +0.0274] | Không |
| Trước New Free Dao | 12 | +0.0064 | [-0.0258, +0.0500] | Không |
| **Sau Bước 3 (hiện tại)** | **15** | **+0.0638** | **[+0.0101, +0.1501]** | **CÓ** |

**Xác nhận đúng giả thuyết đã nêu**: hiệu ứng gần như KHÔNG tồn tại ở N=11-12
(diff nhỏ, CI luôn chứa 0 rộng) — chỉ trở nên LỚN và có ý nghĩa thống kê
sau khi thêm 3 incident mới với protocol đa dạng hơn hẳn (TornadoProxyLight
mixer ở hackerdao/new_free_dao, LI.FI/Stargate ở magic). Việc mở rộng N với
protocol families đa dạng hơn đã "phơi bày" một lỗi overfitting vốn đã tồn
tại tiềm ẩn nhưng không đủ mạnh để phát hiện ở N nhỏ.

## Bước 3 — Đề xuất quyết định feature set (CHỜ XÁC NHẬN, CHƯA áp dụng)

**Đề xuất: loại bỏ toàn bộ 9 cột `bridge_context` khỏi feature set chính
thức của M1** (không giữ một phần), vì:

1. Chỉ 2/9 cột có tác dụng thực sự trong cây, và CẢ HAI đều là nguồn gây
   hại đã xác nhận qua SHAP (Bước 2c) — không có tập con "an toàn" để giữ
   lại trong nhóm 2 cột active.
2. 5/9 cột còn lại chưa bao giờ được dùng (SHAP=0 ở mọi fold) — loại bỏ
   không mất thông tin gì, chỉ giảm nhiễu/rủi ro overfitting gián tiếp.
3. Loại bỏ CẢI THIỆN M1 có ý nghĩa thống kê (Bước 1a) và KHÔNG làm thay đổi
   kết luận RQ1 theo hướng bất lợi (Bước 1b — vẫn "không đủ bằng chứng",
   không "tệ hơn").
4. Bộ lọc coverage=2 hiện tại KHÔNG đủ để tự động loại các cột có hại này ở
   N=15 — cần loại thủ công theo domain knowledge, không chỉ dựa thống kê
   coverage đơn thuần.

**Lưu ý quan trọng về overlap** (đã ghi trong `ablation_e4_e5_v1.md` từ
trước): `time_to_first_bridge` cũng nằm trong nhóm `temporal`, và
`motif_bridge_then_swap`/`motif_nested_bridge` cũng nằm trong nhóm `motif`.
Loại bỏ TOÀN BỘ `bridge_context` sẽ ĐỒNG THỜI loại các cột này khỏi cả
nhóm temporal/motif — đây là hành vi ĐÚNG Ý ĐỊNH (các cột này được xác
nhận có hại CHÍNH XÁC vì bản chất "theo protocol cụ thể" của chúng, bất kể
được xếp vào nhóm nào), nhưng cần ghi rõ trong tài liệu paper để không gây
nhầm lẫn khi đọc lại E4 (no-temporal, CI chứa 0) — E4 xét TOÀN BỘ 5 cột
temporal cùng lúc nên hiệu ứng của riêng `time_to_first_bridge` bị pha
loãng bởi 4 cột temporal khác không có vấn đề.

**Việc này ẢNH HƯỞNG tới cách gọi "M1" trong toàn bộ phần còn lại — CẦN
XÁC NHẬN từ người dùng trước khi sửa bất kỳ file cấu hình/code chính thức
nào** (`src/models/baselines.py::M1TypedTemporalMotifModel`, tài liệu mô tả
"6 nhóm feature" trong `configs/features.yaml`/`configs/model.yaml`, và mọi
báo cáo RQ1/RQ2 đã freeze trước đó — sẽ cần rerun lại toàn bộ nếu áp dụng).

## Đóng góp tiềm năng cho paper (Bước 4)

> Counterintuitively, coarse protocol-specific bridge context features
> (e.g. time-to-first-bridge-touch) hurt cross-incident generalization on
> a small-N evaluation once incident diversity increases — the feature
> essentially memorizes "this specific bridge-family incident subgroup",
> boosting precision within that subgroup while actively misranking the
> majority of held-out incidents that route funds through structurally
> different channels (mixers, flat DEX swaps). Normalized structural/motif
> features that are NOT tied to one specific protocol family remain robust
> across the same expansion (E4/E5 ablations, CI containing 0 throughout).
> This suggests protocol-specific "context" features require either much
> larger N per protocol family or explicit protocol-family stratification
> before being safely included in a cross-incident detection model.
