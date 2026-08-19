# P0 第二轮在线实验状态（已完成，2026-08-15）

## 结论口径

- 第二轮开发集允许策略迭代，不是未见任务泛化估计；开发集 Reactive 与 W4 均为 1/30（3.33%），未观察到世界模型增益。
- 第二套 holdout 在任何 episode 运行前冻结；冻结后未修改任务、策略、权重、候选生成、护栏实现、种子或预算，也未使用 holdout 任务反馈调参。
- 本次结果只代表三站 90 个冻结未见任务、seed 0、每题 12 步的 Classic WebArena 子集，不是完整 812 题 benchmark 成功率。
- 阶段二至阶段四的离线预测、校准、反事实排序和有限步漂移指标，均不等于本次在线任务成功率。

## 冻结与完整性

- 主清单：`configs/webarena_p0_round2_holdout_frozen.json`。
- 主冻结哈希：`a772943ee036958f48ec17249a25865d7a779217797618ef10a03881661230b9`。
- W4 发布指纹：`fe52d922a891ca9464b2691781b2f3d4594eecf3eaed82ff315d849b34118a24`。
- GitLab、Reddit、Shopping 各 30 题，共 90 个唯一任务；四个单元格各 90 个 episode，共 360 个已判定 episode。
- 四单元格：`reactive_guard_off`、`reactive_guard_on`、`w4_guard_off`、`w4_guard_on`。
- 每个 episode 固定 12 步、seed 0；最终分析中 `task_feedback_used=false`，`evaluator_failures=[]`。
- 逐站冻结哈希：
  - GitLab：`377445fbcbe2db2fb0f310290710e4703a2e3e8f61c8e1304d054db747aa3e87`
  - Reddit：`7d36393b46e71c3538c41b784d0f07012b9baff1293e8a6e7bcc22fbe0bfd1db`
  - Shopping：`fce7e3e1f0fcffc06c7bb49ad03e3702b736e3dc8040109af39cc38622dbeef7`

## 四单元格在线结果

| 单元格 | 成功/总数 | 成功率 | Wilson 95% CI |
|---|---:|---:|---:|
| Reactive / 护栏关 | 1/90 | 1.11% | [0.20%, 6.03%] |
| Reactive / 护栏开 | 2/90 | 2.22% | [0.61%, 7.74%] |
| W4 / 护栏关 | 1/90 | 1.11% | [0.20%, 6.03%] |
| W4 / 护栏开 | 2/90 | 2.22% | [0.61%, 7.74%] |

逐站结果：

- GitLab：四单元格均为 1/30（3.33%）。
- Reddit：Reactive/W4 护栏关均为 0/30；Reactive/W4 护栏开均为 1/30（3.33%）。
- Shopping：四单元格均为 0/30。

## 配对 2×2 因果分析

- 世界模型效应（护栏关）：Reactive 1.11% → W4 1.11%，绝对变化 0.00 个百分点，配对 95% CI `[0.00, 0.00]` 个百分点，相对提升 0%。
- 世界模型效应（护栏开）：Reactive 2.22% → W4 2.22%，绝对变化 0.00 个百分点，配对 95% CI `[0.00, 0.00]` 个百分点，相对提升 0%。
- 世界模型主效应（跨护栏平均）：0.00 个百分点，95% CI `[0.00, 0.00]`。
- 护栏共享主效应（跨 Agent 平均）：+1.11 个百分点，95% CI `[0.00, 3.33]`。相对点估计为 +100%，但仅对应 1 个额外成功，且置信区间包含 0，不能视为稳定收益，也不能归因于世界模型。
- 世界模型×护栏交互：0.00 个百分点，95% CI `[0.00, 0.00]`。

## +10% 验收结论

- 主对比为 W4/护栏开减去 Reactive/护栏开：绝对变化 0.00 个百分点，相对提升 0%。
- `point_estimate_meets_target=false`，`claim_allowed_from_frozen_holdout=false`。
- 因此“相对 SR +10%”目标未达到，不能声明世界模型改善了未见 WebArena 在线成功率。

## 环境失败恢复说明

- 原始运行中，部分任务的官方模糊评测器在 agent 尚未提交答案时要求外部 `OPENAI_API_KEY`，导致初始化失败；这些 episode 未被直接计作模型失败。
- 恢复只对报告中明确记录为该凭据错误的冻结任务执行，任务 ID、模式、护栏状态、seed、12 步预算和模型指纹均保持不变。
- 无答案初始化适配器仅在尚未提交答案时返回 `score=0, done=false`；一旦提交答案，仍调用原官方 evaluator，不读取或注入参考答案。
- 主报告、传输恢复报告与模糊评测恢复报告按冻结任务 ID 合并；合并器拒绝重复、缺失、非白名单任务或哈希漂移。最终 12 个逐站单元格均为 30/30，合并与分析返回码均为 0。

## 证据索引

- 最终分析：`data/reports/webarena_p0_round2_2x2_analysis.json`
  - SHA-256：`f61c5f47a255705d953efe7023c945f7b4140ae86d9ecac0874562b703da5a1b`
- 12 个完整逐站报告：`data/reports/webarena_p0_round2_consolidated_*.json`
- 主轨迹：`data/trajectories_webarena_p0_round2_holdout/`
- 恢复轨迹：`data/trajectories_webarena_p0_round2_recovery/`
- 运行状态：`tmp/round2_holdout/matrix_status.tsv`、`tmp/round2_holdout/recovery_status.tsv`
- Windows 归档已逐文件核验 433 个轨迹 SHA-256，0 个缺失或不匹配。

## 下一步

1. 在新的开发集提升基础策略、候选生成、动作纠错和任务理解，不查看本 holdout 调参。
2. 对本次约 360 条轨迹按任务理解、元素定位、动作执行、循环/停滞、预算耗尽和 evaluator 类型做错误诊断。
3. 修复后重新冻结第三套未见集合，再复验相同 2×2；只有新冻结集合支持时才能声明提升。
4. 后续扩展更多站点和多种子；AndroidWorld 5/7 仍只作少量迁移检查。
