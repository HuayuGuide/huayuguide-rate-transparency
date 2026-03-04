# Deployment Guide

## 1) 创建 GitHub 仓库
- Repo: `HuayuGuide/huayuguide-rate-transparency`
- Visibility: Public
- Push 本目录全部文件。

## 2) 启用 Actions
- 打开仓库 Settings -> Actions -> General
- Workflow permissions 选择 `Read and write permissions`

## 3) 首次跑任务
- 进入 Actions -> `Fetch Rate Snapshots`
- 点击 `Run workflow`
- 成功后检查：
  - `data/latest/usdt_cny.json`
  - `status/source_health.json`
  - `status/pipeline_status.json`

## 4) 站点接入
- 将 `integrations/wordpress/hg-rate-transparency-snippet.php` 复制到 Snippets 或插件。
- 使用短码：
  - `[hg_usdt_rate pair="USDT/CNY"]`
  - `[hg_usdt_rate_table]`

## 5) 运维建议
- 每周检查一次 `status/source_health.json` 的 `fail_streak`。
- 连续失败 >= 3 时，优先检查数据源可达性与 endpoint 是否变更。
- 口径变更时同时更新 `docs/methodology.md` + `CHANGELOG.md`。
