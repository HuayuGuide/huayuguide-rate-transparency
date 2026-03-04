# HuayuGuide Rate Transparency

公开汇率透明仓，服务 [huayuguide.com](https://huayuguide.com) 的审计型汇率展示。

目标：
- 对用户公开可复核的汇率快照与方法论。
- 对站点提供稳定的只读 JSON 数据源。
- 对 SEO 提供持续更新的技术信任证据（数据、口径、变更日志）。

## 推荐 GitHub 项目名称
- 仓库名（推荐）：`huayuguide-rate-transparency`
- 组织/账号（推荐）：`HuayuGuide`
- 项目显示名：`HuayuGuide Rate Transparency`
- 项目描述：`Audit-grade USDT P2P benchmark snapshots for HuayuGuide.`

## 推荐仓库设置
- Visibility: `Public`
- Default branch: `main`
- Issues: `On`
- Discussions: `Optional`
- Actions permissions: `Read and write`（用于自动提交快照）
- Branch protection: 建议保护 `main`，仅允许 PR 合并

## 数据口径（核心）
- 充值（USDT -> 平台 CNY 余额）：按 **P2P 买盘价（Bid）** 对标。
- 提款（平台 CNY 余额 -> USDT）：按 **P2P 卖盘价（Ask）** 对标。
- 历史记录必须按测试时点 `asof_ts` 计算，不用当前价回算。

完整定义见 [docs/methodology.md](./docs/methodology.md)。

## 目录说明
- `data/latest/`: 当前快照
- `data/history/`: 追加式历史快照（JSONL）
- `status/`: 数据源健康状态与任务状态
- `schemas/`: JSON schema
- `scripts/`: 抓取与聚合脚本
- `.github/workflows/`: 自动化任务
- `integrations/wordpress/`: WordPress 接入示例

## 快速开始
1. Fork 或创建同名公开仓。
2. 复制本目录所有文件。
3. 进入 Actions，手动执行 `Fetch Rate Snapshots`。
4. 检查 `data/latest/usdt_cny.json` 是否更新。
5. 在站点接入 `integrations/wordpress/hg-rate-transparency-snippet.php`。

## 输出字段示例
`data/latest/usdt_cny.json`：
- `pair`: `USDT/CNY`
- `bid`, `ask`, `mid`
- `asof_ts`, `asof_iso`
- `source`, `source_count`, `sample_count`, `dispersion`
- `quality_score`, `calc_version`, `generated_at`

## 审计声明
本仓为“参考汇率透明层”，不构成投资建议。详见 [DISCLAIMER.md](./DISCLAIMER.md)。
