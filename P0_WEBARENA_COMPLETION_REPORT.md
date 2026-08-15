# WebArena P0 未见任务 2×2 验收报告

> 证据截止：2026-08-14。本文由冻结实验清单、12 份站点单元报告、12 份恢复单元报告、配对分析 JSON 与逐步轨迹归档生成；最终数值以 `data/reports/webarena_p0_2x2_analysis.json` 为准。

## 验收结论

P0 的实验交付已完成，但性能目标未达成：

- 未见任务 holdout：完成。修复前冻结 GitLab、Reddit、Shopping 各 30 题，共 90 个历史未使用任务。
- 隔离世界模型因果贡献：完成。执行 Reactive/W4 × 导航护栏关/开四单元，同任务、同 seed、同 12 步预算配对，共 360 episodes。
- 相对成功率 +10%：未达成。四单元均为 0/90；W4 相对 Reactive 的绝对成功率差为 0.00 个百分点。Reactive 基线为 0%，相对提升不可定义，不能声称达到 +10%。

因此，P0 应记录为“实验设计、在线执行与证据交付完成；在线能力与申报性能指标失败”。

## 冻结与因果设计

| 项目 | 冻结值 |
|---|---|
| 站点 | GitLab / Reddit / Shopping |
| 任务 | 30 题/站，90 个唯一任务 |
| 单元 | Reactive/W4 × 护栏关/开 |
| seed | 0 |
| 步数预算 | 每题最多 12 步 |
| 总 episode | 360 |
| 任务反馈 | 未使用 |
| 任务冻结 SHA-256 | `cfd7547da262a9a678f43925c301e5acb3cd54efffa753a0bdd46e290288d9fb` |
| W4 发布指纹 | `427049583ec231a5f6c49450cd2da51da36ea255ae42ccb1770a9a027b956652` |

冻结后没有更换任务、按 holdout 失败调参、修改模型权重、修改导航护栏或改变步数预算。中断运行与曾发生的同站重叠运行被隔离，不进入最终分析。W4 远程健康证明逐单元核对护栏状态、发布指纹和 `semantic_goal_priority=false`。

## 四单元关键数据

最终表格由分析 JSON 自动生成。主要报告成功数、SR、Wilson 95% CI、动作执行率、平均步数与平均延迟。预期最终结果为四单元均 0/90；单个 90 题全零单元的 SR Wilson 95% CI 上界约为 4.1%。

配对分析使用 90 个任务一一配对和 20,000 次任务级 bootstrap：

- W4-Reactive（护栏关）：0.00 个百分点，95% CI [0.00, 0.00]。
- W4-Reactive（护栏开）：0.00 个百分点，95% CI [0.00, 0.00]。
- 护栏主效应：0.00 个百分点，95% CI [0.00, 0.00]。
- 世界模型×护栏交互：0.00 个百分点，95% CI [0.00, 0.00]。

护栏效应只解释为共享导航规则效应；只有同一护栏水平下的 W4-Reactive 对比估计世界模型贡献。本次没有观察到世界模型成功率贡献。由于四单元全零，实验还存在地板效应：它不能回答世界模型在一个已经具备非零成功率的更强基础策略上是否改善边缘任务。

## 官方模糊判分器依赖

部分 `fuzzy_match` 任务的官方 evaluator 需要外部 API 密钥。原始运行在 `env.reset` 构造 evaluator 后的无答案校验阶段被密钥检查阻断，因而不能把 0 字节占位轨迹算作 Agent 失败。

项目随后使用最小恢复适配器重新真实执行这些任务：仅当 Agent 尚未提交答案时，把校验短路为“score=0、done=false”；若出现 `send_msg`，仍委托原官方 evaluator，不设置本地答案判分器。28 条恢复轨迹均非空、执行真实决策、没有 `send_msg`，因此可确定为失败。本项目不读取或注入参考答案，也不伪造 LLM judge；原始异常、恢复规则、报告路径、轨迹路径与 SHA-256 全部保留在分析 JSON。

## 与早期 9 题回归的关系

早期三站 9 题 post-fix 回归中 Reactive 与 W4 均为 9/9，但它使用了同题失败反馈修复后的共享导航护栏，只证明修复后的端到端链路可以稳定回归。

本次 P0 的 90 题在修复前冻结且没有使用任务反馈，四单元均为 0/90。二者差异说明早期 9/9 不能外推为未见任务泛化，也不能归因于世界模型。不同任务集合之间不做显著性检验。

## 完成质量与遗留问题

完成得好的部分：

- 冻结任务与发布指纹可复核，不因负结果替换样本。
- 同任务四单元严格配对，预算一致，报告绝对百分点、相对值可评价性和配对 CI。
- 正式轨迹采用白名单归档并逐条核验 SHA-256。
- 负结果、外部依赖和地板效应透明呈现。

完成不足与遗留问题：

- 基础策略没有在 90 个未见任务中成功任何一题，在线能力严重不足。
- W4 只能重排候选动作，无法补偿规则候选生成和目标理解的缺失；应优先提升基础策略。
- 当前只覆盖三站、seed 0 和 90/812 题，不能代表完整 benchmark。
- 下一轮必须在独立开发集上修复，不能触碰本次 holdout；修复完成后另行冻结第二套未见集合复验。

## 证据索引

- 冻结主清单：`configs/webarena_p0_holdout_frozen.json`
- 三站冻结配置：`configs/webarena_p0_holdout_{gitlab,reddit,shopping}_frozen.json`
- 最终分析：`data/reports/webarena_p0_2x2_analysis.json`
- 原始单元报告：`data/reports/webarena_p0_<site>_<mode>_guard_<state>.json`
- 恢复单元报告：`data/reports/webarena_p0_recovery_<site>_<mode>_guard_<state>.json`
- 清洁轨迹归档：`data/trajectories_webarena_p0_evidence/`
- 运行器：`scripts/run_webarena_p0_cell.sh`
- 恢复适配器：`scripts/recover_webarena_p0_fuzzy_episodes.py`
- 分析器：`scripts/analyze_webarena_p0_2x2.py`
- PDF 构建器：`scripts/build_webarena_p0_completion_pdf.py`
