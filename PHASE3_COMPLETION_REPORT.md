# 阶段三完成报告：候选动作前瞻决策

更新日期：2026-08-08（阶段三首次验收；在线结果为历史快照）

## 结论

阶段三已完成动态任务—GUI 结构对齐、短期/长期评分、三模型不确定性、W0–W3 决策阶梯、H=1/2/3 有限步重排、覆盖率—风险分析和安全降级。515 条独立测试样本的 6 项工程验收门槛全部通过。

## 结构对齐

结构对齐器使用语义重叠、元素名称、角色兼容性、AXTree 深度、任务阶段、历史重复等 8 维特征，以种子 17、42、73 训练，按验证 MRR 选择种子 42。

| 指标 | 规则基线 | 学习模型 |
|---|---:|---:|
| 测试 Top-1 | 63.9% | 82.9% |
| 测试 Recall@3 | 100% | 100% |
| 测试 MRR | 0.8156 | 0.9054 |
| 结构错配率 | 36.1% | 17.1% |

## W0–W3 离线结果

| 方法 | 总体动作一致率 | 成功动作一致率 | 危险动作规避率 |
|---|---:|---:|---:|
| B0 reactive | 64.1% | 74.0% | 45.8% |
| W0 one-step | 34.2% | 68.8% | 65.8% |
| W1 structure | 34.0% | 68.8% | 65.5% |
| W2 multiscale | 21.2% | 58.4% | 88.7% |
| W3 adaptive | 35.7% | 64.9% | 66.5% |

515/515 状态成功匹配，候选合法率、安全记录动作 Recall@k、解释完整率、有限步合规率均为 100%。W3 平均置信度 0.690，端到端推理平均/P95 为 20.59/64.03 ms。

## H=1/2/3 消融

| 视野 | 动作一致率 | 平均延迟 |
|---|---:|---:|
| H=1 | 35.3% | 5.32 ms |
| H=2 | 23.9% | 13.58 ms |
| H=3 | 21.2% | 34.45 ms |

更深 rollout 在当前数据上累积偏差，因此 W3 使用置信度自适应视野，不把 H=3 固定作为默认策略。

## 真实 WebArena 在线贯通

GPU Agent 已通过 HTTP 推理服务与 SSH 转发连接本机真实 Reddit/WebArena。固定任务 27–31 共执行 30 个动作，动作执行率 100%、运行失败 0；但 5 个任务自主成功率仍为 0%。这证明系统链路可运行，不代表任务能力达标。

> 后续进展：阶段四已完成 Reddit、Shopping、GitLab 三站 9 题的 post-fix 回归，
> reactive 与 W4 均为 9/9。由于两者共享使用同题失败反馈修复的导航护栏，该结果不是
> 未见任务泛化估计，也不能证明世界模型带来在线增益；最终口径见
> `PHASE4_COMPLETION_REPORT.md`。

## 交付物

- `agent_world_model/structure_alignment.py`
- `agent_world_model/phase2_ensemble.py`
- `agent_world_model/remote_agent.py`
- `agent_world_model/phase3_agent.py`
- `configs/phase3_structure_alignment.json`
- `configs/phase3_planner.json`
- `scripts/train_structure_alignment.py`
- `scripts/evaluate_counterfactual_ranking.py`
- `scripts/evaluate_phase3_planner.py`
- `scripts/serve_phase3_inference.py`
- `artifacts/phase3/structure_aligner_best.pt`
- `data/reports/phase3_evaluation_ensemble_gpu.json`
- `data/reports/webarena_phase3_online_evaluation_gpu.json`

## 遗留问题（阶段三首次验收时）

真实 WebArena 成功率仍未提高，观察反事实规模不足，多步偏差明显；完整多站点 WebArena、相对 SR +10% 和执行反馈遗憾闭环应在阶段四继续完成。
