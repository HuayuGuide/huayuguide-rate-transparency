# Sources and Reliability (USDT/CNY)

## Primary sources
- Binance P2P（网页公开接口）
- OKX P2P（网页公开接口）

## Fallback strategy
- 同轮抓取失败：优先另一家交易所补齐 bid/ask
- 两家都失败：保留上一次 `data/latest/usdt_cny.json`，并在 `pipeline_status.json` 标记 `degraded`

## Notes
- P2P 更贴近中文用户真实换汇场景
- 当前仓库不使用 Spot+FX 作为业务口径
