# HuayuGuide Rate Transparency

公开汇率透明仓，服务 [huayuguide.com](https://huayuguide.com) 的审计汇率中心。

当前版本只维护一个快照：`USDT/CNY`。

## 输出文件
- `data/latest/usdt_cny.json`：当前最新快照
- `data/history/YYYY-MM/usdt_cny.jsonl`：历史追加记录
- `status/pipeline_status.json`：任务状态
- `status/source_health.json`：数据源健康状态

## 数据口径
- 充值（USDT -> 平台 CNY）：参考 `Bid`
- 提款（平台 CNY -> USDT）：参考 `Ask`
- 不用当前价回算历史，按 `asof_ts` 固化

完整说明见 [docs/methodology.md](./docs/methodology.md)。

## 运行方式
1. 仓库保持 `Public`
2. 启用 GitHub Actions 的 `Read and write permissions`
3. 手动或定时运行 `Fetch Rate Snapshots`
4. 检查 `data/latest/usdt_cny.json` 是否更新

## 对接插件
插件汇率中心读取 GitHub 快照（`data/latest/usdt_cny.json`）作为主源，实时失败时回退站内历史缓存。

## 审计声明
本仓仅提供参考汇率快照，不构成投资建议。见 [DISCLAIMER.md](./DISCLAIMER.md)。
