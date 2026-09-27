# Leakage audit v2 — so sánh trước/sau sửa shortcut độ dài (Tuần 5, đợt 2)

## v1 (trước khi sửa)

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

- corr(tổng action_count thô, prefix_len) = **1.0000**
- Feature hệ số cao nhất: `action_count_lending_deposit` (coef=1.6352), coverage=1/11 incident positive

## v2 (sau khi sửa: action_count_*_ratio + coverage filter ≥2 incident)

```
                          feature      coef
         action_count_merge_ratio  0.441422
          action_count_swap_ratio -0.482011
      action_count_transfer_ratio -0.503630
action_count_bridge_deposit_ratio -2.012734
```

- Feature hệ số cao nhất: `action_count_merge_ratio` (coef=0.4414)
- Feature bị loại do coverage <2 (fit trên toàn bộ dataset, chỉ minh họa — thực tế tính per-fold): ['action_count_bridge_withdraw_ratio', 'action_count_lending_deposit_ratio', 'action_count_lending_withdraw_ratio', 'action_count_split_ratio', 'action_count_mixer_or_exit_ratio', 'action_count_other_ratio']

## So sánh PR-AUC/Macro-F1 trước/sau (MEAN ± STD trên 11 fold)
| Model | v1 mean PR-AUC | v1 std | v2 mean PR-AUC | v2 std | v1 mean F1 | v2 mean F1 |
|---|---|---|---|---|---|---|
| B0 | 0.093 | 0.042 | 0.069 | 0.029 | 0.475 | 0.482 |
| B1 | 0.602 | 0.226 | 0.563 | 0.212 | 0.517 | 0.524 |
| B2 | 0.303 | 0.291 | 0.337 | 0.312 | 0.500 | 0.482 |
