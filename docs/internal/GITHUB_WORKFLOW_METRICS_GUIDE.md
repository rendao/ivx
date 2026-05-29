# GitHub Workflow Guide (IVX Metrics-Driven)

> First-read entry for new collaborators: `WORKFLOW.md` at repository root.

## Purpose
定义 IVX 项目的 GitHub Workflow 执行规范，确保：
- 交付流程稳定可审计
- 指标数据可持续产出
- Dashboard 指标能从 CI 自动更新

本指南参考了外部流程模板（`WORKFLOW.md`）并结合本仓库已实现能力（`ci.yml` + metrics summary + governance API）。

## Mandatory Flow
1. 明确需求范围与验收标准（Issue/PR 描述中可追溯）。
2. 在分支上实现，并保持模块责任人可见。
3. 提交前完成本地必检（测试、治理行为可记录性）。
4. 创建 PR，补齐风险说明与验证证据。
5. 必须通过 GitHub Actions 质量门禁（unit/integration/lint）。
6. `metrics-summary` 任务必须产出标准 JSON 指标工件。
7. 若配置 Dashboard 地址，CI 自动将指标推送到 `/api/progress`。
8. 合并后保留交接记录（用于后续 owner 接力）。

## Required Local Checks
- 推荐一条命令（减少重复输入）：
  - Windows: `scripts\\workflow.bat local`
  - Linux/macOS: `sh scripts/workflow.sh local`
- 等价拆分命令：
  - `python -m pytest -m "not integration"`
  - `python -m pytest -m integration`
  - `python tools/behavior_recordability_check.py --no-send`

说明：第三项用于验证治理行为事件是否可被当前契约记录，是治理指标可信度前提。

## Required PR Evidence
- What changed（改了什么）
- Why this change is needed（为什么要改）
- Validation result（测试/校验结果）
- Rollback plan（回滚或降级方案）
- Metrics impact（预期影响哪些 `pipeline_metrics.*` 字段）

## GitHub Workflow Topology (Repository Standard)

当前标准工作流文件：`.github/workflows/ci.yml`

### Job 1: unit-and-coverage
- Python 3.12 单版本门禁（精炼、稳定、成本低）
- 产物要求：
  - `artifacts/ci/junit-unit.xml`
  - `artifacts/ci/coverage.xml`

### Job 2: lint
- 语法/静态质量：flake8（阻塞式）

### Job 3: integration
- 依赖 unit + lint
- 产物要求：`artifacts/ci/junit-integration.xml`

### Job 4: metrics-summary
- 下载全部测试工件
- 通过 `.github/scripts/build_metrics_summary.py` 生成：
  - `artifacts/ci/output/metrics-summary.json`
- 上传 artifact：`dashboard-ci-metrics`
- 可选推送：`.github/scripts/push_metrics_summary.py` 推送到 Dashboard

## Metrics Contract Mapping

`build_metrics_summary.py` 输出至少应覆盖：
- `pipeline_metrics.testing.tests_passed`
- `pipeline_metrics.testing.tests_failed`
- `pipeline_metrics.testing.coverage_percent`
- `pipeline_metrics.testing.regressions`
- `pipeline_metrics.ci.last_build_status`
- `pipeline_metrics.ci.build_success_rate`

可选扩展（建议后续迭代）：
- `pipeline_metrics.commit.*`（可由 git/PR API 补充）
- `pipeline_metrics.governance.*`（由 `/api/governance/event` 驱动）

## Dashboard Push Strategy

### Secrets / Variables
`push_metrics_summary.py` 会读取以下环境变量：
- `DASHBOARD_API_URL`（例如 `http://<host>:8789/api/progress`）
- `DASHBOARD_PROJECT_NAME`
- `DASHBOARD_PROJECT_ID`
- `DASHBOARD_PROJECT_PATH`
- `DASHBOARD_PHASE`
- `DASHBOARD_TASK`
- `DASHBOARD_PROGRESS_PERCENT`

可在工作流中按仓库实际注入，例如：

```yaml
env:
  DASHBOARD_API_URL: ${{ secrets.DASHBOARD_API_URL }}
  DASHBOARD_PROJECT_NAME: ${{ vars.DASHBOARD_PROJECT_NAME }}
```

### Runtime Behavior
- 未配置 `DASHBOARD_API_URL`：仅上传 artifact，不推送，CI 不失败。
- 已配置 `DASHBOARD_API_URL`：自动推送并追加 CI 事件到 `recent_events`。

## Governance Event Integration

除 CI 指标外，建议在关键流程点调用：
- `POST /api/governance/event`

最小推荐事件：
- `plan_committed`
- `task_started` / `task_completed`
- `gate_passed` / `gate_failed`
- `decision_logged`
- `auth_prompted` + `auth_approved|auth_denied`

这样可持续产出 `pipeline_metrics.governance.*`，支撑可控性评分。

## Branch Protection Recommendation
建议将以下检查设为 Required：
- `Unit and Coverage`
- `Lint Checks`
- `integration`
- `Build Dashboard Metrics Summary`

## Release Rule
禁止直接发布，除非同时满足：
- CI 质量门禁通过
- 指标工件 `dashboard-ci-metrics` 可下载可解析
- 关键风险项有明确 owner 结论
- 存在可追溯交接记录（如后续仍有未完成事项）

## Quick Validation Checklist
1. 本地执行 `scripts\\workflow.bat local`（或 `sh scripts/workflow.sh local`）。
2. 手动触发/提交一次 CI。
3. 确认 `dashboard-ci-metrics` artifact 产出成功。
4. 下载并检查 `metrics-summary.json` 字段完整性。
5. 若配置 Dashboard URL，确认 `/api/progress` 已反映最新 CI 指标。