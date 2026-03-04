# Security Policy

## Scope
本仓不存储主站密钥、数据库密码或私有凭证。

## Reporting
如发现数据篡改、工作流异常、依赖漏洞，请通过以下方式反馈：
- Email: security@huayuguide.com
- GitHub Issue: 标记 `security`

## Practices
- GitHub Actions 仅授予最小必要权限。
- 输出文件 schema 校验失败时，任务直接失败，不覆盖旧快照。
- 工作流使用 `concurrency` 防并发覆盖。
