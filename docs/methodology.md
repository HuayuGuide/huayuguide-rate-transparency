# Methodology (Audit-Grade FX)

## 1) 方向定义（用户视角）

- 充值：`USDT -> 平台 CNY 余额`
  - 用户动作：卖出 USDT
  - 参考价：`Bid`（买盘价）
- 提款：`平台 CNY 余额 -> USDT`
  - 用户动作：买入 USDT
  - 参考价：`Ask`（卖盘价）

口诀：
- 你卖 U，看 Bid
- 你买 U，看 Ask

## 2) 记录级计算

### 充值暗扣
- `expected_cny = usdt_in * bid_asof`
- `loss_cny = expected_cny - actual_cny`
- `loss_pct = loss_cny / expected_cny`

### 提款暗扣
- `expected_usdt = cny_out / ask_asof`
- `loss_usdt = expected_usdt - actual_usdt`
- `loss_pct = loss_usdt / expected_usdt`

## 3) 时点与快照

- 口径强制使用 `asof_ts`（测试发生时点）对应的快照。
- 禁止使用“当前最新价”回算历史测试。
- 快照字段应包含：`source`, `sample_count`, `quality_score`, `calc_version`。

## 4) 手续费与汇率偏差分离

- `total_loss_pct`：总损耗（包含手续费）
- `fx_deviation_pct`：纯汇率偏差（不含手续费）

前端建议同时展示两行，避免用户误读。

## 5) 数据源优先级

1. Binance P2P
2. OKX P2P
3. Spot+FX fallback（仅兜底，不作为首选业务口径）

## 6) 质量与退化策略

- 广告过滤：优先高完成率与高历史订单商家。
- 统计方法：截尾均值 + 中位数混合，降低刷单干扰。
- 单源失效：降级到其他源，并记录 `status/source_health.json`。
