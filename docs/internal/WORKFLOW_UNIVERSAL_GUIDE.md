# Workflow Guide (Universal, Metrics-Ready)

## Purpose
给任意项目一套最小可执行、可审计、可度量的 GitHub Workflow。

## Ready-to-Use Templates
- PR template: `.github/PULL_REQUEST_TEMPLATE.md`
- CI template: `docs/internal/templates/ci-metrics-template.yml`
- Local check scripts: `scripts/workflow.py`, `scripts/workflow.sh`, `scripts/workflow.bat`

## Mandatory Flow
1. 需求确认：范围 + 验收标准（Issue/PR 可追溯）。
2. 分支开发：在 feature 分支实现，不直接改主分支。
3. 本地必检：提交前跑最小测试与静态检查。
4. PR 证据：补齐变更原因、验证结果、风险与回滚。
5. CI 门禁：必须通过 required checks。
6. 指标产物：CI 生成标准化 metrics artifact（JSON）。
7. 合并条件：通过审批 + 通过门禁 + 风险可控。
8. 交接收尾：记录后续事项、owner、时间点。

## Required Local Checks (Template)
- unit tests
- integration tests（若项目有）
- lint / type check

说明：命令由项目自行实现，但以上三类信号应可复现。

推荐统一入口（减少重复命令和沟通 token）：
- Windows: `scripts\\workflow.bat local`
- Linux/macOS: `sh scripts/workflow.sh local`

## Required PR Evidence
- What changed
- Why needed
- Validation result
- Risk and rollback plan
- Metrics impact（影响了哪些核心指标）

## CI Baseline Topology
推荐 4 类 job：
- test: 单元/集成测试，输出 junit 报告
- quality: lint/security/type-check
- package(optional): 构建发布物
- metrics-summary: 汇总测试与流水线结果，输出 metrics JSON

## Metrics Contract (Minimal)
建议统一为：

```json
{
  "pipeline_metrics": {
    "testing": {
      "tests_passed": 0,
      "tests_failed": 0,
      "coverage_percent": 0,
      "regressions": 0
    },
    "ci": {
      "last_build_status": "success",
      "build_success_rate": 100
    }
  }
}
```

## Branch Protection (Recommended)
至少设为 required：
- test
- quality
- metrics-summary
- at least 1 reviewer approval

## Release Rule
禁止直接发布，除非：
- required checks 全绿
- 指标工件可下载并可解析
- 存在可执行回滚方案
- 关键 owner 明确

## Feasibility by Project Maturity
- Low（小项目）: 先做 test + quality + PR evidence。
- Medium: 增加 metrics-summary artifact。
- High（平台化）: 增加外部指标推送与治理事件。

## Anti-Patterns
- 无验收标准直接开发
- PR 无验证证据
- CI 仅看 pass/fail，不留指标工件
- 指标与业务语义脱节（不可解释）