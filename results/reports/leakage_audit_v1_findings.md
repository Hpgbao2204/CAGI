# Leakage audit — baseline B2 (Bước 5, Tuần 5)

## Hệ số B2 (fit trên toàn bộ 1002 dòng)

```
                      feature      coef
 action_count_lending_deposit  1.635220
           action_count_merge  1.232429
   action_count_mixer_or_exit  0.786759
            action_count_swap  0.076137
           action_count_split  0.012839
 action_count_bridge_withdraw  0.000000
action_count_lending_withdraw  0.000000
           action_count_other  0.000000
        action_count_transfer -0.003376
  action_count_bridge_deposit -0.024651
```

## Tương quan
- pearson(tổng action_count, prefix_len) = 1.0000
- pearson(tổng action_count, label) = -0.0454

## Feature hệ số cao nhất: `action_count_lending_deposit`
- Xuất hiện ở 1/11 group positive.

## Phát hiện
- CANH BAO: tong action_count (dung boi B2) tuong quan MANH voi prefix_len (pearson r=1.000) — khop voi canh bao o EDA Buoc 1 (IQR do dai 2 lop khong chong lan). B2 co nguy co dang hoc PHAN LON tu 'do dai/so luong action' (cardinality) hon la NGU NGHIA loai hanh dong — day la 1 dang shortcut, khong phai tin hieu typology laundering that su.
- CANH BAO: feature co he so cao nhat ('action_count_lending_deposit') chi xuat hien o 1/11 group positive — co the la dac diem rieng cua 1-2 incident thay vi tin hieu chung cho ca lop positive.
