# Figure 1 — Kiến trúc CAGI-ED (đặc tả để vẽ bằng draw.io)

Xuất ra `paper/figures/fig1_architecture.pdf` (File → Export as → PDF, tick
"Crop"), khổ ngang, rộng ~17 cm (full text width LNCS 12.2 cm sẽ được scale).
Paper tự chèn file này ở Sect. 4 (`\includegraphics{figures/fig1_architecture.pdf}`).

## Bố cục tổng thể

Một dải ngang, đọc trái → phải, chia **4 layer** bằng 4 khung bo góc nền nhạt
(mỗi layer 1 màu nền rất nhạt, viền xám 1 pt, nhãn layer ở góc trên-trái in
đậm):

```
 ┌─(L1) Multi-chain collection─┐ ┌─(L2) Semantic decoding─┐ ┌─(L3) Value-flow trajectory─┐ ┌─(L4) Online early-warning scorer─┐
 │  3 chain + API + cache      │→│  protocol map + merge  │→│  đồ thị tainted, prefix τ1:k│→│  x(τ1:k) → f → Platt → alert      │
 └─────────────────────────────┘ └────────────────────────┘ └────────────────────────────┘ └───────────────────────────────────┘
                     ▲                                                                                         │
                     └──────────────── feedback: frontier {v_a} \ P (địa chỉ mới cần fetch) ───────────────────┘ (mũi tên nét đứt phía dưới, từ L3 quay về L1)
                                                                   dưới cùng: dải timeline prefix + endpoint (xem mục L5)
```

Màu gợi ý (nhẹ, in đen trắng vẫn đọc được): L1 xanh dương nhạt `#e8f0fb`,
L2 xanh lá nhạt `#e6f5ee`, L3 cam nhạt `#fdeee6`, L4 tím nhạt `#eeebf8`. Chữ
đen/xám đậm. Mũi tên chính 1.5 pt đen; mũi tên phản hồi nét đứt xám.

---

## L1 — Multi-chain collection (khung trái)

**Thực thể (node) vẽ bên trong:**

1. **3 biểu tượng chain** xếp dọc, mỗi cái là 1 hình trụ nhỏ (shape
   "Cylinder") có nhãn: `Ethereum (1)`, `BSC (56)`, `Arbitrum (42161)`.
   Bên cạnh mỗi trụ vẽ 3–4 **ô block nhỏ nối chuỗi** (hình chữ nhật nhỏ nối
   bằng đoạn thẳng) để gợi ý blockchain.
2. **2 node API** (shape "Process"/hình chữ nhật có 2 vạch dọc):
   * `Etherscan V2` — nối từ trụ Ethereum và Arbitrum; ghi nhỏ:
     `txlist · txlistinternal · tokentx`
   * `NodeReal nr_getAssetTransfers` — nối từ trụ BSC; ghi nhỏ: `in / out, paged`
3. **Evidence cache** (shape "Database"): nhãn `Evidence cache`, dòng phụ:
   `key = (chain, address, incident)`, `SHA-256 + request time`.
4. Ô công thức nhỏ dưới cùng khung L1:
   `window = [b₀, b₀ + 72 h]`

**Cạnh:** chain → API (mũi tên mảnh), API → cache (mũi tên đậm), cache →
sang L2 (mũi tên chính).

---

## L2 — Semantic decoding (khung thứ 2)

**Thực thể:**

1. **Protocol map P** (shape "Document" hoặc bảng nhỏ 4 hàng):
   ```
   bridges  (9 contracts, 8 families)
   DEX      (6 routers/pools)
   mixers   (2)
   lending  (1)
   ```
   ghi nhỏ bên dưới: `verified on-chain (selector / event sig)`.
2. **Decoder** (hình chữ nhật): `raw leg → canonical action a`.
3. **Merge rule** (hình thoi "Decision" hoặc 3 ô nhỏ xếp dọc), mỗi ô là 1
   luật gộp các leg cùng tx:
   * `≥2 tokens in/out same addr → swap`
   * `1 src → ≥2 dst → split`
   * `≥2 src → 1 dst → merge`
4. **Canonical action** — ghi công thức ở ô nổi bật:
   `a = (t, c, u, v, y, κ, q, π)` với `q = log(1 + amount)`
5. **Type vocabulary Y** — vẽ **10 viên thuốc màu (pill) nhỏ**, mỗi viên 1
   kiểu, dùng lại màu này ở L3 để tô cạnh:
   `transfer` (xám), `swap` (xanh dương), `bridge_dep` (cam), `bridge_wdr`
   (cam nhạt), `lend_dep` (vàng), `lend_wdr` (vàng nhạt), `split` (xanh lá),
   `merge` (xanh lá nhạt), `mixer/exit` (đỏ), `other` (trắng viền xám).

**Cạnh:** cache → decoder; protocol map → decoder (mũi tên từ trên xuống);
decoder → merge → "typed actions" → sang L3.

---

## L3 — Bounded value-flow trajectory (khung thứ 3, phần "mạng" chính)

Đây là phần nên vẽ như **một đồ thị thật**:

1. **Đồ thị có hướng ~10 node**:
   * Node **seed s** (hình tròn đậm, viền đỏ, nhãn `s (seed, d=0)`).
   * 2–3 node **ví trung gian** tầng 1 (tròn trắng, nhãn `d=1`).
   * 3–4 node tầng 2 (`d=2`).
   * Node **hạ tầng** (hình lục giác, nền xám): `DEX router`, `Bridge`,
     `Mixer` — thuộc P, **không mở rộng qua** (vẽ viền kép hoặc icon ổ khoá).
   * Cạnh tô màu theo kiểu hành động (dùng màu pill ở L2): s→v1 `transfer`,
     v1→DEX `swap`, v1→v2a,v2b,v2c `split` (3 cạnh xanh lá tỏa ra), v2b→Bridge
     `bridge_dep` (cam, **đậm**), v2c→Mixer `mixer/exit` (đỏ).
   * 1–2 cạnh **nét đứt xám mảnh** đi ra khỏi đồ thị có nhãn `share < η`
     (bị loại vì giá trị nhỏ).
2. **Hộp luật chấp nhận** (ô công thức, đặt góc trên phải khung L3):
   ```
   accept a  ⇔  d(u_a) < D  ∧  t_a − t₁ ≤ H
                ∧ [ ρ(a) / O(u_a, κ_a) ≥ η   ∨   {u_a, v_a} ∩ P ≠ ∅ ]
   d(v_a) ← min(d(v_a), d(u_a) + 1)   (v_a ∉ P)
   η = 5%,  H = 72 h,  2 expansion rounds
   ```
   (ρ(a) = e^q − 1 là giá trị thô; O(u, κ) là tổng outflow của u theo token κ)
3. **Mũi tên phản hồi** (nét đứt, từ đồ thị L3 vòng xuống dưới quay về L1):
   nhãn `new frontier {v_a} \ P → fetch`.

---

## L4 — Online early-warning scorer (khung phải)

Vẽ như 1 **pipeline dọc** các khối, mỗi khối có công thức:

1. **Prefix τ₁:ₖ** — một hàng 6–8 ô vuông nhỏ (mỗi ô 1 action, tô màu theo
   kiểu), 3–4 ô đầu tô đậm, phần còn lại mờ; ngoặc nhọn bên dưới ô đậm ghi
   `observed prefix τ₁:ₖ (a₁..a_k only)`. Mũi tên nhỏ `k ← k+1 on each new action`.
2. **Feature extractor** — 3 ô nhỏ song song (3 nhóm feature):
   * `Flat (14)`: gaps, burstiness `B = (σ−μ)/(σ+μ)`, fan-in/out, depth, value retention
   * `Typed actions (16)`: type shares, bigrams/trigrams, bridge families
   * `Motifs (7)`: split, merge, peel chain, bridge→swap, nested bridge, token pivot
   gộp lại thành vector `x(τ₁:ₖ) ∈ ℝ³⁷`.
3. **Scorer f** — icon 3 cây nhỏ (gradient-boosted trees), nhãn
   `XGBoost (200 × depth 4)`.
4. **Calibration** — ô công thức:
   `p̂ₖ = σ(α · logit f(x) + β)`   (Platt, fitted on training incidents only)
5. **Decision** — hình thoi: `p̂ₖ ≥ θ ?` → nhánh **yes** tới
   6. **Alert card** (hình chữ nhật viền đỏ, như 1 tấm thẻ):
      ```
      ALERT  incident seed s, step k, p̂ = 0.xx
      top TreeSHAP:  φ₁ swap share +…, φ₂ path depth +…, φ₃ …
      AADAPT: ADT3028.003 Layering, ADT3005 Hopping
      ```
      và nhánh **no** quay lại "wait for next action".
   Ghi nhỏ cạnh TreeSHAP: `logit f(x) = φ₀ + Σⱼ φⱼ(x)`.

---

## L5 — Dải timeline (dưới cùng, trải hết chiều ngang, tuỳ chọn nhưng nên có)

Trục thời gian `t` với các chấm action a₁…aₙ; đánh dấu:
* vạch cam nét đứt `first alert t_a (k_a)`,
* vạch đỏ gạch-chấm `endpoint t_e (first bridge/mixer/lending deposit)`,
* mũi tên hai đầu giữa chúng: `lead time = t_e − t_a`, `lead steps = e* − k_a`.

Dải này thay cho hình "prefix" cũ và cho người đọc thấy ngay ý chính của
paper: **cảnh báo trong lúc tiền còn đang chạy, trước điểm thoát**.

---

## Lưu ý trình bày

* Font sans (Helvetica/Arial) 8–9 pt khi scale về 12 cm; công thức dùng
  Math typesetting của draw.io (Extras → Mathematical Typesetting) để ra
  LaTeX thật: ví dụ `$\hat p_k=\sigma(\alpha\,\mathrm{logit} f(\mathbf x)+\beta)$`.
* Nhất quán ký hiệu với paper: s, a, τ₁:ₖ, x(τ₁:ₖ), f, p̂ₖ, θ, η, H, P, e*, t_a, t_e.
* Không đặt con số kết quả (PR-AUC…) trong hình kiến trúc.
