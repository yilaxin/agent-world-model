# Agent 世界模型决策优化

本仓库实现《大创申报书 33.0》中的前三个阶段，当前重点交付为阶段二“动作条件世界模型”和阶段三“候选动作前瞻决策”。最终实验环境为 AutoDL RTX 4090、PyTorch 2.1.2+cu121、CUDA 12.1。

## 最终完成状态

- 数据集：13,348 条状态转移、5,930 个 episode、30 个任务，按 episode 切分为 9,388 / 2,017 / 1,943，无 episode 泄漏。
- 观察反事实：3,600 对全部有效，其中 3,050 对有信息，采集失败为 0，状态匹配率 100%。
- 阶段二：完成五次多种子 GPU 训练，验证集选择三个成员；独立测试状态变化 F1 98.69%、任务信号 F1 98.90%、风险 F1 94.39%、风险 AUROC 99.04%，12 项门禁全部通过。
- 阶段三反事实：测试集 477 个观察配对，其中 396 个有效配对；最佳单模型与集成 Pairwise Accuracy 均为 97.73%，集成平均决策遗憾从 0.0638 降到 0.0511。
- 阶段三多步：独立测试 H2=619、H3=329，长视野终止=94、严重失败=47，全部覆盖门禁通过。
- 诚实边界：本轮未配置完整 WebArena 多站点环境，因此没有新的在线成功率结果；历史 Reddit 5 任务为 0/5，不得用离线指标声称在线成功率提高。AndroidWorld 已完成官方 Python/SDK/API 33 AVD 安装并通过真实设备预检，但真实 reset/action 冒烟与任务级基线/规划器对比尚未通过，因此不能标记“迁移完成”。

完整结果：

- [阶段二、阶段三多次训练完善报告](PHASE23_MULTIRUN_COMPLETION_REPORT.md)
- `output/pdf/阶段二阶段三最终进度与遗留问题报告_2026-08-10.pdf`
- 私有看板：`agent-world-model-phase23-lzk.zhengkunlu4.chatgpt.site`

## 关键目录

```text
agent_world_model/                 核心编码器、世界模型、集成、结构对齐与规划器
artifacts/phase2/                  世界模型检查点与集成清单（完整模型在 GPU 服务器）
artifacts/phase3/                  结构对齐检查点
configs/                           数据、训练与评测配置
data/phase2_p2/                    最终数据卡
data/reports/                      最终机器可读 JSON 证据
scripts/                           数据、训练、评测、在线服务和报告脚本
site/                              Sites 私有结果看板
tests/                             单元测试
```

GPU 服务器工作目录：

```text
/root/autodl-tmp/agent_world_model_phase23_latest
```

## 统一复现

在安装 BrowserGym、Playwright、PyTorch 与 CUDA 的 GPU 环境中执行：

```bash
set -a
source .env
set +a
bash scripts/run_phase23_improvement.sh
```

脚本依次执行采集、质量门禁、五次多种子训练、三成员集成、阶段二独立测试、阶段三反事实排序与真实连续轨迹 H=1/2/3 评估。缺少 WebArena 多站点环境变量时会诚实跳过在线评测。

## 主要证据

- `data/phase2_p2/dataset_card.json`
- `data/reports/phase2_counterfactual_collection_p2.json`
- `data/reports/phase2_p2_multiseed_ensemble_gpu.json`
- `data/reports/phase2_p2_ensemble_evaluation_test_gpu.json`
- `data/reports/phase3_counterfactual_ranking_p2_gpu.json`
- `data/reports/phase3_multistep_observed_p2_gpu.json`
- `data/reports/androidworld_preflight_latest.json`

## 结果边界

阶段二和阶段三的离线指标衡量预测、校准、反事实排序与有限步轨迹漂移，不等于完整 WebArena 在线任务成功率。H=3 潜状态 MSE 虽通过预设相对上限，但仍差于 persistence baseline；完整多站点 WebArena 与相对 SR +10% 应在阶段四独立验证。
