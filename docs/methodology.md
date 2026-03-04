# Methodology (USDT/CNY Audit)

## 1) 用户视角的方向定义
- 充值：`USDT -> 平台 CNY`，看 `Bid`
- 提款：`平台 CNY -> USDT`，看 `Ask`

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

## 3) 时点固化
- 必须使用 `asof_ts` 对应快照
- 禁止使用“当前价”回算旧测试
- 快照包含：`bid`、`ask`、`mid`、`source`、`quality_score`、`calc_version`

## 4) 质量策略
- 广告过滤：高完成率 + 高历史单量优先
- 聚合方式：截尾均值 + 中位数混合
- 记录源健康：写入 `status/source_health.json`
