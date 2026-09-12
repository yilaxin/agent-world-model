# W1 基线策略进展记录

每条记录包含：日期、模块、改动摘要、政策标识、评测规模、归因前后对比与差分判定。

---

## 2026-09-12 · 基线建立（无改动）

- 工作集：GitLab 23 题 × 3 seed + Shopping 17 题 × 3 seed = 120 episodes（`configs/webarena_w1_workingset_*.json`，freeze `1e16fae…` / `e5f3d…` 族）
- 结果：**3/120（2.5%）**，GitLab 0/69、Shopping 3/51，评测器异常 0
- 归因（117 条失败）：循环 42、预算耗尽 38、流程路径 23、目标理解 6、缺终止 3、表单 3、动作执行 2
- 基线文件：`data/reports/webarena_w1_baseline_attribution.json`

## 2026-09-12 · M1 循环恢复（已实现，验证运行中）

- 政策标识：`reactive_rules_v2`（原 `reactive_rules_v1`），提交 `06cdfd2`
- 改动：
  1. 记录每次决策时的 `state_id`，动作后状态未变化即判定为**无效动作**；
  2. 无效动作及其目标 bid 进入 episode 级黑名单，**跨出内层 5 步历史窗口仍然生效**；
  3. 下一步优先选择黑名单之外的控制；若整页无可选项，按 **scroll → go_back → scroll(上)** 升级恢复；
  4. 状态一旦变化即清零计数与黑名单；每条 episode 的第一步重置全部记忆（同一 agent 实例跨 episode 复用）；
  5. 置信度 > 0.9 或由导航护栏产生的决策不被覆盖，站点流程保持原样。
- 单测：新增 6 项（跳过无效控件、黑名单跨窗口生效、升级为滚动、状态变化清零、episode 重置、护栏流程不被覆盖），全量 **148 passed / 23 skipped**
- 验证运行：2026-09-12 18:20 启动同一工作集（120 episodes，无 GPU），v1 报告已归档为 `*_v1.json`
- 判定：待 v2 归因 + `diff_failure_attribution.py --target loop_stall` 结果填入

---

## 待办

- [ ] M1 差分判定（目标：`loop_stall` 下降 ≥ 40%，其他类型涨幅 ≤ 10%，配对成功数不下降）
- [ ] M2 站点流程知识（`wrong_route` 23 条）
- [ ] M3 候选优先级与预算（`budget_exhausted` 38 条）
- [ ] W1 达标后重冻 W4 发布版并更新 Round-5 预登记中的 release 指纹
