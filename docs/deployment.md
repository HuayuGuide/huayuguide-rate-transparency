# Deployment Guide (USDT/CNY only)

## 1) 创建仓库
- Repo: `HuayuGuide/huayuguide-rate-transparency`
- Visibility: `Public`
- 推送当前目录文件

## 2) 启用 Actions
- `Settings -> Actions -> General`
- `Workflow permissions` 选择 `Read and write permissions`

## 3) 首次执行
- 进入 `Actions -> Fetch Rate Snapshots`
- 点击 `Run workflow`
- 成功后检查：
  - `data/latest/usdt_cny.json`
  - `status/pipeline_status.json`
  - `status/source_health.json`

## 4) 站点接入
- 汇率中心主源读取：
  - `https://raw.githubusercontent.com/HuayuGuide/huayuguide-rate-transparency/main/data/latest/usdt_cny.json`
- 插件已内置主源优先与历史缓存兜底，无需额外短码。

## 5) 运维建议
- 每周检查一次 `status/source_health.json`
- 连续失败 >= 3 次时，检查 Binance/OKX 页面接口是否变更
- 口径调整时同步更新 `docs/methodology.md` + `CHANGELOG.md`
