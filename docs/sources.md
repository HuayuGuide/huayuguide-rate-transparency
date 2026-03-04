# Sources and Reliability

## Primary
- Binance P2P (public web endpoint)
- OKX P2P (public web endpoint)

## Fallback
- Binance Spot / OKX Spot / CoinGecko
- Fiat FX feed (for non-primary fallback synthesis)

## Notes
- P2P 数据更贴近中文用户真实换汇场景。
- Spot 不等于用户真实成交价，仅用于兜底与完整性保障。
