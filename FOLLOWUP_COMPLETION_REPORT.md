# 阶段二、阶段三补强工作完成报告

生成日期：2026-08-08  
GPU 服务器目录：`/root/autodl-tmp/agent_world_model_phase2`  
本地分支：`codex/phase2-world-model`

## 结论

本轮已完成 P1 数据扩充、真实成对反事实、严重失败正类补充、P1 世界模型重训、阶段三复验、本地 LLM 候选绑定与消融，以及 AndroidWorld 状态/动作适配代码。WebArena 已形成可重复在线评估，但自主规则 Agent 在固定 Reddit 子集上的成功率仍为 0%，不能声称总体成功率提高 10%。GitHub 因账户和 remote 缺失仍无法推送。

## 已完成工作

| 工作项 | 结果 |
|---|---|
| P1 数据规模 | 3333 条转移、1550 个 episode、30 个任务；达到 3000 条目标 |
| 数据划分 | 训练/验证/测试为 2342/476/515；无 example 重复、无 episode 泄漏 |
| 成对反事实 | 100 对、200 条真实环境执行转移；初始状态匹配率 100%；无跨 split 泄漏 |
| 严重失败 | 总计 175 条；验证 23 条、测试 28 条；反事实动作中 47 条 |
| P1 世界模型 | RTX 4090、AMP；最佳 epoch 35；验证和测试均 10/10 门禁通过 |
| 阶段二测试 | 状态变化 F1 0.9887；任务信号 F1 0.9773；风险 F1 0.9074；风险 AUROC 0.9936；进度/奖励 MAE 0.0612/0.0620 |
| 阶段三复验 | 515/515 状态匹配；候选合法率 100%；安全动作 Recall@K 100%；成功动作 Top-1 一致率 77.92%；风险分流率 64.79%；6/6 门禁通过 |
| WebArena | 固定任务 27-31、固定种子和预算；自主 SR 0%，AER 96.67%，AvgStep 6；评估器烟测 4/5，未计入 Agent SR |
| 本地 LLM | Qwen2.5-3B-Instruct 在 RTX 4090 绑定；30/30 生成成功、合法率 100%、Recall@K 76.67%、平均延迟 273.76 ms |
| AndroidWorld | accessibility tree 状态适配与 click/fill/type/scroll/back/press/noop 动作映射完成；2/2 单测通过 |
| 自动化测试 | GPU 服务器完整单元测试 39/39 通过 |

## 重要实现

- `scripts/collect_phase2_counterfactuals.py`：同任务、同种子、同初始状态执行事实和替代动作，保存真实结果。
- `agent_world_model/phase2_dataset.py`：新增成对有效性与跨 split 泄漏门禁。
- `agent_world_model/phase2_schema.py`：把真实的终止未成功结果纳入严重任务失败，保留数据来源审计。
- `scripts/evaluate_webarena_online.py`：把自主 Agent 指标与答案注入式 evaluator 烟测严格分开。
- `agent_world_model/phase3_candidates.py`：新增受约束本地 LLM 候选选择器，只能从已通过结构校验的候选池中选择。
- `scripts/evaluate_candidate_generators.py`：规则与 Qwen2.5-3B 的同预算消融。
- `agent_world_model/androidworld_adapter.py`：AndroidWorld 状态与动作迁移边界。
- `scripts/androidworld_preflight.py`：ADB、设备、SDK 与 Python 运行包预检。

## 尚未解决

1. **WebArena 自主成功率**：当前固定 Reddit 子集 SR 为 0%。已完成评估链路，不代表 Agent 能完成任务。
2. **完整 WebArena**：只部署 Reddit，尚未部署购物、GitLab、地图、维基等站点。
3. **VLM 消融**：文本 LLM 已绑定，图像 grounding 尚未验证。
4. **AndroidWorld 实机运行**：当前没有 ADB、Android SDK、模拟器和 `android_world` 运行包。
5. **GitHub 托管**：GitHub 连接器无账户，仓库无 remote，系统无 `gh` CLI，因此没有 push 或 PR。
6. **阶段四**：真实执行后的预测-现实偏差、遗憾值和在线反馈更新仍属于阶段四，未提前宣称完成。

## 主要结果位置

- P1 数据卡：`data/phase2_p1/dataset_card.json`
- P1 检查点：`artifacts/phase2/world_model_p1_best.pt`
- 阶段二测试：`data/reports/phase2_p1_evaluation_test_gpu.json`
- 阶段三复验：`data/reports/phase3_evaluation_p1_gpu.json`
- WebArena：`data/reports/webarena_online_evaluation_latest.json`
- LLM 消融：`data/reports/candidate_generator_ablation_gpu.json`
- AndroidWorld 预检：`data/reports/androidworld_preflight_latest.json`
- 最终 PDF：`output/pdf/阶段二阶段三补强工作完成情况与遗留问题.pdf`

## 复现命令

```bash
python scripts/train_phase2_world_model.py --config configs/phase2_world_model_p1.json --device cuda
python scripts/evaluate_phase2_world_model.py --config configs/phase2_world_model_p1.json --split test --device cuda
python scripts/evaluate_phase3_planner.py --checkpoint artifacts/phase2/world_model_p1_best.pt --device cuda --dataset-dir data/phase2_p1
HF_ENDPOINT=https://hf-mirror.com python scripts/evaluate_candidate_generators.py --limit 30 --device cuda --dataset-dir data/phase2_p1
python scripts/evaluate_webarena_online.py --mode both
python scripts/androidworld_preflight.py
```
