# Figure 1 — Kiến trúc CAGI-ED: hướng dẫn vẽ bằng draw.io

Phong cách: giống `pipeline.pdf` tham khảo — nền trắng, ít chữ, mỗi giai đoạn
là **1 khung nhỏ có hình minh hoạ cụ thể** (cylinder, dải tx, đồ thị chữ cái,
bảng xếp hạng), **1 hộp công thức trung tâm**, bố cục **2 hàng**, mũi tên xanh
lá nối hàng trên xuống hàng dưới, chú thích thời gian ở chân mỗi giai đoạn.
**Mọi hình đều có sẵn trong draw.io** (không dùng logo chain, không cần ảnh ngoài).

Xuất: File → Export as → PDF, tick *Crop* → `paper/figures/fig1_architecture.pdf`.

---

## 0. Thiết lập chung

| Mục | Giá trị |
|---|---|
| Canvas | ~1040 × 820 px, Grid 10 px |
| Font | Helvetica; tiêu đề khối 13 pt **đậm**, chữ thường 11 pt, chú thích 10 pt |
| Công thức | *Extras → Mathematical Typesetting* bật, gõ `$...$` trong text |
| Viền | 1 px, bo góc 8 (`rounded=1;arcSize=6`) |

Bảng màu (dùng lại đúng các mã này):

| Vai trò | Fill | Stroke |
|---|---|---|
| Khung giai đoạn (nền xanh nhạt) | `#EEF3FA` | `#C9D6E8` |
| Node thường / cylinder | `#C6DBF0` | `#5B84B1` |
| Node xanh lá (đường đi được chọn) | `#A9D18E` | `#4E8F2F` |
| Node cam (bridge) | `#F4B183` | `#C55A11` |
| Node tím (mixer) | `#D9C3E9` | `#7E57A6` |
| Seed / endpoint (đỏ) | `#FFFFFF` | `#C00000` (viền 2 px) |
| Mũi tên chính | — | `#000000` 1.5 px |
| Mũi tên "được chọn" | — | `#4E8F2F` 2 px |
| Ngưỡng θ | — | `#C00000` nét đứt |

Lấy hình ở đâu: gõ **từ khoá** vào ô *Search Shapes* (góc trên thanh Shapes
bên trái) — cách này luôn ra, không phụ thuộc thư viện nào đang bật:

| Hình | Từ khoá tìm | Thư viện thường gặp |
|---|---|---|
| Hình chữ nhật / bo góc / ellipse | `rectangle`, `rounded`, `ellipse` | General |
| Cylinder (cache, chain) | `cylinder` | General |
| Hexagon (bridge, mixer) | `hexagon` | General |
| Document (icon báo cáo) | `document` | General |
| Note | `note` | General |
| Ngoặc nhọn `{` | `curly bracket` (hoặc Edit Style: `shape=curlyBracket;rounded=1;labelPosition=left;`) | Advanced / General |
| Công tắc | `switch` (chọn "Switch" 2 chân) | Electrical → Electro-Mechanical |
| Bảng xếp hạng | *Arrange → Insert → Table* (2 cột × 8 hàng) | có sẵn |
| Mũi tên hai đầu | vẽ 1 đường thẳng, Format → *Line start* và *Line end* = mũi tên | có sẵn |
| Vạch phân cách dọc | đường thẳng `#BFBFBF`, *Pattern: dashed* | có sẵn |

---

## 1. Bố cục tổng

```
┌──────────────── HÀNG 1: ONLINE SCORING (mỗi action mới) ───────────────────────────────────────┐
│  (A) Seed & collection  ┆  (B) 3 khung xếp dọc      ──►  (C) hộp công thức  ──►  (D) bảng cảnh báo │
│  dải tx + 3 cylinder    ┆  Typed actions / Value-flow                             xếp theo p̂, vạch θ│
│  + evidence cache       ┆  trajectory / Prefix features                                        │
│ ◄── Collection: s/address ──►◄──────────── Scoring: 12–24 ms per action ─────────────────────────►│
└─────────────────────────────────────────────────────────────────────────────────┬───────────────┘
                                                        mũi tên xanh lá (hàng vượt ngưỡng)       │
┌──────────────── HÀNG 2: EARLY WARNING ───────────────────────────────────────────▼──────────────┐
│  (E) Timeline prefix + lead time   ┆   (F) TreeSHAP + AADAPT    ──►  (G) Alert report + policy   │
│ ◄──────── Lead time: t_e − t_a ────────►◄──────────────── Human review ────────────────────────►│
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

Hai hàng cách nhau bởi khoảng trắng; giữa (A) và (B), giữa (E) và (F) có 1
vạch phân cách dọc nét đứt xám (giống tham khảo).

---

## 2. Hàng 1 — Online scoring

### (A) Seed & collection (x ≈ 20–290)

1. Tiêu đề (text đậm, 2 dòng, căn trái): **Incident report → seed $s$**
2. **Dải giao dịch** (5 hình chữ nhật dính nhau, cao 30, fill `#C6DBF0`):
   `tx₁` | `…` | `tx_{k}` | `|` | ô cuối **đậm** fill `#1F3B5C`, chữ trắng `new`
   (giống dải `tx0 … T` của tham khảo; ô cuối = action mới vừa tới).
3. Mũi tên xuống → **3 Cylinder nhỏ** đặt ngang hàng (40×40), nhãn dưới:
   `ETH`, `BSC`, `ARB`. Một text nhỏ phía trên: `Etherscan V2 · NodeReal`.
4. Mũi tên từ 3 cylinder gộp xuống 1 **Cylinder lớn** (120×70), chữ **đậm**
   hai dòng: **evidence cache**; dưới cylinder chú thích 10 pt:
   `(chain, address, incident) · SHA-256`.
5. Vòng phản hồi: mũi tên **nét đứt** từ khung (B) quay về cylinder lớn, nhãn
   nghiêng `new frontier → fetch`.

### (B) Ba khung xếp dọc (x ≈ 310–560) — mỗi khung Rounded Rectangle fill `#EEF3FA`

**B1. Typed actions** (cao ~110)
- Tiêu đề đậm: **Typed actions**
- Một hàng 4 "viên" Rounded Rectangle nhỏ (48×20), chữ 9 pt:
  `transfer` (fill `#D9D9D9`) · `swap` (`#C6DBF0`) · `bridge` (`#F4B183`) · `mixer` (`#D9C3E9`)
- Dòng chú thích 10 pt: `verified protocol map · merge legs of one tx`

**B2. Value-flow trajectory** (cao ~130) — *giống ô "Token-flow graph" tham khảo*
- Tiêu đề đậm: **Value-flow trajectory**
- Đồ thị 5 node (Ellipse 30×30, chữ 11 pt đậm):
  - `s` : fill trắng, viền đỏ 2 px (seed)
  - `A` : fill `#A9D18E` (xanh lá)
  - `B` : fill `#C6DBF0`
  - `C` : **Hexagon** fill `#F4B183`, nhãn `bridge`
  - `D` : **Hexagon** fill `#D9C3E9`, nhãn `mixer`
- Cạnh: `s → A` (xanh lá đậm), `A → B`, `A → C` (xanh lá đậm), `B → D`;
  thêm 1 cạnh nét đứt xám từ `B` ra 1 chấm tròn rỗng nhỏ, nhãn `share < η`.
- Chú thích 10 pt dưới: `$\rho(a)/O(u_a,\kappa_a)\ge\eta$, 2 hops, 72 h`

**B3. Prefix features** (cao ~110)
- Tiêu đề đậm: **Prefix features $\mathbf{x}(\tau_{1:k})$**
- Một **Curly Bracket** nằm ngang ôm 4 ô vuông nhỏ (màu như B1) + 3 ô xám nhạt
  (phần tương lai, *Opacity 40%*), nhãn dưới ngoặc: `$a_1..a_k$ only`
- 3 dòng text 10 pt (font mono như tham khảo, *Courier New*):
  ```
  flat(14)   gaps · fan-out · amount
  typed(16)  type shares · bigrams
  motif(7)   split · peel · bridge→swap
  ```

### (C) Hộp công thức (x ≈ 590–740) — *giống hộp σ(...) tham khảo*

- Rounded Rectangle trắng, viền đen 1.5 px, ~150×80.
- Nội dung (LaTeX): `$\hat p_k=\sigma\!\big(\alpha\,\mathrm{logit}\,f(\mathbf{x}(\tau_{1:k}))+\beta\big)$`
- Dưới hộp, text 10 pt: `XGBoost $f$ + Platt ($\alpha,\beta$ from training incidents)`
- 3 mũi tên đen từ B1, B2, B3 hội tụ vào cạnh trái hộp (như tham khảo).

### (D) Bảng cảnh báo (x ≈ 770–880) — *giống bảng "candidates" tham khảo*

- Tiêu đề đậm phía trên: **monitored flows**
- Table 2 cột (cột 1 rộng 70: tên flow; cột 2 rộng 45: điểm), 8 hàng:
  ```
  chibi·k=2    0.62
  flow-17      0.58
  flow-03      0.51
  ----------- θ -------   ← đường nét đứt đỏ vắt ngang giữa hàng 3 và 4, nhãn đỏ bên phải: θ
  flow-11      0.31
  flow-08      0.12
  flow-22      0.05
  ⋮
  ```
  3 hàng trên fill `#D5E8D4` (xanh lá nhạt, vượt ngưỡng).
- Mũi tên từ hộp (C) → bảng.
- **Mũi tên xanh lá** (2 px, bo góc) đi từ hàng 1 của bảng, sang phải, vòng
  xuống dưới, chạy ngang sang trái, rồi đi xuống vào khung (E) của hàng 2
  (giống đường xanh lá của tham khảo).

### Chú thích thời gian hàng 1 (dưới cùng hàng 1)
Hai mũi tên hai đầu xám mảnh, chữ 10 pt ở giữa:
- dưới (A): `Collection: seconds per address`
- dưới (B)–(D): `Scoring: 12–24 ms per action (CPU)`

---

## 3. Hàng 2 — Early warning

### (E) Timeline & lead time (x ≈ 20–420)

- Tiêu đề đậm: **Prefix replay**
- Dải action (giống dải tx hàng 1), 9 ô:
  `a₁` `a₂` `…` `a_{k_a}` `…` `a_{e*}` `…` `a_n`
  - ô `a_{k_a}` fill `#A9D18E` (xanh lá — điểm cảnh báo đầu tiên),
  - ô `a_{e*}` viền đỏ 2 px, fill `#F8CBAD` (endpoint: bridge/mixer/lending deposit).
- Phía trên dải: 1 **Switch (SPST)** nhỏ (Electrical) + text `$\hat p_k\ge\theta$`
  đặt ngay trên ô `a_{k_a}` (giống "value switch" của tham khảo).
- Dưới dải: 1 mũi tên hai đầu từ `a_{k_a}` tới `a_{e*}`, nhãn
  `lead time $t_e-t_a$  ·  lead steps $e^\star-k_a$`.
- Chú thích đỏ 10 pt dưới ô endpoint: `exit: bridge / mixer / lending`.

### (F) Explanation (x ≈ 440–690)

- Tiêu đề đậm: **TreeSHAP evidence**
- 3 thanh ngang (Rectangle cao 12, fill `#5B84B1`) độ dài giảm dần, nhãn bên
  trái 10 pt: `amount`, `fan-out`, `swap share`; trục mảnh phía dưới.
- Text 10 pt dưới: `$\mathrm{logit} f(\mathbf{x})=\phi_0+\sum_j\phi_j$`
- 1 ô Note nhỏ: `AADAPT: ADT3028.003 Layering`

### (G) Alert report + policy (x ≈ 710–1020) — *giống "Triage report" + "Builder policy"*

- Tiêu đề đậm: **Alert report** + icon **Document** nhỏ bên trái.
- Rectangle trắng, font mono 10 pt:
  ```
  {"seed": "0x80c1…",
   "step": 2, "p": 0.62,
   "top": ["amount", "fan-out", "swap"],
   "aadapt": ["ADT3028.003"]}
  ```
- Mũi tên từ (F) → (G) (qua 1 **Ellipse** nhỏ chữ `Ω`/hoặc `⊕` nếu muốn giống
  tham khảo, không bắt buộc).
- Dưới: tiêu đề đậm **Analyst policy** + icon Document; khung 3 dòng màu:
  - **`p̂ ≥ θ`** (xanh lá `#2E7D32`) `→ notify analyst`
  - **`θ' ≤ p̂ < θ`** (xanh dương `#1F5FAD`) `→ keep monitoring`
  - **`p̂ < θ'`** (đỏ sẫm `#A50021`) `→ no action`

### Chú thích thời gian hàng 2
- dưới (E): `Lead time: minutes before exit`
- dưới (F)–(G): `Human review`

---

## 4. Checklist trước khi xuất

- [ ] Ký hiệu khớp paper: $s$, $a_k$, $\tau_{1:k}$, $\mathbf{x}(\tau_{1:k})$, $f$, $\hat p_k$, $\theta$, $\eta$, $e^\star$, $t_a$, $t_e$.
- [ ] Không có số kết quả nào ngoài ví dụ minh hoạ (0.62 của Chibi là số thật trong paper; các flow khác ghi rõ là ví dụ).
- [ ] Chữ nhỏ nhất ≥ 9 pt ở kích thước canvas (hình sẽ scale về ~12 cm).
- [ ] Chỉ dùng hình tìm được bằng ô Search của draw.io (không chèn ảnh/logo ngoài).
